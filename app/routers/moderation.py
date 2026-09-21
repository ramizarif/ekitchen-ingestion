"""
Moderation endpoints.

  POST /api/v1/screen-image   image (base64)  -> safety verdict (safe|unsafe|uncertain)
  POST /api/v1/screen-text    reported text   -> safety verdict (safe|unsafe|uncertain)

Internal endpoints called by the Go backend's kitchenservice. screen-image auto-screens
user-uploaded media (cook photos, avatars, cookbook covers) BEFORE it is published;
screen-text judges a piece of writing AFTER a user reported it, so the moderator's alert
says whether it actually breaks the rules. The Go side owns the writes and the fail-safe
policy; this service only does the OpenAI calls. Mirrors the receipt router (lazy
singleton, payload in, verdict out).
"""
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.image_moderator import ImageModerator
from services.text_moderator import TextModerator

logger = logging.getLogger(__name__)
router = APIRouter()

# Lazily-constructed singletons so importing the router never requires the API key
# (e.g. during tests / schema generation); built on first real request.
_moderator: Optional[ImageModerator] = None
_text_moderator: Optional[TextModerator] = None


def _get_moderator() -> ImageModerator:
    global _moderator
    if _moderator is None:
        _moderator = ImageModerator()
    return _moderator


def _get_text_moderator() -> TextModerator:
    global _text_moderator
    if _text_moderator is None:
        _text_moderator = TextModerator()
    return _text_moderator


class ScreenImageRequest(BaseModel):
    image_base64: str = Field(..., description="Base64-encoded image")
    content_type: str = Field("image/jpeg", description="image/jpeg, image/png, image/webp, or image/gif")


class ScreenImageResponse(BaseModel):
    verdict: str = Field(..., description="safe | unsafe | uncertain")
    categories: List[str] = Field(default_factory=list)
    reason: str = ""
    processing_time_ms: int


@router.post(
    "/screen-image",
    response_model=ScreenImageResponse,
    summary="Screen a user-uploaded image for objectionable content (Apple 1.2 UGC filter)",
)
async def screen_image(request: ScreenImageRequest):
    start = time.time()
    try:
        result = _get_moderator().screen_image(request.image_base64, request.content_type)
    except ValueError as e:
        # Bad image/format — permanent, don't retry (matches the receipt path's 400).
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("image moderation failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"moderation failed: {e}")

    return ScreenImageResponse(
        verdict=result["verdict"],
        categories=result["categories"],
        reason=result["reason"],
        processing_time_ms=int((time.time() - start) * 1000),
    )


class ScreenTextRequest(BaseModel):
    text: str = Field(..., description="The reported text, as the user wrote it")
    context: str = Field(
        "",
        description='Where it appeared, e.g. "comment on a cooking post" or "recipe tip"',
    )


class ScreenTextResponse(BaseModel):
    verdict: str = Field(..., description="safe | unsafe | uncertain")
    categories: List[str] = Field(default_factory=list)
    reason: str = ""
    processing_time_ms: int


@router.post(
    "/screen-text",
    response_model=ScreenTextResponse,
    summary="Judge reported user-written text (advisory; the moderator still decides)",
)
async def screen_text(request: ScreenTextRequest):
    start = time.time()
    try:
        result = _get_text_moderator().screen_text(request.text, request.context)
    except ValueError as e:
        # Empty text — permanent, don't retry (matches the image path's 400).
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("text moderation failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"moderation failed: {e}")

    return ScreenTextResponse(
        verdict=result["verdict"],
        categories=result["categories"],
        reason=result["reason"],
        processing_time_ms=int((time.time() - start) * 1000),
    )
