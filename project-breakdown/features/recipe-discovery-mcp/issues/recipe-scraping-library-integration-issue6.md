# Issue #6: Recipe Scraping Library Integration

**Status**: ✅ Done
**Assigned**: Engineering Agent (to be spawned after #5)  
**Priority**: Critical (Core functionality for recipe discovery)  
**Estimated Effort**: 6-8 hours  

## Prerequisites 
- **Issue #4**: Python Scraping Library Research - ✅ COMPLETED
  - recipe-scrapers library approved for production use
  - FastMCP integration patterns validated
  - Async wrapper approach proven effective
- **Issue #5**: MCP Server Setup and Foundation - 🔄 IN PROGRESS
  - FastMCP server foundation required
  - Error handling framework needed
  - Configuration management needed

## Issue Overview

Integrate the recipe-scrapers library with the FastMCP server foundation, implementing async wrappers, comprehensive error handling, and batch scraping operations for production-ready recipe extraction.

## Implementation Plan

### Step 1: Async HTTP Client Wrapper (60 minutes)
Create `recipe_discovery_mcp/http_client.py`:

```python
import asyncio
import httpx
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

class AsyncHttpClient:
    def __init__(self, timeout: int = 30, max_concurrent: int = 10):
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        
    async def get(self, url: str, headers: Optional[Dict] = None) -> str:
        """Async HTTP GET with proper resource management"""
        async with self.semaphore:
            # Implementation with proper error handling
            pass
            
    async def close(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)
```

### Step 2: Recipe Scraper Integration (90 minutes)
Create `recipe_discovery_mcp/scraper.py` using patterns from Issue #4:

```python
import asyncio
from typing import List, Dict, Any, Optional
from recipe_scrapers import scrape_me
from concurrent.futures import ThreadPoolExecutor

from .models import RecipeData
from .http_client import AsyncHttpClient
from .utils.error_handling import handle_scraping_errors
from .utils.retry import RetryManager

class RecipeScrapingService:
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self.http_client = AsyncHttpClient()
        self.retry_manager = RetryManager()
        
    @handle_scraping_errors
    async def scrape_recipe(self, url: str) -> RecipeData:
        """Scrape single recipe with error handling"""
        async with self.semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor, 
                self._scrape_sync, 
                url
            )
    
    def _scrape_sync(self, url: str) -> RecipeData:
        """Synchronous scraping wrapper"""
        try:
            scraper = scrape_me(url)
            return RecipeData(
                url=url,
                title=scraper.title(),
                ingredients=scraper.ingredients(),
                instructions=scraper.instructions(),
                total_time=scraper.total_time(),
                yields=scraper.yields(),
                image_url=scraper.image(),
                success=True
            )
        except Exception as e:
            return RecipeData(
                url=url,
                success=False,
                error=str(e)
            )
    
    async def scrape_batch(self, urls: List[str]) -> List[RecipeData]:
        """Batch scraping with progress tracking"""
        tasks = [self.scrape_recipe(url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

### Step 3: Rate Limiting System (45 minutes)
Create `recipe_discovery_mcp/rate_limiter.py`:

```python
import asyncio
import time
from typing import Dict
from collections import defaultdict

class RateLimiter:
    def __init__(self, requests_per_second: float = 2.0):
        self.requests_per_second = requests_per_second
        self.last_request_time = defaultdict(float)
        
    async def acquire(self, domain: str):
        """Rate limit requests per domain"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time[domain]
        min_interval = 1.0 / self.requests_per_second
        
        if time_since_last < min_interval:
            await asyncio.sleep(min_interval - time_since_last)
            
        self.last_request_time[domain] = time.time()
```

### Step 4: Retry and Error Handling (60 minutes)
Create `recipe_discovery_mcp/utils/retry.py`:

```python
import asyncio
import random
from typing import Callable, Any, Optional
from functools import wraps

class RetryManager:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        
    async def with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with exponential backoff retry"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(delay)
                    
        raise last_exception

def retry_on_failure(max_retries: int = 3):
    """Decorator for automatic retry with backoff"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retry_manager = RetryManager(max_retries)
            return await retry_manager.with_retry(func, *args, **kwargs)
        return wrapper
    return decorator
```

### Step 5: MCP Tool Integration (75 minutes)
Update `recipe_discovery_mcp/server.py` with scraping tools:

```python
from fastmcp.tools import tool
from .scraper import RecipeScrapingService

# Initialize scraping service
scraping_service = RecipeScrapingService()

@tool("scrape_single_recipe")
async def scrape_single_recipe(url: str) -> Dict[str, Any]:
    """Scrape a single recipe from URL"""
    result = await scraping_service.scrape_recipe(url)
    return result.to_json()

@tool("scrape_recipe_batch") 
async def scrape_recipe_batch(urls: List[str]) -> Dict[str, Any]:
    """Scrape multiple recipes in batch"""
    results = await scraping_service.scrape_batch(urls)
    return {
        "recipes": [r.to_json() for r in results],
        "total": len(results),
        "successful": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success)
    }

