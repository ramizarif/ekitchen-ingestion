"""Async HTTP client wrapper for recipe scraping operations

Provides async wrapper around synchronous HTTP operations for the recipe-scrapers
library with comprehensive error handling, rate limiting, and resource management.
"""

import asyncio
import time
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import httpx
import structlog

from .config import get_config
from .utils.error_handling import NetworkError, MCPError


class AsyncHttpClient:
    """Async HTTP client with rate limiting and resource management
    
    Wraps httpx with async/await patterns for use with recipe-scrapers library.
    Provides rate limiting per domain and proper resource cleanup.
    """
    
    def __init__(self, timeout: int = 30, max_concurrent: int = 10):
        """Initialize async HTTP client
        
        Args:
            timeout: Request timeout in seconds
            max_concurrent: Maximum concurrent requests
        """
        self.config = get_config()
        self.timeout = timeout or self.config.request_timeout
        self.max_concurrent = max_concurrent or self.config.max_concurrent_requests
        
        # Concurrency control
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent)
        
        # Rate limiting per domain
        self.domain_last_request = {}
        self.requests_per_second = self.config.requests_per_second
        
        # HTTP client configuration
        self.client_config = {
            "timeout": httpx.Timeout(self.timeout),
            "headers": {
                "User-Agent": self.config.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            },
            "follow_redirects": True,
            "verify": True
        }
        
        self.logger = structlog.get_logger().bind(component="http_client")
        
    async def get(self, url: str, headers: Optional[Dict] = None) -> str:
        """Async HTTP GET with proper resource management and rate limiting
        
        Args:
            url: URL to fetch
            headers: Optional additional headers
            
        Returns:
            Response content as string
            
        Raises:
            NetworkError: For HTTP-related errors
            MCPError: For other failures
        """
        async with self.semaphore:
            try:
                # Apply rate limiting based on domain
                await self._apply_rate_limiting(url)
                
                # Merge headers
                request_headers = self.client_config["headers"].copy()
                if headers:
                    request_headers.update(headers)
                
                # Execute HTTP request in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                content = await loop.run_in_executor(
                    self.executor,
                    self._fetch_sync,
                    url,
                    request_headers
                )
                
                self.logger.debug(
                    "HTTP request successful",
                    url=url,
                    content_length=len(content) if content else 0
                )
                
                return content
                
            except httpx.TimeoutException as e:
                self.logger.warning(
                    "HTTP request timeout",
                    url=url,
                    timeout=self.timeout
                )
                raise NetworkError(f"Request timeout for {url}: {str(e)}")
                
            except httpx.HTTPStatusError as e:
                self.logger.warning(
                    "HTTP error response",
                    url=url,
                    status_code=e.response.status_code,
                    reason=e.response.reason_phrase
                )
                raise NetworkError(
                    f"HTTP {e.response.status_code} for {url}: {e.response.reason_phrase}"
                )
                
            except httpx.RequestError as e:
                self.logger.error(
                    "HTTP request error",
                    url=url,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                raise NetworkError(f"Request failed for {url}: {str(e)}")
                
            except Exception as e:
                self.logger.error(
                    "Unexpected error in HTTP request",
                    url=url,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                raise MCPError(f"Unexpected error fetching {url}: {str(e)}")
    
    def _fetch_sync(self, url: str, headers: Dict[str, str]) -> str:
        """Synchronous HTTP fetch for use in thread pool
        
        Args:
            url: URL to fetch
            headers: Request headers
            
        Returns:
            Response content as string
        """
        with httpx.Client(**self.client_config) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.text
    
    async def _apply_rate_limiting(self, url: str) -> None:
        """Apply rate limiting based on domain
        
        Args:
            url: URL to extract domain from
        """
        try:
            domain = urlparse(url).netloc
            current_time = time.time()
            
            if domain in self.domain_last_request:
                time_since_last = current_time - self.domain_last_request[domain]
                min_interval = 1.0 / self.requests_per_second
                
                if time_since_last < min_interval:
                    sleep_time = min_interval - time_since_last
                    self.logger.debug(
                        "Rate limiting request",
                        domain=domain,
                        sleep_time=sleep_time
                    )
                    await asyncio.sleep(sleep_time)
            
            self.domain_last_request[domain] = time.time()
            
        except Exception as e:
            # Don't fail the request for rate limiting errors
            self.logger.warning(
                "Rate limiting error",
                url=url,
                error=str(e)
            )
    
    async def close(self) -> None:
        """Cleanup resources and shutdown thread pool
        
        Should be called when the client is no longer needed.
        """
        try:
            self.logger.info("Shutting down HTTP client")
            
            # Shutdown thread pool executor
            self.executor.shutdown(wait=True)
            
            # Clear domain tracking
            self.domain_last_request.clear()
            
            self.logger.info("HTTP client shutdown complete")
            
        except Exception as e:
            self.logger.error(
                "Error during HTTP client shutdown",
                error_type=type(e).__name__,
                error_message=str(e)
            )
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        await self.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics for monitoring
        
        Returns:
            Dictionary with client statistics
        """
        return {
            "max_concurrent": self.max_concurrent,
            "timeout": self.timeout,
            "requests_per_second": self.requests_per_second,
            "tracked_domains": len(self.domain_last_request),
            "executor_active": not self.executor._shutdown
        }