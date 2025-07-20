"""Data models for Recipe Discovery MCP Server"""

from pydantic import BaseModel, Field, validator, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from urllib.parse import urlparse


class ScrapingStatus(str, Enum):
    """Enumeration of possible scraping status values"""
    SUCCESS = "success"
    FAILED = "failed"  
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    PARSING_ERROR = "parsing_error"
    NETWORK_ERROR = "network_error"
    INVALID_URL = "invalid_url"


class RecipeData(BaseModel):
    """Enhanced recipe data structure with comprehensive scraping metadata
    
    Matches recipe-scrapers library output format and provides enriched
    structure for downstream processing by eKitchen Database MCP.
    """
    # Required fields
    url: str = Field(..., description="Source URL of the recipe")
    
    # Recipe Content (from recipe-scrapers)
    title: Optional[str] = Field(None, description="Recipe title")
    ingredients: List[str] = Field(default_factory=list, description="List of ingredient strings")
    instructions: str = Field("", description="Recipe instructions as text")
    total_time: Optional[int] = Field(None, description="Total cooking time in minutes")
    prep_time: Optional[int] = Field(None, description="Preparation time in minutes")
    cook_time: Optional[int] = Field(None, description="Cooking time in minutes")
    yields: Optional[str] = Field(None, description="Recipe yield (e.g., '4 servings')")
    image_url: Optional[str] = Field(None, description="URL of recipe image")
    
    # Extended recipe fields
    description: Optional[str] = Field(None, description="Recipe description")
    cuisine: Optional[str] = Field(None, description="Cuisine type")
    category: Optional[str] = Field(None, description="Recipe category")
    author: Optional[str] = Field(None, description="Recipe author")
    
    # Nutritional info (if available from source)
    calories: Optional[int] = Field(None, description="Calories per serving")
    protein: Optional[str] = Field(None, description="Protein content")
    carbs: Optional[str] = Field(None, description="Carbohydrate content")
    fat: Optional[str] = Field(None, description="Fat content")
    
    # Scraping Metadata (Issue #6 enhancement)
    scraped_at: datetime = Field(default_factory=datetime.now, description="When recipe was scraped")
    status: ScrapingStatus = Field(ScrapingStatus.SUCCESS, description="Scraping status")
    success: bool = Field(True, description="Whether scraping was successful")
    error: Optional[str] = Field(None, description="Error message if scraping failed")
    retry_count: int = Field(0, description="Number of retry attempts made")
    response_time: Optional[float] = Field(None, description="Response time in seconds")
    
    # Site Metadata
    site_domain: Optional[str] = Field(None, description="Domain of the source website")
    recipe_schema_type: Optional[str] = Field(None, description="Type of structured data found (JSON-LD, microdata, etc.)")
    
    # Processing hints for downstream systems
    ingredient_count: int = Field(0, description="Number of ingredients")
    instruction_length: int = Field(0, description="Length of instructions in characters")
    has_image: bool = Field(False, description="Whether recipe has an image")
    has_timing: bool = Field(False, description="Whether recipe has timing information")
    
    @validator('site_domain', pre=True, always=True)
    def extract_domain(cls, v, values):
        """Automatically extract domain from URL"""
        if v is None and 'url' in values:
            try:
                parsed = urlparse(values['url'])
                return parsed.netloc
            except Exception:
                pass
        return v
    
    @validator('ingredient_count', pre=True, always=True)
    def calculate_ingredient_count(cls, v, values):
        """Calculate ingredient count from ingredients list"""
        if 'ingredients' in values:
            return len(values['ingredients'])
        return v
    
    @validator('instruction_length', pre=True, always=True)
    def calculate_instruction_length(cls, v, values):
        """Calculate instruction length"""
        if 'instructions' in values and values['instructions']:
            return len(values['instructions'])
        return v
    
    @validator('has_image', pre=True, always=True)
    def check_has_image(cls, v, values):
        """Check if recipe has an image"""
        return bool(values.get('image_url'))
    
    @validator('has_timing', pre=True, always=True)
    def check_has_timing(cls, v, values):
        """Check if recipe has timing information"""
        return bool(
            values.get('total_time') or 
            values.get('prep_time') or 
            values.get('cook_time')
        )
    
    @validator('success', pre=True, always=True)
    def sync_success_with_status(cls, v, values):
        """Ensure success field matches status"""
        if 'status' in values:
            return values['status'] == ScrapingStatus.SUCCESS
        return v
    
    def to_json(self) -> Dict[str, Any]:
        """Serialize recipe data for downstream processing
        
        Returns dict suitable for JSON serialization and AI processing
        by eKitchen Database MCP.
        """
        return self.model_dump(exclude_none=True)
    
    @classmethod
    def create_failed(cls, url: str, error: str, status: ScrapingStatus = ScrapingStatus.FAILED) -> "RecipeData":
        """Create a failed recipe data instance
        
        Args:
            url: The URL that failed to scrape
            error: Error message describing the failure
            status: Specific failure status
            
        Returns:
            RecipeData instance marked as failed
        """
        return cls(
            url=url,
            status=status,
            success=False,
            error=error,
            scraped_at=datetime.now()
        )
    
    def get_quality_score(self) -> float:
        """Calculate a quality score for the recipe data (0.0 - 1.0)
        
        Returns:
            Quality score based on completeness of data
        """
        score = 0.0
        max_score = 7.0
        
        # Core content scoring
        if self.title:
            score += 1.0
        if self.ingredients and len(self.ingredients) > 0:
            score += 1.5
        if self.instructions and len(self.instructions) > 50:
            score += 1.5
        
        # Additional content scoring
        if self.has_timing:
            score += 0.5
        if self.has_image:
            score += 0.5
        if self.yields:
            score += 0.5
        if self.description:
            score += 0.5
        
        # Bonus for rich data
        if self.ingredient_count >= 5:
            score += 0.5
        if self.instruction_length >= 200:
            score += 0.5
        
        return min(score / max_score, 1.0)
    
    def is_valid_recipe(self) -> bool:
        """Check if this represents a valid, usable recipe
        
        Returns:
            True if recipe has minimum required data
        """
        return (
            self.success and
            self.title and
            len(self.ingredients) >= 2 and
            len(self.instructions) >= 50
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a concise summary of the recipe
        
        Returns:
            Summary dict with key recipe information
        """
        return {
            "url": self.url,
            "title": self.title,
            "ingredients_count": self.ingredient_count,
            "has_timing": self.has_timing,
            "has_image": self.has_image,
            "quality_score": self.get_quality_score(),
            "is_valid": self.is_valid_recipe(),
            "site_domain": self.site_domain,
            "scraped_at": self.scraped_at.isoformat()
        }


class ScrapingRequest(BaseModel):
    """Request model for recipe scraping operations"""
    urls: List[str] = Field(..., description="List of recipe URLs to scrape")
    batch_size: int = Field(10, description="Number of recipes to process in parallel")
    timeout: int = Field(30, description="Timeout per request in seconds")
    retry_failed: bool = Field(True, description="Whether to retry failed requests")


class ScrapingResponse(BaseModel):
    """Response model for recipe scraping operations"""
    total_requested: int = Field(..., description="Total number of URLs requested")
    successful: int = Field(..., description="Number of successfully scraped recipes")
    failed: int = Field(..., description="Number of failed scraping attempts")
    recipes: List[RecipeData] = Field(..., description="List of scraped recipe data")
    processing_time: float = Field(..., description="Total processing time in seconds")
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.total_requested == 0:
            return 0.0
        return (self.successful / self.total_requested) * 100


class ServerHealth(BaseModel):
    """Server health status model"""
    status: str = Field(..., description="Server status (healthy, degraded, unhealthy)")
    timestamp: datetime = Field(default_factory=datetime.now)
    version: str = Field("0.1.0", description="Server version")
    uptime_seconds: float = Field(..., description="Server uptime in seconds")
    active_requests: int = Field(0, description="Number of active scraping requests")
    total_requests: int = Field(0, description="Total requests processed since startup")
    success_rate: float = Field(100.0, description="Overall success rate percentage")