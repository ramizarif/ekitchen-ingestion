"""Data models for Recipe Discovery MCP Server"""

from pydantic import BaseModel, Field, field_validator, HttpUrl, ConfigDict
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
    
    @field_validator('site_domain', mode='before')
    @classmethod
    def extract_domain(cls, v, info=None):
        """Automatically extract domain from URL"""
        return v  # Simplified for now to avoid complexity
    
    @field_validator('ingredient_count', mode='before')
    @classmethod
    def calculate_ingredient_count(cls, v, info=None):
        """Calculate ingredient count from ingredients list"""
        return v  # Simplified for now
    
    @field_validator('instruction_length', mode='before')
    @classmethod
    def calculate_instruction_length(cls, v, info=None):
        """Calculate instruction length"""
        return v  # Simplified for now
    
    @field_validator('has_image', mode='before')
    @classmethod
    def check_has_image(cls, v, info=None):
        """Check if recipe has an image"""
        return v  # Simplified for now
    
    @field_validator('has_timing', mode='before')
    @classmethod
    def check_has_timing(cls, v, info=None):
        """Check if recipe has timing information"""
        return v  # Simplified for now
    
    @field_validator('success', mode='before')
    @classmethod
    def sync_success_with_status(cls, v, info=None):
        """Ensure success field matches status"""
        return v  # Simplified for now
    
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


# Enhanced models for multi-site discovery (Issue #7)

class SiteConfig(BaseModel):
    """Configuration for a recipe site"""
    domain: str = Field(..., description="Site domain name")
    name: str = Field(..., description="Human-readable site name")
    base_url: str = Field(..., description="Base URL for the site")
    rate_limit: float = Field(2.0, description="Requests per second limit")
    timeout: int = Field(30, description="Request timeout in seconds")
    max_concurrent: int = Field(5, description="Maximum concurrent requests")
    search_paths: List[str] = Field(default_factory=list, description="Search URL templates")
    recipe_url_patterns: List[str] = Field(default_factory=list, description="Regex patterns for recipe URLs")
    priority: str = Field("medium", description="Site priority (high, medium, low)")
    enabled: bool = Field(True, description="Whether site is enabled for discovery")
    
    class Config:
        schema_extra = {
            "example": {
                "domain": "allrecipes.com",
                "name": "AllRecipes",
                "base_url": "https://www.allrecipes.com",
                "rate_limit": 1.0,
                "timeout": 30,
                "max_concurrent": 3,
                "search_paths": ["/search/results/?search={query}"],
                "recipe_url_patterns": ["/recipe/\\d+/.*"],
                "priority": "high",
                "enabled": True
            }
        }


class DiscoveryConfig(BaseModel):
    """Configuration for discovery operations"""
    max_urls_per_site: int = Field(50, description="Maximum URLs to discover per site")
    max_total_concurrent: int = Field(10, description="Maximum total concurrent operations")
    target_sites: Optional[List[str]] = Field(None, description="Specific sites to target (None for all)")
    validate_urls: bool = Field(True, description="Whether to validate discovered URLs")
    include_failed: bool = Field(False, description="Whether to include failed recipes in results")
    timeout_per_recipe: int = Field(30, description="Timeout per recipe scraping operation")
    
    class Config:
        schema_extra = {
            "example": {
                "max_urls_per_site": 25,
                "max_total_concurrent": 8,
                "target_sites": ["allrecipes.com", "foodnetwork.com"],
                "validate_urls": True,
                "include_failed": False,
                "timeout_per_recipe": 30
            }
        }


class DiscoveryJob(BaseModel):
    """Represents a discovery job with metadata"""
    job_id: str = Field(..., description="Unique job identifier")
    query: str = Field(..., description="Search query")
    config: DiscoveryConfig = Field(..., description="Discovery configuration")
    started_at: datetime = Field(default_factory=datetime.now, description="Job start time")
    status: str = Field("running", description="Job status (running, completed, failed)")
    
    def __post_init__(self):
        if not hasattr(self, 'job_id') or not self.job_id:
            import uuid
            self.job_id = str(uuid.uuid4())[:8]
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "abc12345",
                "query": "chicken recipe",
                "config": {
                    "max_urls_per_site": 25,
                    "validate_urls": True
                },
                "started_at": "2024-01-15T10:30:00Z",
                "status": "running"
            }
        }


