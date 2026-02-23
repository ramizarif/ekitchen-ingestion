"""
Unified recipe ingestion endpoint - automatically routes to video or website parser.
"""
import os
import sys
import re
import time
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, HttpUrl, Field
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '..', '..', 'local.env')
load_dotenv(env_path)

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from parsers.video import VideoParser
from services.recipe_processor import DirectRecipeProcessor
from app.routers.analytics import record_extraction_cost

logger = logging.getLogger(__name__)

router = APIRouter()


# Video platform URL patterns
VIDEO_PATTERNS = {
    'tiktok': [
        r'tiktok\.com/@[\w.]+/video/\d+',
        r'tiktok\.com/t/[\w]+',
        r'vm\.tiktok\.com/[\w]+',
    ],
    'instagram': [
        r'instagram\.com/reel/[\w-]+',
        r'instagram\.com/reels/[\w-]+',
        r'instagram\.com/p/[\w-]+',
    ],
    'youtube': [
        r'youtube\.com/shorts/[\w-]+',
        r'youtu\.be/[\w-]+',
    ]
}


def detect_url_type(url: str) -> tuple[str, Optional[str]]:
    """
    Detect if URL is a video platform or website.
    
    Returns:
        tuple: (url_type, platform) where url_type is 'video' or 'website'
    """
    url_lower = url.lower()
    
    for platform, patterns in VIDEO_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url_lower):
                return ('video', platform)
    
    return ('website', None)


class IngestRequest(BaseModel):
    """Request model for /ingest endpoint."""
    url: HttpUrl = Field(..., description="Recipe URL to ingest (website or video)")
    generate_image: bool = Field(True, description="Whether to generate DALL-E image")
    save_images_dir: Optional[str] = Field(None, description="Directory to save images (optional)")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/",
                "generate_image": True
            }
        }


class IngestResponse(BaseModel):
    """Response model for successful ingestion."""
    success: bool = True
    recipe_id: str = Field(..., description="ID of created global recipe")
    recipe_name: str = Field(..., description="Name of the recipe")
    ingredients_processed: int = Field(..., description="Number of ingredients processed")
    image_generated: bool = Field(False, description="Whether image was generated")
    processing_time_seconds: float = Field(..., description="Total processing time")
    source_type: str = Field("website", description="Source type: 'website' or 'video'")
    analytics: Optional[Dict[str, Any]] = Field(
        None,
        description="Analytics metadata for ingestion pipeline (costs, extraction methods, performance)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "recipe_id": "550e8400-e29b-41d4-a716-446655440000",
                "recipe_name": "Best Chocolate Chip Cookies",
                "ingredients_processed": 12,
                "image_generated": True,
                "processing_time_seconds": 45.2,
                "source_type": "website",
                "analytics": {
                    "url": "https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/",
                    "platform": "allrecipes",
                    "source_type": "website",
                    "processing_time_ms": 45200,
                    "cost_breakdown": {
                        "gpt4_text": 0.002,
                        "spoonacular_api": 0.001,
                        "total": 0.003
                    }
                }
            }
        }


class IngestErrorResponse(BaseModel):
    """Response model for ingestion errors."""
    success: bool = False
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Human-readable error message")
    processing_time_seconds: float = Field(..., description="Processing time before failure")


# Lazy initialization
_processor = None
_video_parser = None


def get_processor():
    """Lazy initialization of DirectRecipeProcessor."""
    global _processor
    if _processor is None:
        try:
            _processor = DirectRecipeProcessor(log_to_file=True)
            logger.info("DirectRecipeProcessor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize DirectRecipeProcessor: {e}")
            raise
    return _processor


def get_video_parser() -> VideoParser:
    """Lazy initialization of VideoParser."""
    global _video_parser
    if _video_parser is None:
        _video_parser = VideoParser(timeout=120)
        logger.info("VideoParser initialized")
    return _video_parser


