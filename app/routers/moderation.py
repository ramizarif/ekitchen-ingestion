"""
Image-moderation endpoint.

  POST /api/v1/screen-image   image (base64) -> safety verdict (safe|unsafe|uncertain)

Internal endpoint called by the Go backend's kitchenservice.screenMedia to auto-screen
user-uploaded media (cook photos, avatars, cookbook covers) before it is published.
The Go side owns the media write + the fail-safe policy; this service only does the
GPT-4o vision call. Mirrors the receipt router (lazy singleton, base64 image in).
"""
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.image_moderator import ImageModerator

logger = logging.getLogger(__name__)
router = APIRouter()

# Lazily-constructed singleton so importing the router never requires the API key
# (e.g. during tests / schema generation); built on first real request.
_moderator: Optional[ImageModerator] = None


def _get_moderator() -> ImageModerator:
    global _moderator
    if _moderator is None:
        _moderator = ImageModerator()
    return _moderator


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