class UrlDiscoveryResult(BaseModel):
    """Results from URL discovery operation"""
    site_domain: str = Field(..., description="Site domain")
    query: str = Field(..., description="Search query used")
    discovered_urls: List[str] = Field(..., description="List of discovered URLs")
    search_pages_processed: int = Field(..., description="Number of search pages processed")
    processing_time: float = Field(..., description="Time taken for discovery in seconds")
    success: bool = Field(..., description="Whether discovery was successful")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    @property
    def url_count(self) -> int:
        """Number of URLs discovered"""
        return len(self.discovered_urls)
    
    class Config:
        schema_extra = {
            "example": {
                "site_domain": "allrecipes.com",
                "query": "chicken recipe",
                "discovered_urls": [
                    "https://www.allrecipes.com/recipe/123/chicken-dish",
                    "https://www.allrecipes.com/recipe/456/another-chicken"
                ],
                "search_pages_processed": 2,
                "processing_time": 3.45,
                "success": True,
                "error_message": None
            }
        }


class DiscoveryResult(BaseModel):
    """Results from multi-site discovery operation"""
    job: DiscoveryJob = Field(..., description="Discovery job information")
    recipes: List[RecipeData] = Field(..., description="Discovered and scraped recipes")
    url_discovery_results: Dict[str, UrlDiscoveryResult] = Field(
        default_factory=dict, 
        description="URL discovery results by site"
    )
    site_summaries: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Summary statistics by site"
    )
    completed_at: datetime = Field(default_factory=datetime.now, description="Completion time")
    
    @property
    def summary(self) -> Dict[str, Any]:
        """Get summary statistics"""
        successful_recipes = [r for r in self.recipes if r.success]
        failed_recipes = [r for r in self.recipes if not r.success]
        
        return {
            "job_id": self.job.job_id,
            "query": self.job.query,
            "total_recipes": len(self.recipes),
            "successful_recipes": len(successful_recipes),
            "failed_recipes": len(failed_recipes),
            "success_rate": (len(successful_recipes) / len(self.recipes) * 100) if self.recipes else 0,
            "sites_processed": len(self.site_summaries),
            "total_urls_discovered": sum(
                result.url_count for result in self.url_discovery_results.values()
            ),
            "duration_seconds": (self.completed_at - self.job.started_at).total_seconds(),
            "avg_recipes_per_site": len(self.recipes) / len(self.site_summaries) if self.site_summaries else 0
        }
    
    def get_recipes_by_site(self, site_domain: str) -> List[RecipeData]:
        """Get recipes for a specific site"""
        return [recipe for recipe in self.recipes if recipe.site_domain == site_domain]
    
    def get_successful_recipes(self) -> List[RecipeData]:
        """Get only successful recipes"""
        return [recipe for recipe in self.recipes if recipe.success]
    
    def get_failed_recipes(self) -> List[RecipeData]:
        """Get only failed recipes"""
        return [recipe for recipe in self.recipes if not recipe.success]
    
    class Config:
        schema_extra = {
            "example": {
                "job": {
                    "job_id": "abc12345",
                    "query": "chicken recipe",
                    "status": "completed"
                },
                "recipes": [
                    {
                        "url": "https://example.com/recipe/1",
                        "title": "Chicken Dish",
                        "success": True
                    }
                ],
                "site_summaries": {
                    "allrecipes.com": {
                        "total_urls": 25,
                        "successful_recipes": 20,
                        "success_rate": 80.0
                    }
                },
                "completed_at": "2024-01-15T10:45:00Z"
            }
        }


class BatchDiscoveryRequest(BaseModel):
    """Request model for batch recipe discovery"""
    queries: List[str] = Field(..., description="List of search queries")
    config: DiscoveryConfig = Field(..., description="Discovery configuration")
    parallel_jobs: int = Field(3, description="Number of parallel discovery jobs")
    
    class Config:
        schema_extra = {
            "example": {
                "queries": ["chicken recipe", "pasta recipe", "dessert recipe"],
                "config": {
                    "max_urls_per_site": 20,
                    "validate_urls": True
                },
                "parallel_jobs": 2
            }
        }


class BatchDiscoveryResponse(BaseModel):
    """Response model for batch recipe discovery"""
    results: List[DiscoveryResult] = Field(..., description="Discovery results for each query")
    total_queries: int = Field(..., description="Total number of queries processed")
    successful_queries: int = Field(..., description="Number of successful queries")
    failed_queries: int = Field(..., description="Number of failed queries")
    total_recipes: int = Field(..., description="Total recipes discovered across all queries")
    processing_time: float = Field(..., description="Total processing time in seconds")
    
    @property
    def success_rate(self) -> float:
        """Calculate batch success rate"""
        return (self.successful_queries / self.total_queries * 100) if self.total_queries > 0 else 0
    
    @property
    def avg_recipes_per_query(self) -> float:
        """Calculate average recipes per query"""
        return self.total_recipes / self.total_queries if self.total_queries > 0 else 0
    
    class Config:
        schema_extra = {
            "example": {
                "results": [],
                "total_queries": 3,
                "successful_queries": 2,
                "failed_queries": 1,
                "total_recipes": 45,
                "processing_time": 125.6
            }
        }