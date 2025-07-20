"""Recipe scraping service with async wrapper for recipe-scrapers library

Integrates the recipe-scrapers library with async patterns for production-ready
recipe extraction with comprehensive error handling and batch processing.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import structlog

try:
    from recipe_scrapers import scrape_me
except ImportError:
    # Graceful handling if recipe-scrapers not installed
    scrape_me = None

from .models import RecipeData
from .http_client import AsyncHttpClient
from .config import get_config
from .utils.error_handling import handle_scraping_errors, MCPError, NetworkError


class RecipeScrapingService:
    """Recipe scraping service with async operations and batch processing
    
    Wraps the synchronous recipe-scrapers library with async patterns for
    production use in the Recipe Discovery MCP server.
    """
    
    def __init__(self, max_concurrent: int = None):
        """Initialize recipe scraping service
        
        Args:
            max_concurrent: Maximum concurrent scraping operations
        """
        self.config = get_config()
        self.max_concurrent = max_concurrent or self.config.max_concurrent_requests
        
        # Verify recipe-scrapers is available
        if scrape_me is None:
            raise MCPError(
                "recipe-scrapers library not installed. "
                "Install with: pip install recipe-scrapers"
            )
        
        # Concurrency control
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent)
        
        # HTTP client for additional requests if needed
        self.http_client = AsyncHttpClient(
            timeout=self.config.request_timeout,
            max_concurrent=self.max_concurrent
        )
        
        # Statistics tracking
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "start_time": datetime.now()
        }
        
        self.logger = structlog.get_logger().bind(component="scraper")
        self.logger.info(
            "Recipe scraping service initialized",
            max_concurrent=self.max_concurrent,
            timeout=self.config.request_timeout
        )
    
    @handle_scraping_errors
    async def scrape_recipe(self, url: str) -> RecipeData:
        """Scrape single recipe with comprehensive error handling
        
        Args:
            url: Recipe URL to scrape
            
        Returns:
            RecipeData with recipe information or error details
        """
        async with self.semaphore:
            start_time = time.time()
            
            try:
                self.logger.debug("Starting recipe scrape", url=url)
                self.stats["total_requests"] += 1
                
                # Execute scraping in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                recipe_data = await loop.run_in_executor(
                    self.executor,
                    self._scrape_sync,
                    url
                )
                
                processing_time = time.time() - start_time
                
                if recipe_data.success:
                    self.stats["successful_requests"] += 1
                    self.logger.info(
                        "Recipe scraped successfully",
                        url=url,
                        title=recipe_data.title,
                        ingredients_count=len(recipe_data.ingredients),
                        processing_time=processing_time
                    )
                else:
                    self.stats["failed_requests"] += 1
                    self.logger.warning(
                        "Recipe scraping failed",
                        url=url,
                        error=recipe_data.error,
                        processing_time=processing_time
                    )
                
                return recipe_data
                
            except Exception as e:
                self.stats["failed_requests"] += 1
                processing_time = time.time() - start_time
                
                self.logger.error(
                    "Unexpected error in recipe scraping",
                    url=url,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    processing_time=processing_time
                )
                
                return RecipeData.create_failed(url, f"Unexpected error: {str(e)}")
    
    def _scrape_sync(self, url: str) -> RecipeData:
        """Synchronous scraping wrapper for thread pool execution
        
        Args:
            url: Recipe URL to scrape
            
        Returns:
            RecipeData with scraped information
        """
        try:
            # Use recipe-scrapers to extract recipe data
            scraper = scrape_me(url)
            
            # Extract available data from scraper
            recipe_data = RecipeData(
                url=url,
                title=self._safe_extract(scraper.title),
                ingredients=self._safe_extract(scraper.ingredients) or [],
                instructions=self._safe_extract(scraper.instructions) or "",
                total_time=self._safe_extract(scraper.total_time),
                prep_time=self._safe_extract(scraper.prep_time),
                cook_time=self._safe_extract(scraper.cook_time),
                yields=self._safe_extract(scraper.yields),
                image_url=self._safe_extract(scraper.image),
                description=self._safe_extract(scraper.description),
                author=self._safe_extract(scraper.author),
                cuisine=self._safe_extract(scraper.cuisine),
                category=self._safe_extract(scraper.category),
                scraped_at=datetime.now(),
                success=True
            )
            
            # Validate that we got meaningful data
            if not recipe_data.title or not recipe_data.ingredients:
                return RecipeData.create_failed(
                    url, 
                    "No title or ingredients found - may not be a recipe page"
                )
            
            return recipe_data
            
        except Exception as e:
            error_msg = f"Scraping failed: {str(e)}"
            
            # Categorize error types for better handling
            if "404" in str(e) or "Not Found" in str(e):
                error_msg = f"Recipe not found (404): {url}"
            elif "timeout" in str(e).lower():
                error_msg = f"Request timeout: {url}"
            elif "connection" in str(e).lower():
                error_msg = f"Connection error: {url}"
            
            return RecipeData.create_failed(url, error_msg)
    
    def _safe_extract(self, extraction_func) -> Any:
        """Safely extract data from scraper with error handling
        
        Args:
            extraction_func: Function/callable to extract data
            
        Returns:
            Extracted data or None if extraction fails
        """
        try:
            if callable(extraction_func):
                return extraction_func()
            return extraction_func
        except Exception:
            return None
    
    async def scrape_batch(
        self, 
        urls: List[str], 
        batch_size: Optional[int] = None
    ) -> List[RecipeData]:
        """Batch scraping with progress tracking and error isolation
        
        Args:
            urls: List of recipe URLs to scrape
            batch_size: Number of URLs to process concurrently (defaults to max_concurrent)
            
        Returns:
            List of RecipeData objects (successful and failed)
        """
        if not urls:
            return []
        
        batch_size = batch_size or self.max_concurrent
        start_time = time.time()
        
        self.logger.info(
            "Starting batch recipe scraping",
            total_urls=len(urls),
            batch_size=batch_size
        )
        
        try:
            # Process URLs in batches to control concurrency
            all_results = []
            
            for i in range(0, len(urls), batch_size):
                batch_urls = urls[i:i + batch_size]
                batch_number = (i // batch_size) + 1
                total_batches = (len(urls) + batch_size - 1) // batch_size
                
                self.logger.debug(
                    "Processing batch",
                    batch_number=batch_number,
                    total_batches=total_batches,
                    batch_size=len(batch_urls)
                )
                
                # Create tasks for this batch
                tasks = [self.scrape_recipe(url) for url in batch_urls]
                
                # Execute batch with error isolation
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results and handle exceptions
                for j, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        # Convert exceptions to failed RecipeData
                        failed_url = batch_urls[j]
                        error_data = RecipeData.create_failed(
                            failed_url, 
                            f"Batch processing error: {str(result)}"
                        )
                        all_results.append(error_data)
                    else:
                        all_results.append(result)
            
            processing_time = time.time() - start_time
            successful_count = sum(1 for r in all_results if r.success)
            failed_count = len(all_results) - successful_count
            
            self.logger.info(
                "Batch scraping completed",
                total_processed=len(all_results),
                successful=successful_count,
                failed=failed_count,
                success_rate=f"{(successful_count/len(all_results)*100):.1f}%",
                processing_time=processing_time
            )
            
            return all_results
            
        except Exception as e:
            self.logger.error(
                "Fatal error in batch processing",
                error_type=type(e).__name__,
                error_message=str(e),
                total_urls=len(urls)
            )
            
            # Return failed entries for all URLs
            return [
                RecipeData.create_failed(url, f"Batch processing failed: {str(e)}")
                for url in urls
            ]
    
    async def test_scraping_service(self) -> Dict[str, Any]:
        """Test scraping service with known good URLs
        
        Returns:
            Test results with service status and performance data
        """
        test_urls = [
            "https://www.allrecipes.com/recipe/213742/cheesy-chicken-broccoli-casserole/",
            "https://www.foodnetwork.com/recipes/alton-brown/baked-macaroni-and-cheese-recipe-1939524",
            "https://www.bbcgoodfood.com/recipes/classic-shepherd-pie"
        ]
        
        self.logger.info("Running scraping service test", test_urls=len(test_urls))
        
        start_time = time.time()
        results = await self.scrape_batch(test_urls)
        test_time = time.time() - start_time
        
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        
        test_report = {
            "service_status": "operational" if successful_results else "error",
            "test_summary": {
                "total_tests": len(test_urls),
                "successful": len(successful_results),
                "failed": len(failed_results),
                "success_rate": f"{(len(successful_results)/len(test_urls)*100):.1f}%",
                "test_duration_seconds": round(test_time, 2)
            },
            "successful_recipes": [
                {
                    "url": r.url,
                    "title": r.title,
                    "ingredients_count": len(r.ingredients)
                } 
                for r in successful_results
            ],
            "failed_tests": [
                {
                    "url": r.url,
                    "error": r.error
                }
                for r in failed_results
            ]
        }
        
        self.logger.info(
            "Scraping service test completed",
            status=test_report["service_status"],
            success_rate=test_report["test_summary"]["success_rate"]
        )
        
        return test_report
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics for monitoring
        
        Returns:
            Dictionary with service performance statistics
        """
        uptime = (datetime.now() - self.stats["start_time"]).total_seconds()
        
        return {
            "uptime_seconds": uptime,
            "total_requests": self.stats["total_requests"],
            "successful_requests": self.stats["successful_requests"],
            "failed_requests": self.stats["failed_requests"],
            "success_rate": (
                (self.stats["successful_requests"] / self.stats["total_requests"] * 100)
                if self.stats["total_requests"] > 0 else 0.0
            ),
            "requests_per_second": (
                self.stats["total_requests"] / uptime if uptime > 0 else 0.0
            ),
            "max_concurrent": self.max_concurrent
        }
    
    async def close(self) -> None:
        """Cleanup resources and shutdown service
        
        Should be called when the service is no longer needed.
        """
        try:
            self.logger.info("Shutting down recipe scraping service")
            
            # Cleanup HTTP client
            await self.http_client.close()
            
            # Shutdown thread pool executor
            self.executor.shutdown(wait=True)
            
            self.logger.info("Recipe scraping service shutdown complete")
            
        except Exception as e:
            self.logger.error(
                "Error during scraping service shutdown",
                error_type=type(e).__name__,
                error_message=str(e)
            )
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        await self.close()