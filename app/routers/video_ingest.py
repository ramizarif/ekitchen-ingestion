"""
Video recipe ingestion endpoint - TikTok, Instagram Reels, YouTube Shorts.
Uses audio-first approach: yt-dlp → Whisper → GPT-4 → DirectRecipeProcessor.
"""
import os
import sys
import time
import logging
import asyncio
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from local.env
env_path = os.path.join(os.path.dirname(__file__), '..', '..', 'local.env')
load_dotenv(env_path)

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from parsers.video import VideoParser
from services.recipe_processor import DirectRecipeProcessor

logger = logging.getLogger(__name__)

router = APIRouter()


class VideoIngestRequest(BaseModel):
    """Request model for /ingest/video endpoint."""
    url: str = Field(..., description="Video URL (TikTok, Instagram Reel, YouTube Short)")
    generate_image: bool = Field(True, description="Whether to generate DALL-E image")
    save_to_database: bool = Field(True, description="Whether to save to eKitchen database")
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.tiktok.com/@cookingwithshereen/video/7234567890123456789",
                "generate_image": True,
                "save_to_database": True
            }
        }


class VideoParseResult(BaseModel):
    """Parsed recipe data from video (before DB save)."""
    name: str
    description: Optional[str] = None
    ingredients: List[str]
    steps: List[str]
    servings: Optional[int] = None
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    total_time_minutes: Optional[int] = None
    tips: List[str] = []
    video_url: str
    platform: str
    transcript_preview: Optional[str] = None


class VideoIngestResponse(BaseModel):
    """Response model for successful video ingestion."""
    success: bool = True
    recipe_id: Optional[str] = Field(None, description="ID of created recipe (if saved to DB)")
    recipe_name: str = Field(..., description="Name of the recipe")
    ingredients_count: int = Field(..., description="Number of ingredients extracted")
    steps_count: int = Field(..., description="Number of steps extracted")
    image_generated: bool = Field(False, description="Whether image was generated")
    confidence_score: float = Field(..., description="Extraction confidence (0-1)")
    warnings: List[str] = Field(default_factory=list, description="Extraction warnings")
    processing_time_seconds: float = Field(..., description="Total processing time")
    parsed_recipe: Optional[VideoParseResult] = Field(None, description="Parsed recipe data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "recipe_id": "550e8400-e29b-41d4-a716-446655440000",
                "recipe_name": "Creamy Garlic Pasta",
                "ingredients_count": 8,
                "steps_count": 5,
                "image_generated": True,
                "confidence_score": 0.85,
                "warnings": ["Cooking time not specified"],
                "processing_time_seconds": 35.2
            }
        }


class VideoIngestErrorResponse(BaseModel):
    """Response model for video ingestion errors."""
    success: bool = False
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Human-readable error message")
    processing_time_seconds: float = Field(..., description="Processing time before failure")


# Lazy initialization
_video_parser = None
_recipe_processor = None


def get_video_parser() -> VideoParser:
    """Lazy initialization of VideoParser."""
    global _video_parser
    if _video_parser is None:
        _video_parser = VideoParser(timeout=120)
        logger.info("VideoParser initialized")
    return _video_parser


def get_recipe_processor():
    """Lazy initialization of DirectRecipeProcessor."""
    global _recipe_processor
    if _recipe_processor is None:
        try:
            _recipe_processor = DirectRecipeProcessor(log_to_file=True)
            logger.info("DirectRecipeProcessor initialized for video ingestion")
        except Exception as e:
            logger.error(f"Failed to initialize DirectRecipeProcessor: {e}")
            raise
    return _recipe_processor


