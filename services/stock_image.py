"""
Stock recipe-image sourcing: find a real, license-free photo for a recipe and
vet it with a vision model before use. This is the PRIMARY image source for
ingestion; callers fall back to DALL-E only when this returns None.

Pipeline per recipe:
  1. AI-extract a stock-photo search query from the recipe name + cuisine
     (strips brand/appliance/possessive noise, phrases the finished plated dish).
  2. Search Pexels and Pixabay (Pixabay AI-generated + low-quality hits filtered out).
  3. Vision-vet each candidate against the recipe (gpt-4o-mini, biased to reject)
     so we never ship a mismatched photo (no hotdog for a pasta recipe).
  4. Download the first vetted winner at full resolution, re-encode to a
     reasonably-sized JPEG, and return it with provenance metadata.

Licensing: Pixabay requires no attribution; Pexels asks for photographer credit
(captured in StockImageResult.credit / persisted via the backend image_source +
credit fields). Feasibility validated 2026-06-23: ~52% of the live catalog gets a
vetted real photo, the rest correctly fall back to AI.

Env vars: PEXELS_API_KEY, PIXABAY_API_KEY, OPENAI_API_KEY.
Optional: STOCK_VET_MODEL (default gpt-4o-mini), STOCK_QUERY_MODEL (default gpt-4o-mini).
"""

from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass
from typing import Callable, List, Optional

import requests
from PIL import Image

# Source identifiers — must match the backend image_source values.
SOURCE_PEXELS = "pexels"
SOURCE_PIXABAY = "pixabay"
SOURCE_AI = "ai"

# Tuning (validated by the 2026-06-23 spike).
CONFIDENCE_THRESHOLD = 0.70      # a candidate must be match=True AND conf >= this
CANDIDATES_PER_SOURCE = 3        # vet up to N candidates from each source
VET_IMAGE_SIZE = "medium"        # Pexels variant sent to the vision model (cheap)
MAX_DIMENSION = 1600             # downscale the winner's longest side to this
JPEG_QUALITY = 88                # matches scripts/backfill_recipe_images.py
HTTP_TIMEOUT = 20


@dataclass
class StockImageResult:
    jpeg_bytes: bytes
    source: str            # SOURCE_PEXELS | SOURCE_PIXABAY
    credit: str            # photographer / contributor name (for attribution)
    page_url: str          # source page (attribution link)
    query: str             # the search query that found it
    confidence: float      # vet confidence
    vet_reason: str
    width: int
    height: int


@dataclass
class _Candidate:
    source: str
    vet_url: str           # cheap/medium image sent to the vetting model
    full_url: str          # full-res image to download for the winner
    credit: str
    page_url: str