@router.post(
    "/ingest",
    response_model=IngestResponse,
    responses={
        400: {"model": IngestErrorResponse},
        500: {"model": IngestErrorResponse},
        503: {"model": IngestErrorResponse}
    },
    summary="Ingest a recipe from any URL",
    description="""
    Unified recipe ingestion endpoint that automatically detects URL type and routes accordingly.
    
    **Supported Sources:**
    - **Websites** (200+ recipe sites): AllRecipes, FoodNetwork, BonAppetit, etc.
    - **TikTok**: tiktok.com/@user/video/..., vm.tiktok.com/...
    - **Instagram**: instagram.com/reel/..., instagram.com/reels/...
    - **YouTube Shorts**: youtube.com/shorts/...
    
    **Pipeline for Websites:**
    1. Scrape recipe using recipe-scrapers
    2. AI ingredient parsing + Spoonacular enrichment
    3. Create recipe in eKitchen
    
    **Pipeline for Videos:**
    1. Download audio with yt-dlp (audio-only, fast)
    2. Transcribe with Whisper API
    3. Extract recipe with GPT-4
    4. AI ingredient parsing + Spoonacular enrichment
    5. Create recipe in eKitchen
    """
)
async def ingest_recipe(request: IngestRequest):
    """
    Ingest a recipe from any URL - automatically routes to appropriate parser.
    """
    start_time = time.time()
    url = str(request.url)
    
    # Detect URL type
    url_type, platform = detect_url_type(url)
    logger.info(f"Starting ingestion for URL: {url} (type: {url_type}, platform: {platform})")
    
    if url_type == 'video':
        return await _ingest_video(url, platform, request, start_time)
    else:
        return await _ingest_website(url, request, start_time)


async def _ingest_video(url: str, platform: str, request: IngestRequest, start_time: float):
    """Handle video URL ingestion (TikTok, Instagram, YouTube)."""
    
    try:
        video_parser = get_video_parser()
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"VideoParser initialization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "success": False,
                "error_code": "PARSER_UNAVAILABLE",
                "error_message": f"Video parser not available: {str(e)}",
                "processing_time_seconds": processing_time
            }
        )
    
    try:
        # Step 1: Parse video (download audio → Whisper → GPT-4)
        logger.info(f"Parsing {platform} video...")
        parse_result = await video_parser.parse(url)
        
        if not parse_result.success:
            processing_time = time.time() - start_time
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error_code": parse_result.error_code or "VIDEO_PARSE_FAILED",
                    "error_message": parse_result.error_message or "Failed to extract recipe from video",
                    "processing_time_seconds": processing_time
                }
            )
        
        recipe_data = parse_result.data
        logger.info(f"Parsed video recipe: {recipe_data.get('name')} ({len(recipe_data.get('ingredients', []))} ingredients)")

        # Record cost data for analytics (Issue #39)
        if parse_result.cost_breakdown:
            try:
                record_extraction_cost({
                    "url": url,
                    "platform": platform,
                    "extraction_method": parse_result.extraction_method,
                    "cost_breakdown": parse_result.cost_breakdown,
                    "frames_used": parse_result.frames_used or 0,
                    "audio_duration_seconds": parse_result.audio_duration_seconds or 0,
                    "processing_time_ms": parse_result.processing_time_ms or 0,
                    "success": True
                })
            except Exception as e:
                logger.warning(f"Failed to record cost data: {e}")

        # Step 2: Process through DirectRecipeProcessor
        processor = get_processor()
        
        save_images_dir = request.save_images_dir
        if request.generate_image and not save_images_dir:
            save_images_dir = os.path.join(
                os.path.dirname(__file__), '..', '..',
                'data', 'generated-recipe-images', 'single-recipes'
            )
        
        # Use process_parsed_recipe which accepts pre-parsed data
        result = processor.process_parsed_recipe(
            parsed_recipe=recipe_data,
            save_images_dir=save_images_dir if request.generate_image else None,
            use_enhanced_ingredients=True
        )
        
        processing_time = time.time() - start_time
        
        if result.success:
            logger.info(f"Successfully ingested video recipe: {result.recipe_name} (ID: {result.recipe_id})")

            # Build analytics metadata for eKitchen backend to store
            analytics = {
                "url": url,
                "source_type": "video",
                "platform": platform,
                "extraction_method": parse_result.extraction_method,
                "frames_used": parse_result.frames_used or 0,
                "audio_duration_seconds": parse_result.audio_duration_seconds,
                "video_size_mb": parse_result.video_size_mb,
                "processing_time_ms": parse_result.processing_time_ms,
                "transcript_tokens": parse_result.transcript_tokens,
                "output_tokens": parse_result.output_tokens,
                "confidence_score": parse_result.confidence_score,
                "fallback_reason": parse_result.fallback_reason,
                "cost_breakdown": parse_result.cost_breakdown
            }

            return IngestResponse(
                success=True,
                recipe_id=result.recipe_id,
                recipe_name=result.recipe_name or "Unknown",
                ingredients_processed=result.ingredients_processed,
                image_generated=result.image_generated,
                processing_time_seconds=processing_time,
                source_type="video",
                analytics=analytics
            )
        else:
            logger.error(f"Video ingestion failed: {result.error_message}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "error_code": "INGESTION_FAILED",
                    "error_message": result.error_message or "Unknown error during video ingestion",
                    "processing_time_seconds": processing_time
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Unexpected error during video ingestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_code": "UNEXPECTED_ERROR",
                "error_message": str(e),
                "processing_time_seconds": processing_time
            }
        )