@tool("test_scraping_service")
async def test_scraping_service() -> Dict[str, Any]:
    """Test scraping service with known good URLs"""
    test_urls = [
        "https://www.allrecipes.com/recipe/213742/cheesy-chicken-broccoli-casserole/",
        "https://www.foodnetwork.com/recipes/alton-brown/baked-macaroni-and-cheese-recipe-1939524"
    ]
    results = await scraping_service.scrape_batch(test_urls)
    return {
        "test_results": [r.to_json() for r in results],
        "service_status": "operational" if any(r.success for r in results) else "error"
    }
```

### Step 6: Configuration Updates (30 minutes)
Update configuration for scraping settings:

#### Add to `config.py`:
```python
# Scraping Configuration
scraping_timeout: int = 30
max_concurrent_scrapes: int = 10
requests_per_second: float = 2.0
max_retries: int = 3
retry_base_delay: float = 1.0

# User Agent Settings
user_agent: str = "eKitchen Recipe Discovery Bot 1.0"
respect_robots_txt: bool = True
```

#### Add to `.env.example`:
```env
# Scraping Configuration
SCRAPING_TIMEOUT=30
MAX_CONCURRENT_SCRAPES=10
REQUESTS_PER_SECOND=2.0
MAX_RETRIES=3
USER_AGENT="eKitchen Recipe Discovery Bot 1.0"
```

### Step 7: Enhanced Data Models (30 minutes)
Update `models.py` with richer recipe data:

```python
from pydantic import BaseModel, HttpUrl, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class ScrapingStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"  
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    PARSING_ERROR = "parsing_error"

class RecipeData(BaseModel):
    """Enhanced recipe data structure with scraping metadata"""
    url: HttpUrl
    
    # Recipe Content
    title: Optional[str] = None
    ingredients: List[str] = []
    instructions: str = ""
    total_time: Optional[int] = None  # minutes
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    yields: Optional[str] = None
    image_url: Optional[HttpUrl] = None
    
    # Nutritional Info (if available)
    calories: Optional[int] = None
    protein: Optional[str] = None
    carbs: Optional[str] = None
    fat: Optional[str] = None
    
    # Scraping Metadata
    scraped_at: datetime = datetime.now()
    status: ScrapingStatus = ScrapingStatus.SUCCESS
    error_message: Optional[str] = None
    retry_count: int = 0
    response_time: Optional[float] = None  # seconds
    
    # Site Metadata
    site_domain: Optional[str] = None
    recipe_schema_type: Optional[str] = None  # JSON-LD, microdata, etc.
    
    @validator('site_domain', pre=True, always=True)
    def extract_domain(cls, v, values):
        if 'url' in values:
            from urllib.parse import urlparse
            return urlparse(str(values['url'])).netloc
        return v
        
    def to_json(self) -> Dict[str, Any]:
        """Serialize for downstream processing"""
        return self.dict(exclude_none=True)
        
    @property
    def success(self) -> bool:
        """Convenience property for success checking"""
        return self.status == ScrapingStatus.SUCCESS
```

### Step 8: Testing Framework (90 minutes)
Create comprehensive tests:

#### Unit Tests (`tests/unit/test_scraper.py`):
```python
import pytest
import asyncio
from unittest.mock import patch, MagicMock

from recipe_discovery_mcp.scraper import RecipeScrapingService
from recipe_discovery_mcp.models import RecipeData, ScrapingStatus

class TestRecipeScrapingService:
    @pytest.fixture
    def scraping_service(self):
        return RecipeScrapingService(max_concurrent=5)
        
    @pytest.mark.asyncio
    async def test_scrape_single_recipe_success(self, scraping_service):
        """Test successful single recipe scraping"""
        # Mock successful scraping
        with patch('recipe_scrapers.scrape_me') as mock_scraper:
            mock_scraper.return_value = create_mock_scraper()
            
            result = await scraping_service.scrape_recipe(
                "https://example.com/recipe"
            )
            
            assert result.success
            assert result.title == "Test Recipe"
            assert len(result.ingredients) > 0
            
    @pytest.mark.asyncio
    async def test_scrape_batch_mixed_results(self, scraping_service):
        """Test batch scraping with mixed success/failure"""
        # Implementation with mocked responses
        pass
        
    @pytest.mark.asyncio  
    async def test_rate_limiting(self, scraping_service):
        """Test rate limiting works correctly"""
        # Implementation testing delay between requests
        pass
