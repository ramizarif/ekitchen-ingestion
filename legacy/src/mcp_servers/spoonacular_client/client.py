"""Spoonacular API client for ingredient data retrieval

Async HTTP client implementing Spoonacular's ingredient endpoints with
rate limiting, retry logic, and comprehensive error handling.
"""

import asyncio
import time
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin
import httpx
import structlog

from .config import get_config, SpoonacularConfig
from .exceptions import (
    SpoonacularError,
    SpoonacularAuthError,
    SpoonacularRateLimitError,
    SpoonacularNotFoundError,
    SpoonacularNetworkError
)

logger = structlog.get_logger()


class SpoonacularClient:
    """Async Spoonacular API client with rate limiting and error handling
    
    Implements three core ingredient endpoints:
    1. Ingredient search: Find ingredients by name
    2. Ingredient information: Get nutrition data per 100g  
    3. Ingredient substitutes: Get substitute suggestions
    """
    
    def __init__(self, config: Optional[SpoonacularConfig] = None):
        """Initialize Spoonacular client
        
        Args:
            config: Optional SpoonacularConfig, loads from file if not provided
        """
        self.config = config or get_config()
        
        # Rate limiting state
        self.last_request_time = 0
        self.request_count_minute = 0
        self.minute_window_start = time.time()
        
        # HTTP client configuration
        self.client_config = {
            "timeout": httpx.Timeout(self.config.request_timeout),
            "headers": {
                "User-Agent": "eKitchen-Ingestion/1.0",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            "follow_redirects": True,
            "verify": True
        }
        
        self.logger = logger.bind(component="spoonacular_client")
        
    async def search_ingredients(self, 
                               query: str, 
                               number: int = 10,
                               meta_information: bool = True,
                               intolerances: Optional[str] = None) -> Dict[str, Any]:
        """Search for ingredients by name
        
        Args:
            query: Search term (e.g., "apple", "chicken breast")
            number: Number of results to return (max 100)
            meta_information: Include nutrition and other metadata
            intolerances: Comma-separated intolerances to exclude
            
        Returns:
            API response with ingredient search results
            
        Raises:
            SpoonacularError: For API errors
        """
        params = {
            "apiKey": self.config.api_key,
            "query": query,
            "number": min(number, 100),
            "metaInformation": str(meta_information).lower()
        }
        
        if intolerances:
            params["intolerances"] = intolerances
            
        return await self._make_request(
            "GET",
            "/food/ingredients/search",
            params=params
        )
    
    async def get_ingredient_information(self, 
                                       ingredient_id: int,
                                       amount: float = 100,
                                       unit: str = "grams") -> Dict[str, Any]:
        """Get detailed ingredient information including nutrition per 100g
        
        Args:
            ingredient_id: Spoonacular ingredient ID
            amount: Amount for nutrition calculation
            unit: Unit for amount (grams, ounces, etc)
            
        Returns:
            API response with detailed ingredient information
            
        Raises:
            SpoonacularError: For API errors
        """
        params = {
            "apiKey": self.config.api_key,
            "amount": amount,
            "unit": unit
        }
        
        return await self._make_request(
            "GET", 
            f"/food/ingredients/{ingredient_id}/information",
            params=params
        )
    
    async def get_ingredient_substitutes(self, ingredient_name: str) -> Dict[str, Any]:
        """Get substitute suggestions for an ingredient
        
        Args:
            ingredient_name: Name of ingredient to find substitutes for
            
        Returns:
            API response with substitute suggestions
            
        Raises:
            SpoonacularError: For API errors
        """
        params = {
            "apiKey": self.config.api_key,
            "ingredientName": ingredient_name
        }
        
        return await self._make_request(
            "GET",
            "/food/ingredients/substitutes",
            params=params
        )
    
    async def _make_request(self, 
                          method: str,
                          endpoint: str, 
                          params: Optional[Dict] = None,
                          data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to Spoonacular API with rate limiting and retries
        
        Args:
            method: HTTP method (GET, POST, etc)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            
        Returns:
            JSON response data
            
        Raises:
            SpoonacularError: For API errors
        """
        url = urljoin(self.config.base_url, endpoint)
        
        for attempt in range(self.config.max_retries + 1):
            try:
                # Apply rate limiting
                await self._apply_rate_limiting()
                
                async with httpx.AsyncClient(**self.client_config) as client:
                    if method.upper() == "GET":
                        response = await client.get(url, params=params)
                    elif method.upper() == "POST":
                        response = await client.post(url, params=params, json=data)
                    else:
                        raise SpoonacularError(f"Unsupported HTTP method: {method}")
                    
                    # Handle response
                    return await self._handle_response(response, attempt)
                    
            except SpoonacularRateLimitError as e:
                if attempt == self.config.max_retries:
                    raise
                    
                # Wait and retry for rate limits
                wait_time = e.retry_after or (self.config.retry_delay * (2 ** attempt))
                self.logger.warning(
                    "Rate limit hit, waiting before retry",
                    attempt=attempt + 1,
                    wait_time=wait_time
                )
                await asyncio.sleep(wait_time)
                
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                if attempt == self.config.max_retries:
                    raise SpoonacularNetworkError(f"Network error after {attempt + 1} attempts: {str(e)}")
                    
                # Wait and retry for network errors
                wait_time = self.config.retry_delay * (2 ** attempt)
                self.logger.warning(
                    "Network error, retrying",
                    attempt=attempt + 1,
                    wait_time=wait_time,
                    error=str(e)
                )
                await asyncio.sleep(wait_time)
                
            except SpoonacularError:
                # Don't retry API errors (auth, not found, etc)
                raise
                
    async def _handle_response(self, response: httpx.Response, attempt: int) -> Dict[str, Any]:
        """Handle HTTP response and convert to appropriate exceptions
        
        Args:
            response: HTTP response object
            attempt: Current attempt number
            
        Returns:
            JSON response data
            
        Raises:
            SpoonacularError: For various API errors
        """
        if response.status_code == 200:
            try:
                return response.json()
            except Exception as e:
                raise SpoonacularError(f"Invalid JSON response: {str(e)}")
                
        elif response.status_code == 401:
            raise SpoonacularAuthError(
                "Invalid API key. Check your Spoonacular API key in config/spoonacular.json",
                status_code=401
            )
            
        elif response.status_code == 403:
            raise SpoonacularAuthError(
                "API access forbidden. Check your Spoonacular subscription plan.",
                status_code=403
            )
            
        elif response.status_code == 404:
            raise SpoonacularNotFoundError(
                "Resource not found",
                status_code=404
            )
            
        elif response.status_code == 429:
            # Extract retry-after header if available
            retry_after = None
            if "retry-after" in response.headers:
                try:
                    retry_after = int(response.headers["retry-after"])
                except ValueError:
                    pass
                    
            raise SpoonacularRateLimitError(
                f"Rate limit exceeded. Daily/minute quota reached.",
                status_code=429,
                retry_after=retry_after
            )
            
        else:
            # Try to get error message from response
            try:
                error_data = response.json()
                error_message = error_data.get("message", f"HTTP {response.status_code}")
            except:
                error_message = f"HTTP {response.status_code}: {response.reason_phrase}"
                
            raise SpoonacularError(
                error_message,
                status_code=response.status_code
            )
    
    async def _apply_rate_limiting(self):
        """Apply rate limiting based on Spoonacular API limits
        
        Spoonacular has both per-minute and per-day limits.
        This implements per-minute limiting with buffer for safety.
        """
        current_time = time.time()
        
        # Reset minute window if needed
        if current_time - self.minute_window_start >= 60:
            self.minute_window_start = current_time
            self.request_count_minute = 0
            
        # Check if we need to wait
        if self.request_count_minute >= self.config.requests_per_minute:
            sleep_time = 60 - (current_time - self.minute_window_start)
            if sleep_time > 0:
                self.logger.info(
                    "Rate limit approaching, waiting",
                    sleep_time=sleep_time,
                    requests_this_minute=self.request_count_minute
                )
                await asyncio.sleep(sleep_time)
                
                # Reset after waiting
                self.minute_window_start = time.time()
                self.request_count_minute = 0
        
        # Increment request count
        self.request_count_minute += 1
        self.last_request_time = current_time
    
    async def close(self):
        """Clean up resources"""
        # No persistent connections to close in this implementation
        pass
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()