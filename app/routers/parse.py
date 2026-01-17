"""
Recipe parsing endpoints.
"""
import time
import logging
from fastapi import APIRouter, HTTPException, status
from app.models import ParseRequest, ParseResponse, ErrorResponse, RecipeData, ErrorDetail
from parsers.website import WebsiteParser

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize parsers
website_parser = WebsiteParser(timeout=30)


@router.post("/parse", response_model=ParseResponse, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def parse_recipe(request: ParseRequest):
    """
    Parse a recipe from a URL.

    Supports:
    - **Websites** (200+ sites via recipe-scrapers) ✅
    - TikTok videos (GPT-4 Vision) - Coming soon
    - Instagram posts/reels (GPT-4 Vision) - Coming soon
    - YouTube videos (GPT-4 Vision) - Coming soon
    - Images (GPT-4 Vision) - Coming soon

    Returns:
        ParseResponse with recipe data or ErrorResponse on failure
    """
    start_time = time.time()

    # Route to appropriate parser based on source_type
    if request.source_type == "website":
        result = await website_parser.parse(str(request.url))
    else:
        # Other parsers not yet implemented
        processing_time_ms = int((time.time() - start_time) * 1000)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={
                "success": False,
                "error": {
                    "code": "NOT_IMPLEMENTED",
                    "message": f"Parser for '{request.source_type}' not yet implemented",
                    "details": "Currently only 'website' source type is supported"
                },
                "processing_time_ms": processing_time_ms
            }
        )

    # Handle parsing result
    if result.success:
        # Convert to response model
        recipe_data = RecipeData(**result.data)

        response = ParseResponse(
            success=True,
            data=recipe_data,
            processing_time_ms=int((time.time() - start_time) * 1000),
            parser_used=result.parser_name,
            confidence_score=result.confidence_score,
            warnings=result.warnings or []
        )
        
        logger.info(f"Successfully parsed recipe: {recipe_data.name} from {request.url}")
        logger.info(f"Response: {response.model_dump_json(indent=2)}")
        
        return response
    else:
        # Return error response
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Determine HTTP status code based on error type
        if result.error_code == "INVALID_URL":
            http_status = status.HTTP_400_BAD_REQUEST
        elif result.error_code in ["NOT_FOUND", "UNSUPPORTED_SITE"]:
            http_status = status.HTTP_404_NOT_FOUND
        elif result.error_code == "FORBIDDEN":
            http_status = status.HTTP_403_FORBIDDEN
        elif result.error_code == "TIMEOUT":
            http_status = status.HTTP_504_GATEWAY_TIMEOUT
        else:
            http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

        raise HTTPException(
            status_code=http_status,
            detail={
                "success": False,
                "error": {
                    "code": result.error_code,
                    "message": result.error_message,
                    "details": f"Failed to parse recipe from {request.url}"
                },
                "processing_time_ms": processing_time_ms
            }
        )


@router.get("/parsers")
async def list_parsers():
    """List available parsers and their status."""
    return {
        "parsers": [
            {
                "source_type": "website",
                "status": "available",
                "description": "Parse recipes from 200+ websites using recipe-scrapers",
                "examples": [
                    "https://www.allrecipes.com/...",
                    "https://www.foodnetwork.com/...",
                    "https://www.bonappetit.com/...",
                    "https://www.seriouseats.com/..."
                ]
            },
            {
                "source_type": "image",
                "status": "planned",
                "description": "Extract recipes from screenshots using GPT-4 Vision"
            },
            {
                "source_type": "youtube",
                "status": "planned",
                "description": "Parse recipes from YouTube videos"
            },
            {
                "source_type": "tiktok",
                "status": "planned",
                "description": "Parse recipes from TikTok videos"
            },
            {
                "source_type": "instagram",
                "status": "planned",
                "description": "Parse recipes from Instagram posts/reels"
            }
        ]
    }


@router.post("/validate")
async def validate_url(request: ParseRequest):
    """
    Quick validation of a URL without full parsing.
    Useful for checking if a URL is supported before committing to full parse.
    """
    if request.source_type == "website":
        is_valid = await website_parser.validate_url(str(request.url))

        return {
            "valid": is_valid,
            "source_type": request.source_type,
            "estimated_parse_time_seconds": 3 if is_valid else 0,
            "supported": is_valid,
            "parser": "recipe-scrapers" if is_valid else None
        }
    else:
        return {
            "valid": False,
            "source_type": request.source_type,
            "estimated_parse_time_seconds": 0,
            "supported": False,
            "error": f"Parser for '{request.source_type}' not yet implemented"
        }
