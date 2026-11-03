"""
Best-effort progress reporting for recipe imports.

The eKitchen backend creates an import row and passes its id here as
`import_id`. While we work we POST each stage (and whatever preview we know) to
`/recipe-imports/{id}/progress` so the app can show what is happening. Contract:
docs/IMPORT_PROGRESS.md in the ekitchen-receipt-prices repo.

Rules:
- Never raises, never fails or meaningfully slows the import (3s timeout).
- No import_id (older backend) -> no-op.
- Stages only move forward. A report is sent only when the stage changes or the
  preview has new keys/values.
- 409 means the import is already terminal; we stop reporting quietly.
"""
import logging
import time
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

STAGES = ("queued", "reading", "extracting", "matching", "writing", "photo", "saving")
_STAGE_RANK = {stage: rank for rank, stage in enumerate(STAGES)}

HTTP_TIMEOUT_SECONDS = 3.0
MATCHING_MIN_INTERVAL_SECONDS = 1.0

MAX_TITLE_CHARS = 140
MAX_SHORT_TEXT_CHARS = 200
MAX_THUMBNAIL_CHARS = 2048
MAX_INGREDIENTS = 40
MAX_INGREDIENT_CHARS = 120

_STRING_FIELDS = {
    "platform", "title", "creator", "site_name", "thumbnail_url", "extraction_method",
    "cuisine", "difficulty", "meal_type", "photo_source",
}
_INT_FIELDS = {
    "ingredient_count", "step_count", "servings", "total_minutes",
    "ingredients_done", "matched_count", "new_count",
}

# Parser extraction methods -> the contract's extraction_method values.
_EXTRACTION_METHODS = {
    "description_only": "description",
    "audio_only": "audio",
    "hybrid": "video",
    "vision_only": "video",
}


def contract_extraction_method(parser_method: Optional[str]) -> Optional[str]:
    """Map a VideoParser extraction_method to the contract's name, or None."""
    return _EXTRACTION_METHODS.get(parser_method or "")


def clean_preview(preview: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only contract fields, drop empty values, and clamp to the contract limits."""
    cleaned: Dict[str, Any] = {}
    for key, value in preview.items():
        if value is None:
            continue

        if key in _STRING_FIELDS:
            if not isinstance(value, str):
                continue
            text = value.strip()
            if not text:
                continue
            if key == "thumbnail_url":
                if not text.startswith("https://") or len(text) > MAX_THUMBNAIL_CHARS:
                    continue
                cleaned[key] = text
            elif key == "title":
                cleaned[key] = text[:MAX_TITLE_CHARS]
            else:
                cleaned[key] = text[:MAX_SHORT_TEXT_CHARS]

        elif key in _INT_FIELDS:
            if isinstance(value, bool):
                continue
            try:
                number = int(value)
            except (TypeError, ValueError):
                continue
            if number >= 0:
                cleaned[key] = number

        elif key == "ingredients":
            if not isinstance(value, (list, tuple)):
                continue
            items = []
            for item in value:
                if not isinstance(item, str) or not item.strip():
                    continue
                items.append(item.strip()[:MAX_INGREDIENT_CHARS])
                if len(items) == MAX_INGREDIENTS:
                    break
            cleaned[key] = items

        # Unknown keys are dropped; the backend would discard them anyway.
    return cleaned


AuthProvider = Callable[[], Tuple[str, str]]  # () -> (base_url, bearer_token)


class ProgressReporter:
    """Reports one import's stages to the eKitchen backend. Best effort."""

    def __init__(
        self,
        import_id: Optional[str],
        auth_provider: Optional[AuthProvider] = None,
        *,
        post: Optional[Callable[..., Any]] = None,
        clock: Callable[[], float] = time.monotonic,
        min_interval: float = MATCHING_MIN_INTERVAL_SECONDS,
    ):
        self.import_id = import_id or None
        self._auth_provider = auth_provider
        self._post = post  # None: requests.post, looked up at call time
        self._clock = clock
        self._min_interval = min_interval
        self._stage: Optional[str] = None
        self._sent: Dict[str, Any] = {}  # preview values the backend has accepted
        self._last_sent_at: Optional[float] = None
        self._closed = False  # set on 409: the import is already terminal

    @property
    def enabled(self) -> bool:
        return self.import_id is not None and not self._closed

    def report(self, stage: str, *, force: bool = False, **preview: Any) -> None:
        """Report `stage` with optional preview fields. Never raises.

        Same-stage updates are throttled to one per `min_interval` unless `force`
        is set, so call sites can report every iteration of a loop. A throttled
        update is not lost: the next send diffs against what was actually sent.
        """
        if not self.enabled:
            return
        try:
            self._report(stage, force, preview)
        except Exception as e:  # best effort: a progress bug must never fail an import
            logger.warning(f"Import progress report failed (stage={stage}): {e}")

    def _report(self, stage: str, force: bool, preview: Dict[str, Any]) -> None:
        rank = _STAGE_RANK.get(stage)
        if rank is None:
            logger.warning(f"Import progress: unknown stage '{stage}' ignored")
            return

        current_rank = _STAGE_RANK.get(self._stage) if self._stage else None
        if current_rank is not None and rank < current_rank:
            return  # stages never move backwards

        new_stage = current_rank is None or rank > current_rank
        cleaned = clean_preview(preview)
        changed = {k: v for k, v in cleaned.items() if self._sent.get(k) != v}
        if not new_stage and not changed:
            return

        now = self._clock()
        if (not new_stage and not force and self._last_sent_at is not None
                and now - self._last_sent_at < self._min_interval):
            return

        body: Dict[str, Any] = {"stage": stage}
        if changed:
            body["preview"] = changed

        base_url, token = self._auth_provider()
        url = f"{base_url.rstrip('/')}/recipe-imports/{quote(self.import_id, safe='')}/progress"
        post = self._post or requests.post
        response = post(
            url,
            json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=HTTP_TIMEOUT_SECONDS,
        )

        status = response.status_code
        if status == 409:
            logger.info(f"Import {self.import_id} is already terminal; stopping progress reports")
            self._closed = True
            return
        if status >= 300:
            logger.warning(f"Import progress report rejected (stage={stage}): HTTP {status}")
            return

        self._stage = stage
        self._sent.update(changed)
        self._last_sent_at = now


# Shared no-op reporter for callers that were not given one.
NO_PROGRESS = ProgressReporter(None)
