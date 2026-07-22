"""
Image moderation: user-uploaded photo -> a safety verdict for the cooking app's UGC.

LLM-backed like the receipt processor, and kept here for the same reason: all OpenAI
usage + the key live in one place, and the Go backend (kitchenservice.screenMedia)
delegates the vision call here.

  screen_image(): GPT-4o vision -> {"verdict": safe|unsafe|uncertain, "categories": [...],
  "reason": "..."} for a single user-uploaded image (cook photos, avatars, cookbook covers).

Posture is deliberately CONSERVATIVE (Apple Guideline 1.2): auto-reject only clear,
unambiguous violations; send anything borderline to "uncertain" so it lands in the Go
side's manual queue rather than false-rejecting a legitimate food photo. Raw meat, red
sauces, kitchen knives in a cooking context, a glass of wine with dinner, and people in
frame (avatars/cookbook covers are supposed to have faces) are all SAFE.
"""
import json
import logging

import openai

from app.config import settings

logger = logging.getLogger(__name__)

MODERATION_MODEL = "gpt-4o"

MODERATION_SYSTEM_PROMPT = """You are a content-safety reviewer for eKitchen, a home-cooking app.
Users upload photos of food they cooked, their kitchen, a cookbook cover, or a profile avatar.

Your ONLY job is to decide whether an image is objectionable enough to block from a general
audience. Judge safety, NOT relevance or quality — an ordinary, benign image that happens not to
show food is still "safe".

Return STRICT JSON, no prose: {"verdict": "...", "categories": [...], "reason": "..."}.
- "verdict": one of "safe", "unsafe", "uncertain".
- "categories": list of any that apply from: "sexual", "nudity", "violence", "gore",
  "illegal", "drugs", "hate_symbol", "shocking". Empty list if none.
- "reason": one short factual sentence (no accusatory language).

VERDICT RULES — bias toward "safe"/"uncertain", never over-block:
- "unsafe": ONLY for a CLEAR, UNAMBIGUOUS violation — explicit sexual content or nudity,
  graphic real violence or gore, depiction of illegal activity or hard-drug use, or hate symbols.
- "uncertain": possibly problematic but not clearly a violation, OR the content is ambiguous /
  you cannot confidently tell it is benign. This routes to a human reviewer.
- "safe": clearly benign. This INCLUDES normal cooking and kitchen imagery that naive filters
  trip on: raw or bloody meat and fish, red/brown sauces, whole animals/seafood being prepped,
  kitchen knives and cleavers in use, a glass of wine or beer alongside a meal, and people's
  faces or bodies dressed normally (avatars and cookbook covers are expected to show people).

When unsure between "unsafe" and "uncertain", choose "uncertain". Only "unsafe" auto-rejects.
"""


class ImageModerator:
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    def screen_image(self, image_base64: str, content_type: str) -> dict:
        """Run GPT-4o vision over a user image; return a safety verdict.

        Returns {"verdict": str, "categories": list[str], "reason": str}. Raises
        ValueError on an unsupported image type (a permanent, non-retryable error).
        """
        if content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
            raise ValueError(
                f"unsupported image type {content_type} "
                "(need jpeg/png/webp/gif; HEIC must be converted client-side)"
            )

        resp = self.client.chat.completions.create(
            model=MODERATION_MODEL,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": MODERATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Review this user-uploaded image and return the verdict JSON."},
                        {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{image_base64}"}},
                    ],
                },
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        return self._normalize_verdict(data)

    @staticmethod
    def _normalize_verdict(data: dict) -> dict:
        """Defensive normalization so the API contract is stable and always safe-by-omission.

        An unrecognized/missing verdict resolves to "uncertain" (never a silent "safe").
        """
        verdict = str(data.get("verdict", "")).strip().lower()
        if verdict not in ("safe", "unsafe", "uncertain"):
            verdict = "uncertain"

        categories = data.get("categories", [])
        if not isinstance(categories, list):
            categories = []
        categories = [str(c) for c in categories]

        return {
            "verdict": verdict,
            "categories": categories,
            "reason": str(data.get("reason", "")),
        }
