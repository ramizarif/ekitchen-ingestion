"""
Text moderation: a reported piece of user writing -> a safety verdict for the moderator.

Sibling of image_moderator.py, and here for the same reason: all OpenAI usage + the key
live in one place, and the Go backend delegates the call.

  screen_text(): -> {"verdict": safe|unsafe|uncertain, "categories": [...], "reason": "..."}
  for one comment, cook caption, recipe tip, user-written recipe, or cookbook bio.

Unlike image screening, this runs AFTER a human reported the text, and the verdict is
ADVISORY: the Go side shows it to the moderator and never deletes on it. So the posture
differs from the image path — there, "unsafe" auto-rejects an upload, so the prompt bends
toward "safe"/"uncertain". Here an over-cautious "uncertain" just means the moderator
reads it themselves, which is what they do today anyway. The useful output is an honest
three-way split, so the obvious cases stop competing for attention with the petty ones.

WHY TWO CALLS: the free omni-moderation endpoint is excellent on the categories it knows
(hate, harassment, sexual, violence, self-harm) and catches obfuscated slurs a chat model
sometimes talks itself out of. It knows nothing about spam, scams, or someone posting a
stranger's phone number — all of which show up in reports — and it returns scores rather
than a sentence a human can act on. It also has no idea it is looking at a cooking app,
where "this chili is a war crime" is praise. So the moderation scores are gathered first
and handed to GPT-4o as evidence, and GPT-4o makes the judgement and writes the reason.
Moderation is free and ~100ms; the GPT call only happens on reported content, which is
rare. If moderation fails the GPT call still runs (degraded, not blocked); if GPT fails
the caller gets an error, which the Go side treats as "a human needs to look".
"""
import json
import logging

import openai

from app.config import settings

logger = logging.getLogger(__name__)

MODERATION_MODEL = "gpt-4o"
CLASSIFIER_MODEL = "omni-moderation-latest"

# Longer than any single field the app accepts (comments cap at 500), but a user-written
# recipe can run long, and a wall of text is a cost and latency risk on a rare path.
MAX_TEXT_CHARS = 8000

# Scores below this are noise — nearly every string scores nonzero somewhere.
SCORE_FLOOR = 0.05

MODERATION_SYSTEM_PROMPT = """You are a content-safety reviewer for eKitchen, a home-cooking app.
Users write comments on each other's cooks, captions on dishes they made, tips on recipes,
recipes of their own, and a short bio on their cookbook profile.

The text you are given WAS REPORTED BY ANOTHER USER. A report is not evidence: people report
things they merely dislike, disagree with, or find unflattering about their cooking. Decide
whether the text actually breaks the rules below.

Return STRICT JSON, no prose: {"verdict": "...", "categories": [...], "reason": "..."}.
- "verdict": one of "safe", "unsafe", "uncertain".
- "categories": list of any that apply from: "hate", "harassment", "sexual", "violence",
  "self_harm", "spam", "personal_info", "illegal". Empty list if none.
- "reason": ONE short sentence, under 25 words, naming the specific problem so a human can
  act on it without opening the app. If nothing is wrong, say so plainly.

BREAKS THE RULES ("unsafe" when clear):
- Hate speech or slurs aimed at a group, including disguised spellings.
- Harassment or bullying aimed at a person: insults directed at another user, pile-ons,
  demeaning someone's body, family, or intelligence.
- Sexual content.
- Threats of violence, or encouragement of violence or self-harm.
- Spam, scams, phishing, or advertising: promo codes, follow-for-follow, link drops,
  repeated pasted blurbs, anything selling something unrelated to the dish.
- Someone else's personal information: phone numbers, addresses, workplaces, full names
  published to identify or expose a person.
- Instructions for genuinely illegal activity.

DOES NOT BREAK THE RULES ("safe"), no matter who reported it:
- Ordinary cooking talk, questions, and enthusiasm.
- Strong opinions about food and blunt criticism of a RECIPE or a DISH, including "this is
  disgusting", "worst thing I've made", "trash". Criticism aimed at food is not harassment;
  criticism aimed at a PERSON may be.
- Mild profanity as emphasis: "damn good", "this is insane", "holy crap".
- Violent or crude language about ingredients and technique: butchering, killing the heat,
  bleeding a steak, "murdered this brisket", "a war crime against pasta".
- Culinary terms that merely look rude out of context.
- The poster's own frustration, self-deprecation, or bad day, absent self-harm.

"uncertain" is for a genuine judgement call: a borderline insult, sarcasm that could cut
either way, an unexplained link, a name that might or might not identify someone real.
Prefer "uncertain" over guessing — it routes to a human, which costs almost nothing.

The automated classifier scores below are ONE signal, not the answer. They do not know
this is a cooking app and they do not cover spam or personal information. A high score on
text that is plainly about food is a false positive; say so and mark it safe.
"""


class TextModerator:
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    def screen_text(self, text: str, context: str = "") -> dict:
        """Judge one reported piece of user writing; return an advisory verdict.

        Returns {"verdict": str, "categories": list[str], "reason": str}. Raises
        ValueError on empty text (a permanent, non-retryable error).
        """
        text = (text or "").strip()
        if not text:
            raise ValueError("text is empty")
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS]

        scores = self._classifier_scores(text)

        where = context.strip() or "user-written text in a cooking app"
        user_content = (
            f"Where this appeared: {where}\n"
            f"Automated classifier scores: {self._format_scores(scores)}\n\n"
            f"Reported text:\n\"\"\"\n{text}\n\"\"\"\n\n"
            "Return the verdict JSON."
        )

        resp = self.client.chat.completions.create(
            model=MODERATION_MODEL,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": MODERATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        return self._normalize_verdict(data)

    def _classifier_scores(self, text: str) -> dict:
        """Category scores from the free moderation endpoint, as evidence for the model.

        Best-effort: a failure here degrades the judgement rather than failing the call,
        because GPT alone still answers every category we care about.
        """
        try:
            resp = self.client.moderations.create(model=CLASSIFIER_MODEL, input=text)
            result = resp.results[0]
            raw = result.category_scores
            scores = raw if isinstance(raw, dict) else raw.model_dump()
            return {k: float(v) for k, v in scores.items() if v is not None and float(v) >= SCORE_FLOOR}
        except Exception:  # noqa: BLE001
            logger.warning("moderation classifier unavailable; judging on the model alone", exc_info=True)
            return {}

    @staticmethod
    def _format_scores(scores: dict) -> str:
        if not scores:
            return "unavailable"
        top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:5]
        return ", ".join(f"{name} {score:.2f}" for name, score in top)

    @staticmethod
    def _normalize_verdict(data: dict) -> dict:
        """Defensive normalization so the API contract is stable and always safe-by-omission.

        An unrecognized/missing verdict resolves to "uncertain" (never a silent "safe"),
        matching the image path: the fallback is always "a human decides".
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