@router.post(
    "/ingest/video",
    response_model=VideoIngestResponse,
    responses={
        400: {"model": VideoIngestErrorResponse},
        500: {"model": VideoIngestErrorResponse}
    },
    summary="Ingest recipe from video URL",
    description="""
    Extract and ingest recipes from video content using audio-first approach.
    
    **Supported Platforms:**
    - TikTok (tiktok.com, vm.tiktok.com)
    - Instagram Reels (instagram.com/reel/, instagram.com/reels/)
    - YouTube Shorts (youtube.com/shorts/)
    
    **Pipeline:**
    1. Download video with yt-dlp
    2. Extract audio with ffmpeg
    3. Transcribe with OpenAI Whisper
    4. Parse transcript with GPT-4 to extract structured recipe
    5. (Optional) Create ingredients and recipe in eKitchen database
    6. (Optional) Generate DALL-E hero image
    
    **Note:** Video processing takes longer than website scraping (30-60 seconds typical).
    """
)
async def ingest_video_recipe(request: VideoIngestRequest):
    """
    Ingest a recipe from a video URL.
    
    This endpoint handles TikTok, Instagram Reels, and YouTube Shorts.
    It uses an audio-first approach for reliable recipe extraction.
    """
    start_time = time.time()
    url = request.url
    
    logger.info(f"Starting video ingestion for URL: {url}")
    
    try:
        parser = get_video_parser()
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
    
    # Validate URL first
    if not await parser.validate_url(url):
        processing_time = time.time() - start_time
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error_code": "UNSUPPORTED_URL",
                "error_message": "URL must be a TikTok, Instagram Reel, or YouTube Short",
                "processing_time_seconds": processing_time
            }
        )
    
    try:
        # Parse video to extract recipe
        parse_result = await parser.parse(url)
        
        if not parse_result.success:
            processing_time = time.time() - start_time
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error_code": parse_result.error_code or "PARSE_FAILED",
                    "error_message": parse_result.error_message or "Failed to extract recipe from video",
                    "processing_time_seconds": processing_time
                }
            )
        
        recipe_data = parse_result.data
        recipe_name = recipe_data.get('name', 'Video Recipe')
        ingredients = recipe_data.get('ingredients', [])
        steps = recipe_data.get('steps', [])
        
        logger.info(f"Parsed video recipe: {recipe_name} ({len(ingredients)} ingredients, {len(steps)} steps)")
        
        # Build parsed recipe result
        parsed_recipe = VideoParseResult(
            name=recipe_name,
            description=recipe_data.get('description'),
            ingredients=ingredients,
            steps=steps,
            servings=recipe_data.get('servings'),
            prep_time_minutes=recipe_data.get('prep_time_minutes'),
            cook_time_minutes=recipe_data.get('cook_time_minutes'),
            total_time_minutes=recipe_data.get('total_time_minutes'),
            tips=recipe_data.get('tips', []),
            video_url=url,
            platform=recipe_data.get('source_metadata', {}).get('host', 'unknown'),
            transcript_preview=recipe_data.get('source_metadata', {}).get('transcript', '')[:500]
        )
        
        recipe_id = None
        image_generated = False
        
        # Save to database if requested
        if request.save_to_database and ingredients:
            try:
                processor = get_recipe_processor()
                
                logger.info("Saving to database via DirectRecipeProcessor.process_parsed_recipe...")
                
                # Determine image save directory
                save_images_dir = None
                if request.generate_image:
                    save_images_dir = os.path.join(
                        os.path.dirname(__file__), '..', '..',
                        'data', 'generated-recipe-images', 'single-recipes'
                    )
                
                # Use process_parsed_recipe which accepts pre-parsed data
                # (skips the URL scraping phase that would fail for video URLs)
                result = processor.process_parsed_recipe(
                    parsed_recipe=recipe_data,  # Pass the video-parsed recipe directly
                    save_images_dir=save_images_dir,
                    use_enhanced_ingredients=True
                )
                
                if result.success:
                    recipe_id = result.recipe_id
                    image_generated = result.image_generated
                    logger.info(f"Recipe saved to database: {recipe_id}")
                else:
                    logger.warning(f"Database save failed: {result.error_message}")
                    # Continue anyway - we still have the parsed data
                    
            except Exception as e:
                logger.error(f"Failed to save to database: {e}")
                # Continue - return parsed data even if DB save failed
        
        processing_time = time.time() - start_time
        
        return VideoIngestResponse(
            success=True,
            recipe_id=recipe_id,
            recipe_name=recipe_name,
            ingredients_count=len(ingredients),
            steps_count=len(steps),
            image_generated=image_generated,
            confidence_score=parse_result.confidence_score or 0.5,
            warnings=parse_result.warnings or [],
            processing_time_seconds=processing_time,
            parsed_recipe=parsed_recipe if not request.save_to_database else None
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


@router.get(
    "/ingest/video/supported-platforms",
    summary="Get supported video platforms",
    description="Returns list of supported video platforms and URL patterns."
)
async def get_supported_platforms():
    """Return list of supported video platforms."""
    return {
        "platforms": [
            {
                "name": "TikTok",
                "patterns": [
                    "tiktok.com/@username/video/...",
                    "vm.tiktok.com/..."
                ],
                "example": "https://www.tiktok.com/@cookingwithshereen/video/7234567890123456789"
            },
            {
                "name": "Instagram",
                "patterns": [
                    "instagram.com/reel/...",
                    "instagram.com/reels/..."
                ],
                "example": "https://www.instagram.com/reel/ABC123xyz/"
            },
            {
                "name": "YouTube",
                "patterns": [
                    "youtube.com/shorts/...",
                    "youtu.be/..."
                ],
                "example": "https://www.youtube.com/shorts/AbCdEfG123"
            }
        ]
    }