class StockImageFinder:
    def __init__(
        self,
        openai_client=None,
        pexels_key: Optional[str] = None,
        pixabay_key: Optional[str] = None,
        log: Optional[Callable[[str], None]] = None,
    ):
        self.pexels_key = pexels_key or os.environ.get("PEXELS_API_KEY")
        self.pixabay_key = pixabay_key or os.environ.get("PIXABAY_API_KEY")
        self.vet_model = os.environ.get("STOCK_VET_MODEL", "gpt-4o-mini")
        self.query_model = os.environ.get("STOCK_QUERY_MODEL", "gpt-4o-mini")
        self._log = log or (lambda m: None)

        self.client = openai_client
        if self.client is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)

    @property
    def enabled(self) -> bool:
        """True only if we have everything needed to search + vet."""
        return bool(self.pexels_key or self.pixabay_key) and self.client is not None

    # ── public API ────────────────────────────────────────────────────────────
    def find(self, name: str, cuisine: str = "") -> Optional[StockImageResult]:
        """Return a vetted real photo for the recipe, or None to fall back to AI."""
        if not self.enabled:
            self._log("Stock image finder disabled (missing keys or OpenAI client)")
            return None
        name = (name or "").strip()
        if not name:
            return None

        query = self._extract_query(name, cuisine)
        self._log(f"🔎 Stock search query: \"{query}\" (recipe: {name})")

        candidates: List[_Candidate] = []
        if self.pexels_key:
            candidates += self._search_pexels(query)
        if self.pixabay_key:
            candidates += self._search_pixabay(query)

        for c in candidates:
            verdict = self._vet(name, cuisine, c.vet_url)
            if verdict["match"] and verdict["confidence"] >= CONFIDENCE_THRESHOLD:
                self._log(f"✅ Vetted {c.source} photo (conf {verdict['confidence']:.2f}): {verdict['reason']}")
                downloaded = self._download_jpeg(c.full_url)
                if downloaded is None:
                    self._log(f"⚠️  Winner download failed, trying next candidate")
                    continue
                jpeg_bytes, w, h = downloaded
                return StockImageResult(
                    jpeg_bytes=jpeg_bytes, source=c.source, credit=c.credit,
                    page_url=c.page_url, query=query,
                    confidence=verdict["confidence"], vet_reason=verdict["reason"],
                    width=w, height=h,
                )

        self._log(f"↩️  No vetted stock photo for \"{name}\" — will fall back to AI")
        return None

    # ── query extraction ──────────────────────────────────────────────────────
    _QUERY_SYSTEM = (
        "You turn a recipe title (and cuisine) into the best SEARCH QUERY for finding a "
        "stock photo of the finished, plated dish. Strip filler ('best', 'easy', "
        "'perfect for breakfast', '30-minute', 'one-pan'), brand/restaurant names, "
        "possessives ('Aunt Mary's'), cook-method prefixes ('air fryer', 'instant pot', "
        "'sheet pan'), and states like 'leftover'/'frozen'. Phrase it as the FINISHED dish "
        "a food photographer would tag; if a method changes appearance, reflect the cooked "
        "result (e.g. 'frozen brussels sprouts' -> 'roasted brussels sprouts'). Use the "
        'canonical dish name, 1-4 words. Respond ONLY as JSON: {"query": "<search terms>"}'
    )

    def _extract_query(self, name: str, cuisine: str) -> str:
        try:
            resp = self.client.chat.completions.create(
                model=self.query_model, max_tokens=40, temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self._QUERY_SYSTEM},
                    {"role": "user", "content": f"Title: {name}\nCuisine: {cuisine or 'n/a'}"},
                ],
            )
            q = json.loads(resp.choices[0].message.content).get("query", "").strip()
            return q or name
        except Exception as e:
            self._log(f"⚠️  Query extraction failed ({e}); using raw title")
            return name

    # ── search ────────────────────────────────────────────────────────────────
    def _search_pexels(self, query: str) -> List[_Candidate]:
        try:
            r = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": self.pexels_key},
                params={"query": query, "per_page": CANDIDATES_PER_SOURCE, "orientation": "square"},
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            out = []
            for p in r.json().get("photos", []):
                src = p.get("src", {})
                out.append(_Candidate(
                    source=SOURCE_PEXELS,
                    vet_url=src.get(VET_IMAGE_SIZE) or src.get("medium"),
                    full_url=src.get("original") or src.get("large2x") or src.get("large"),
                    credit=p.get("photographer", ""),
                    page_url=p.get("url", ""),
                ))
            return [c for c in out if c.vet_url and c.full_url]
        except Exception as e:
            self._log(f"⚠️  Pexels search error: {e}")
            return []

    def _search_pixabay(self, query: str) -> List[_Candidate]:
        try:
            r = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": self.pixabay_key, "q": query, "image_type": "photo",
                    "category": "food", "safesearch": "true",
                    "per_page": max(CANDIDATES_PER_SOURCE, 3),
                },
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            out = []
            for h in r.json().get("hits", []):
                if h.get("isAiGenerated") or h.get("isLowQuality"):
                    continue  # never source an AI image; this is the whole point
                out.append(_Candidate(
                    source=SOURCE_PIXABAY,
                    vet_url=h.get("webformatURL"),
                    full_url=h.get("largeImageURL") or h.get("webformatURL"),
                    credit=h.get("user", ""),
                    page_url=h.get("pageURL", ""),
                ))
                if len(out) >= CANDIDATES_PER_SOURCE:
                    break
            return [c for c in out if c.vet_url and c.full_url]
        except Exception as e:
            self._log(f"⚠️  Pixabay search error: {e}")
            return []

    # ── vetting ───────────────────────────────────────────────────────────────
    _VET_SYSTEM = (
        "You vet stock photos for use as the HERO image of a recipe in a cooking app. "
        "Given a recipe (name + cuisine) and a photo, decide if the photo accurately and "
        "appetizingly depicts THAT finished dish (or a very close, honest representation). "
        "REJECT if it shows a clearly different dish, only raw/unprepared ingredients, heavy "
        "text/watermark/logos, packaging, a person dominating the frame, or is misleading or "
        "unappetizing. Bias toward rejection: when uncertain, set match=false. Respond ONLY "
        'with compact JSON: {"match": bool, "confidence": 0.0-1.0, "reason": "<=12 words"}.'
    )

    def _vet(self, name: str, cuisine: str, image_url: str) -> dict:
        try:
            resp = self.client.chat.completions.create(
                model=self.vet_model, max_tokens=120, temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self._VET_SYSTEM},
                    {"role": "user", "content": [
                        {"type": "text", "text": f"Recipe: {name}\nCuisine: {cuisine or 'n/a'}"},
                        {"type": "image_url", "image_url": {"url": image_url, "detail": "low"}},
                    ]},
                ],
            )
            d = json.loads(resp.choices[0].message.content)
            return {
                "match": bool(d.get("match")),
                "confidence": float(d.get("confidence", 0)),
                "reason": str(d.get("reason", ""))[:120],
            }
        except Exception as e:
            # A fetch/parse failure is a non-match; move on to the next candidate.
            return {"match": False, "confidence": 0.0, "reason": f"vet error: {str(e)[:60]}"}

    # ── download + re-encode ──────────────────────────────────────────────────
    def _download_jpeg(self, url: str):
        """Download full-res image, downscale + re-encode to JPEG. Returns (bytes, w, h)."""
        try:
            r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            with Image.open(io.BytesIO(r.content)) as img:
                img = img.convert("RGB")
                img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
                out = io.BytesIO()
                img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
                return out.getvalue(), img.width, img.height
        except Exception as e:
            self._log(f"⚠️  Image download/re-encode failed: {e}")
            return None