async def _ingest_website(url: str, request: IngestRequest, start_time: float):
    """Handle website URL ingestion (recipe-scrapers)."""
    
    try:
        processor = get_processor()
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Processor initialization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "success": False,
                "error_code": "PROCESSOR_UNAVAILABLE",
                "error_message": f"Recipe processor not available: {str(e)}",
                "processing_time_seconds": processing_time
            }
        )
    
    try:
        save_images_dir = request.save_images_dir
        if request.generate_image and not save_images_dir:
            save_images_dir = os.path.join(
                os.path.dirname(__file__), '..', '..',
                'data', 'generated-recipe-images', 'single-recipes'
            )
        
        # Run the autonomous processing pipeline for websites
        result = processor.process_recipe_autonomous(
            recipe_url=url,
            save_images_dir=save_images_dir if request.generate_image else None,
            use_enhanced_ingredients=True,
            allow_ingredient_skipping=False
        )
        
        processing_time = time.time() - start_time
        
        if result.success:
            logger.info(f"Successfully ingested website recipe: {result.recipe_name} (ID: {result.recipe_id})")

            # Extract platform from URL (e.g., "allrecipes.com" → "allrecipes")
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.replace('www.', '')
            platform_name = domain.split('.')[0] if domain else 'unknown'

            # Build analytics metadata for eKitchen backend to store
            # Note: Website ingestion doesn't use video-specific fields (extraction_method, frames_used, etc.)
            analytics = {
                "url": url,
                "source_type": "website",
                "platform": platform_name,
                "extraction_method": None,  # NULL for websites
                "frames_used": 0,
                "audio_duration_seconds": None,
                "video_size_mb": None,
                "processing_time_ms": int(processing_time * 1000),
                "transcript_tokens": 0,  # Could estimate from scraped text if needed
                "output_tokens": 0,  # Could track GPT-4 usage for ingredient parsing if needed
                "confidence_score": None,  # Could add recipe-scrapers confidence if available
                "fallback_reason": None,
                "cost_breakdown": {
                    # Websites don't have Whisper/Vision costs, mainly Spoonacular API + GPT-4 for ingredient parsing
                    "spoonacular_api": 0.0,  # Could track actual Spoonacular API costs
                    "gpt4_text": 0.0,  # Could track GPT-4 costs for ingredient standardization
                    "total": 0.0
                }
            }

            return IngestResponse(
                success=True,
                recipe_id=result.recipe_id,
                recipe_name=result.recipe_name or "Unknown",
                ingredients_processed=result.ingredients_processed,
                image_generated=result.image_generated,
                processing_time_seconds=processing_time,
                source_type="website",
                analytics=analytics
            )
        else:
            logger.error(f"Website ingestion failed: {result.error_message}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "error_code": "INGESTION_FAILED",
                    "error_message": result.error_message or "Unknown error during ingestion",
                    "processing_time_seconds": processing_time
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Unexpected error during website ingestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_code": "UNEXPECTED_ERROR",
                "error_message": str(e),
                "processing_time_seconds": processing_time
            }
        )


@router.get(
    "/ingest/supported-sources",
    summary="Get supported recipe sources",
    description="Returns list of supported websites and video platforms."
)
async def get_supported_sources():
    """Return list of supported recipe sources."""
    return {
        "websites": {
            "description": "200+ recipe websites supported via recipe-scrapers",
            "examples": [
                "allrecipes.com",
                "foodnetwork.com",
                "bonappetit.com",
                "seriouseats.com",
                "budgetbytes.com",
                "delish.com"
            ]
        },
        "video_platforms": [
            {
                "name": "TikTok",
                "patterns": ["tiktok.com/@user/video/...", "vm.tiktok.com/..."],
                "example": "https://www.tiktok.com/@cookingwithshereen/video/7234567890123456789"
            },
            {
                "name": "Instagram",
                "patterns": ["instagram.com/reel/...", "instagram.com/reels/..."],
                "example": "https://www.instagram.com/reel/ABC123xyz/"
            },
            {
                "name": "YouTube Shorts",
                "patterns": ["youtube.com/shorts/..."],
                "example": "https://www.youtube.com/shorts/AbCdEfG123"
            }
        ]
    }
