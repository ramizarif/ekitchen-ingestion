"""
Receipt scanning endpoints.

  POST /api/v1/scan-receipt      image (base64) -> normalized line items with prices,
                                 plus the store, date and totals, and a price check
  POST /api/v1/resolve-ingredient receipt item + candidate ids -> chosen id

Both are internal endpoints called by the Go backend's receiptservice (the Go
side owns the kitchen write; this service only does the LLM work).
"""
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.receipt_processor import ReceiptProcessor

logger = logging.getLogger(__name__)
router = APIRouter()

# Lazily-constructed singleton so importing the router never requires the API key
# (e.g. during tests / schema generation); built on first real request.
_processor: Optional[ReceiptProcessor] = None


def _get_processor() -> ReceiptProcessor:
    global _processor
    if _processor is None:
        _processor = ReceiptProcessor()
    return _processor


# ---- /scan-receipt ----

class ScanReceiptRequest(BaseModel):
    image_base64: str = Field(..., description="Base64-encoded receipt image")
    content_type: str = Field("image/jpeg", description="image/jpeg, image/png, or image/webp")


class ExtractedItem(BaseModel):
    raw: str
    name: str
    canonical_query: str
    brand: str = ""
    quantity: float = 1
    unit: str = ""
    is_food: bool = False
    is_composite: bool = False
    confidence: float = 0.0
    line_total: Optional[float] = None
    unit_price: Optional[float] = None
    discount: float = 0.0


class ReceiptInfo(BaseModel):
    store_name: str = ""
    store_chain: str = ""
    store_zip: str = ""
    purchased_on: str = ""
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None


class PriceCheck(BaseModel):
    status: str = "unverified"  # matched | partial | mismatch | unverified
    items_sum: float = 0.0
    expected: Optional[float] = None
    missing_prices: int = 0


class ScanReceiptResponse(BaseModel):
    success: bool = True
    items: List[ExtractedItem]
    item_count: int
    receipt: ReceiptInfo
    price_check: PriceCheck
    processing_time_ms: int


@router.post(
    "/scan-receipt",
    response_model=ScanReceiptResponse,
    summary="Extract normalized line items from a grocery-receipt image",
)
async def scan_receipt(request: ScanReceiptRequest):
    start = time.time()
    try:
        result = _get_processor().extract_receipt(request.image_base64, request.content_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("receipt extraction failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"extraction failed: {e}")

    return ScanReceiptResponse(
        success=True,
        items=result["items"],
        item_count=len(result["items"]),
        receipt=result["receipt"],
        price_check=result["price_check"],
        processing_time_ms=int((time.time() - start) * 1000),
    )


# ---- /resolve-ingredient ----

class Candidate(BaseModel):
    id: str
    name: str


class ResolveIngredientRequest(BaseModel):
    query: str = Field(..., description="canonical_query for the receipt item")
    raw: str = Field("", description="raw receipt text (context)")
    brand: str = Field("", description="brand if any (context)")
    candidates: List[Candidate] = Field(..., description="catalog candidates from the Go search")


class ResolveIngredientResponse(BaseModel):
    chosen_id: Optional[str] = None
    confidence: float = 0.0


@router.post(
    "/resolve-ingredient",
    response_model=ResolveIngredientResponse,
    summary="Pick the best catalog ingredient id for a receipt item from candidates",
)
async def resolve_ingredient(request: ResolveIngredientRequest):
    try:
        result = _get_processor().resolve_ingredient(
            query=request.query,
            raw=request.raw,
            brand=request.brand,
            candidates=[c.model_dump() for c in request.candidates],
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("ingredient resolution failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"resolution failed: {e}")

    return ResolveIngredientResponse(**result)
