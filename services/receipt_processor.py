"""
Receipt processing: grocery-receipt image -> normalized line items, and
candidate disambiguation for canonical ingredient resolution.

Two responsibilities, both LLM-backed (kept in the ingestion service so all
OpenAI usage + the key live in one place; the Go backend delegates here):
  - extract_receipt(): GPT-4o vision OCR + abbreviation expansion + food/non-food
    classification + a singular, qualifier-stripped `canonical_query` per item.
  - resolve_ingredient(): given a receipt item and the candidate catalog
    ingredients the Go backend's search returned, pick the best-matching id
    (used only when the search returned >1 candidate).

The extraction prompt is the one validated in scripts/receipt_extraction_spike.py
(38% -> 90% catalog match rate on real receipts).
"""
import json
import logging

import openai

from app.config import settings

logger = logging.getLogger(__name__)

VISION_MODEL = "gpt-4o"
RESOLVE_MODEL = "gpt-4o-mini"  # picking among a supplied short list is cheap

EXTRACTION_SYSTEM_PROMPT = """You extract purchased line items from a photo of a grocery receipt for a cooking app.

Return STRICT JSON: {"items": [ ... ]}. No prose. One object per PURCHASED LINE ITEM with:
- "raw": exact text as printed (reconstruct an obvious cut-off first letter from context).
- "name": readable, plain-English product name with store/brand abbreviations expanded
  (e.g. "PBX FNCY PARM SHRD" -> "shredded parmesan", "GV WHL MLK" -> "whole milk").
- "canonical_query": the SINGULAR, base cooking-ingredient term to look up in an
  ingredient catalog. RULES:
    * singular, lowercase ("carrots" -> "carrot", "limes" -> "lime")
    * strip marketing/processing qualifiers that don't change the ingredient:
      organic, natural, fancy, family size, value, light, fat-free, reduced-fat,
      shredded, sliced, baby, large, jumbo, mixed -> drop them
      ("organic carrots" -> "carrot", "shredded parmesan" -> "parmesan",
       "fat-free light vanilla yogurt" -> "vanilla yogurt", "baby broccoli" -> "broccoli")
    * KEEP descriptors that define a distinct catalog ingredient: color of peppers
      ("red bell pepper"), the protein/base noun, style of dairy ("greek yogurt").
    * drop the brand from canonical_query.
    * for a composite/prepared item, set canonical_query to "" (it won't resolve to
      a single ingredient).
- "brand": brand if identifiable (store brand or name brand), else "".
- "quantity": the PURCHASE quantity only — a count ("3 @", "12 CT") or a weight
  ("1.14 lb"). A package SIZE like "16 OZ" is the unit size of one item, so set
  quantity 1 and unit "oz". NEVER treat a trailing standalone code/number with no
  unit (e.g. a 2-4 digit PLU like "80") as quantity — use 1.
- "unit": "count", "lb", "oz", "gallon", "liter", etc. when determinable, else "".
- "is_food": true ONLY for edible grocery food/ingredients. false for non-food
  (laundry detergent, napkins, bags), taxes, deposits, totals, payment lines.
- "is_composite": true ONLY for a PREPARED DISH or MULTI-INGREDIENT KIT that is not a
  single ingredient (e.g. "chicken tikka samosas", "caesar salad kit", "frozen lasagna").
  A single processed product is NOT composite: ketchup, peanut butter, broth, bread,
  yogurt, tomato paste are is_composite=false.
- "confidence": 0.0-1.0 in the name/canonical_query normalization.

EXCLUDE entirely: subtotals, totals, tax, "you saved", payment/change/card lines,
"items in transaction", store address/phone/metadata. Only real purchased line items.
"""

RESOLVE_SYSTEM_PROMPT = """You match a grocery-receipt item to the single best ingredient
from a candidate list taken from a cooking app's ingredient catalog.

You are given the receipt item (raw text, normalized name, brand) and a numbered list
of candidate ingredients. Choose the candidate that best represents the SAME ingredient.

Rules:
- Pick the most specific candidate that is genuinely the same ingredient.
- Reject candidates that merely share a substring but are a different food
  (e.g. for "green juice" do NOT pick "ice"; for a "berry blend" prefer a generic
  berry only if one exists, else choose none).
- If NO candidate is actually the same ingredient, return chosen_id null.

Return STRICT JSON: {"chosen_id": <id string or null>, "confidence": <0.0-1.0>}.
No prose.
"""


class ReceiptProcessor:
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    def extract_receipt(self, image_base64: str, content_type: str) -> list[dict]:
        """Run GPT-4o vision over a receipt image; return normalized line items."""
        if content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
            raise ValueError(
                f"unsupported image type {content_type} "
                "(need jpeg/png/webp/gif; HEIC must be converted client-side)"
            )

        resp = self.client.chat.completions.create(
            model=VISION_MODEL,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract the purchased line items from this receipt."},
                        {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{image_base64}"}},
                    ],
                },
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        items = data.get("items", [])
        if not isinstance(items, list):
            raise ValueError("model did not return an items list")
        return [self._normalize_item(it) for it in items]

    @staticmethod
    def _normalize_item(it: dict) -> dict:
        """Defensive field normalization so the API contract is stable."""
        return {
            "raw": str(it.get("raw", "")),
            "name": str(it.get("name", "")),
            "canonical_query": str(it.get("canonical_query", "")),
            "brand": str(it.get("brand", "")),
            "quantity": float(it.get("quantity", 1) or 1),
            "unit": str(it.get("unit", "")),
            "is_food": bool(it.get("is_food", False)),
            "is_composite": bool(it.get("is_composite", False)),
            "confidence": float(it.get("confidence", 0.0) or 0.0),
        }

    def resolve_ingredient(self, query: str, raw: str, brand: str, candidates: list[dict]) -> dict:
        """Pick the best candidate id for a receipt item. candidates: [{id, name}].

        Returns {"chosen_id": str|None, "confidence": float}. Called only when the
        Go backend's catalog search returned more than one candidate.
        """
        if not candidates:
            return {"chosen_id": None, "confidence": 0.0}

        candidate_lines = "\n".join(
            f'{i+1}. id="{c["id"]}" name="{c["name"]}"' for i, c in enumerate(candidates)
        )
        user_msg = (
            f'Receipt item: raw="{raw}", name="{query}", brand="{brand}".\n'
            f"Candidates:\n{candidate_lines}\n\n"
            "Return the chosen_id (or null)."
        )

        resp = self.client.chat.completions.create(
            model=RESOLVE_MODEL,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": RESOLVE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        chosen = data.get("chosen_id")
        # Guard against a hallucinated id not in the candidate set.
        valid_ids = {c["id"] for c in candidates}
        if chosen not in valid_ids:
            chosen = None
        return {"chosen_id": chosen, "confidence": float(data.get("confidence", 0.0) or 0.0)}