```

#### Integration Tests (`tests/integration/test_mcp_integration.py`):
```python
import pytest
from fastmcp.testing import TestClient

from recipe_discovery_mcp.server import server

class TestMCPIntegration:
    @pytest.fixture
    def client(self):
        return TestClient(server)
        
    @pytest.mark.asyncio
    async def test_scrape_single_recipe_tool(self, client):
        """Test MCP tool for single recipe scraping"""
        response = await client.call_tool(
            "scrape_single_recipe",
            {"url": "https://www.allrecipes.com/recipe/213742/"}
        )
        
        assert response.success
        assert "title" in response.data
        
    @pytest.mark.asyncio
    async def test_scrape_batch_tool(self, client):
        """Test MCP tool for batch scraping"""
        urls = [
            "https://www.allrecipes.com/recipe/213742/",
            "https://www.foodnetwork.com/recipes/recipe-123/"
        ]
        
        response = await client.call_tool(
            "scrape_recipe_batch", 
            {"urls": urls}
        )
        
        assert response.success
        assert response.data["total"] == 2
```

### Step 9: Error Scenarios Testing (45 minutes)
Test comprehensive error handling:

- Network connection failures
- Invalid URLs and 404 errors
- Malformed HTML and parsing errors
- Rate limiting responses
- Timeout scenarios
- Resource cleanup on errors

### Step 10: Documentation and Integration Validation (30 minutes)
- Update README with scraping functionality
- Document MCP tools and their parameters
- Validate integration with Claude Desktop
- Prepare handoff documentation for Issue #7

## Acceptance Criteria

### Functional Requirements ✅
- [ ] Single recipe scraping works with 95%+ success rate on supported sites
- [ ] Batch scraping handles 10+ recipes concurrently
- [ ] Rate limiting respects 2 requests/second default
- [ ] Retry logic handles transient failures automatically
- [ ] Error handling provides meaningful error messages
- [ ] All MCP tools work correctly with Claude Desktop

### Technical Requirements ✅
- [ ] Async wrapper properly integrates recipe-scrapers sync library
- [ ] ThreadPoolExecutor manages concurrent scraping effectively
- [ ] Resource cleanup prevents memory leaks
- [ ] Configuration supports all scraping parameters
- [ ] Logging captures scraping metrics and errors
- [ ] Code follows FastMCP and eKitchen patterns

### Integration Requirements ✅
- [ ] Builds successfully on Issue #5 server foundation
- [ ] Uses error handling framework from Issue #5
- [ ] Configuration integrates with Issue #5 config system
- [ ] Data models support downstream eKitchen Database MCP
- [ ] Ready for Issue #7 multi-site discovery engine
- [ ] Claude Desktop can invoke all scraping tools

### Quality Requirements ✅
- [ ] Code coverage >85% for core scraping functionality
- [ ] All error conditions properly handled and tested
- [ ] Performance supports target of 100+ recipes in <10 minutes
- [ ] Memory usage remains stable during batch operations
- [ ] No resource leaks or connection pooling issues

## Integration Notes

### Builds On Issue #5 ✅
- Uses FastMCP server foundation and async patterns
- Leverages error handling framework and logging system
- Integrates with configuration management system
- Follows established project structure and conventions

### Builds On Issue #4 ✅
- Implements recipe-scrapers library as approved
- Uses validated async wrapper patterns
- Follows proven error handling strategies
- Meets performance expectations from research

### Prepares For Issue #7 🔄
- Scraping service ready for multi-site coordination
- Batch processing supports site-level parallelization
- Error isolation enables per-site failure handling
- Rate limiting supports multiple concurrent domains

### Aligns With Project Architecture ✅
- MCP-powered conversational recipe discovery
- Async operations with comprehensive error handling
- Structured data flow with JSON serialization
- Natural language orchestration readiness

## Performance Expectations

### Throughput Targets
- **Single Recipe**: <3 seconds per recipe
- **Batch Processing**: 10+ recipes concurrently
- **Success Rate**: 95%+ on supported recipe sites
- **Error Recovery**: Automatic retry with exponential backoff

### Resource Usage
- **Memory**: <100MB for 10 concurrent scrapes
- **CPU**: Efficient ThreadPoolExecutor utilization
- **Network**: Respectful rate limiting (2 req/sec default)
- **Storage**: Minimal temporary data footprint

---

**Blocked until Issue #5 completion**  
**Ready for immediate implementation once dependencies met**  
**Expected completion: 6-8 hours after Issue #5**  
**Board Sync 2025-07-20 01:36**: Status updated from GitHub board - Done → Done
