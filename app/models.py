"""
Pydantic models for request/response validation.
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, HttpUrl, Field


class ParseRequest(BaseModel):
    """Request model for /parse endpoint."""

    url: HttpUrl = Field(..., description="URL to parse (website, video, or image)")
    source_type: Literal["website", "tiktok", "instagram", "youtube", "image"] = Field(
        ...,
        description="Type of source to parse"
    )
    request_id: Optional[str] = Field(None, description="Client-provided request ID for tracking")
    timeout_seconds: Optional[int] = Field(None, description="Override default timeout")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.allrecipes.com/recipe/12345/chocolate-cake/",
                "source_type": "website",
                "request_id": "req_123abc",
                "timeout_seconds": 30
            }
        }


class RecipeData(BaseModel):
    """Structured recipe data."""

    name: str = Field(..., description="Recipe title")
    description: Optional[str] = Field(None, description="Recipe description")
    ingredients: List[str] = Field(..., description="List of ingredient strings")
    steps: List[str] = Field(..., description="Cooking instructions as ordered steps")
    servings: Optional[int] = Field(None, description="Number of servings")
    prep_time_minutes: Optional[int] = Field(None, description="Preparation time in minutes")
    cook_time_minutes: Optional[int] = Field(None, description="Cooking time in minutes")
    total_time_minutes: Optional[int] = Field(None, description="Total time in minutes")
    image_url: Optional[str] = Field(None, description="URL to recipe image")
    video_url: Optional[str] = Field(None, description="URL to recipe video")
    source_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata from source")


class ParseResponse(BaseModel):
    """Response model for successful parse."""

    success: bool = True
    data: RecipeData
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    parser_used: str = Field(..., description="Parser that was used (e.g., 'recipe-scrapers', 'gpt-4-vision')")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Quality/confidence score")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal issues during parsing")


class ErrorDetail(BaseModel):
    """Error detail information."""

    code: str = Field(..., description="Error code (e.g., 'PARSING_FAILED', 'INVALID_URL')")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[str] = Field(None, description="Additional error context")


class ErrorResponse(BaseModel):
    """Response model for errors."""

    success: bool = False
    error: ErrorDetail
    processing_time_ms: Optional[int] = None
