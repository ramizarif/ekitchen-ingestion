"""Comprehensive error scenario testing for Recipe Discovery MCP

Tests various failure modes and edge cases to ensure robust error handling
across all components of the recipe scraping system.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from recipe_discovery_mcp.scraper import RecipeScrapingService
from recipe_discovery_mcp.http_client import AsyncHttpClient
from recipe_discovery_mcp.rate_limiter import RateLimiter
from recipe_discovery_mcp.models import RecipeData, ScrapingStatus
from recipe_discovery_mcp.utils.retry import RetryManager, RetryConfig
from recipe_discovery_mcp.utils.error_handling import NetworkError, MCPError


class TestNetworkErrorScenarios:
    """Test network-related error scenarios"""
    
    @pytest.fixture
    def http_client(self):
        return AsyncHttpClient(timeout=1, max_concurrent=2)
    
    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, http_client):
        """Test handling of request timeouts"""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            # Mock timeout exception
            mock_client.get.side_effect = httpx.TimeoutException("Request timed out")
            
            with pytest.raises(NetworkError) as exc_info:
                await http_client.get("https://example.com/timeout")
            
            assert "timeout" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self, http_client):
        """Test handling of connection errors"""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            # Mock connection error
            mock_client.get.side_effect = httpx.ConnectError("Connection failed")
            
            with pytest.raises(NetworkError) as exc_info:
                await http_client.get("https://example.com/connection-error")
            
            assert "failed" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_http_error_status_codes(self, http_client):
        """Test handling of various HTTP error status codes"""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            # Mock HTTP error responses
            error_codes = [404, 403, 500, 502, 503, 504]
            
            for code in error_codes:
                mock_response = MagicMock()
                mock_response.status_code = code
                mock_response.reason_phrase = f"HTTP {code}"
                
                mock_client.get.side_effect = httpx.HTTPStatusError(
                    f"HTTP {code}", request=MagicMock(), response=mock_response
                )
                
                with pytest.raises(NetworkError) as exc_info:
                    await http_client.get(f"https://example.com/error-{code}")
                
                assert str(code) in str(exc_info.value)


class TestScrapingErrorScenarios:
    """Test recipe scraping error scenarios"""
    
    @pytest.fixture
    def scraping_service(self):
        with patch('recipe_discovery_mcp.scraper.get_config'):
            with patch('recipe_discovery_mcp.scraper.scrape_me') as mock_scrape_me:
                service = RecipeScrapingService(max_concurrent=2)
                service.mock_scrape_me = mock_scrape_me
                return service
    
    @pytest.mark.asyncio
    async def test_recipe_scrapers_library_errors(self, scraping_service):
        """Test handling of recipe-scrapers library exceptions"""
        error_scenarios = [
            ("Import error", ImportError("recipe-scrapers not found")),
            ("Parsing error", ValueError("Invalid HTML structure")),
            ("AttributeError", AttributeError("'NoneType' object has no attribute 'text'")),
            ("Network timeout", TimeoutError("Request timed out")),
            ("Generic exception", Exception("Unknown scraping error"))
        ]
        
        for error_name, exception in error_scenarios:
            scraping_service.mock_scrape_me.side_effect = exception
            
            result = await scraping_service.scrape_recipe("https://example.com/recipe")
            
            assert not result.success
            assert result.status == ScrapingStatus.FAILED
            assert error_name.lower().replace(" ", "_") in result.error.lower() or \
                   str(exception) in result.error
    
    @pytest.mark.asyncio
    async def test_malformed_recipe_data(self, scraping_service):
        """Test handling of malformed or incomplete recipe data"""
        # Mock scraper that returns None/empty values
        mock_scraper = MagicMock()
        mock_scraper.title.return_value = None
        mock_scraper.ingredients.return_value = []
        mock_scraper.instructions.return_value = ""
        mock_scraper.total_time.return_value = None
        mock_scraper.yields.return_value = None
        mock_scraper.image.return_value = None
        
        scraping_service.mock_scrape_me.return_value = mock_scraper
        
        result = await scraping_service.scrape_recipe("https://example.com/empty-recipe")
        
        assert not result.success
        assert "No title or ingredients found" in result.error
    
    @pytest.mark.asyncio
    async def test_batch_scraping_with_failures(self, scraping_service):
        """Test batch scraping with mixed failures"""
        def mock_scraper_side_effect(url):
            if "fail" in url:
                raise Exception(f"Failed to scrape {url}")
            elif "timeout" in url:
                raise TimeoutError("Request timeout")
            elif "empty" in url:
                # Return empty scraper
                mock_scraper = MagicMock()
                mock_scraper.title.return_value = None
                mock_scraper.ingredients.return_value = []
                return mock_scraper
            else:
                # Return successful scraper
                mock_scraper = MagicMock()
                mock_scraper.title.return_value = f"Recipe from {url}"
                mock_scraper.ingredients.return_value = ["ingredient1", "ingredient2"]
                mock_scraper.instructions.return_value = "Test instructions"
                return mock_scraper
        
        scraping_service.mock_scrape_me.side_effect = mock_scraper_side_effect
        
        urls = [
            "https://example.com/recipe1",      # Success
            "https://example.com/fail-recipe",  # Exception
            "https://example.com/recipe2",      # Success
            "https://example.com/timeout-recipe", # Timeout
            "https://example.com/empty-recipe"   # Empty data
        ]
        
        results = await scraping_service.scrape_batch(urls)
        
        assert len(results) == 5
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        assert len(successful) == 2  # Only recipe1 and recipe2
        assert len(failed) == 3      # fail, timeout, empty
        
        # Check specific error types
        fail_result = next(r for r in results if "fail" in r.url)
        assert "Failed to scrape" in fail_result.error
        
        timeout_result = next(r for r in results if "timeout" in r.url)
        assert "timeout" in timeout_result.error.lower()
        
        empty_result = next(r for r in results if "empty" in r.url)
        assert "No title or ingredients" in empty_result.error


class TestRateLimitingErrorScenarios:
    """Test rate limiting edge cases and error scenarios"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_with_invalid_domain(self):
        """Test rate limiter with invalid/empty domains"""
        rate_limiter = RateLimiter(requests_per_second=5.0)
        
        # Test with None domain
        await rate_limiter.acquire(None)  # Should not raise
        
        # Test with empty string
        await rate_limiter.acquire("")   # Should not raise
        
        # Verify stats still work
        stats = rate_limiter.get_stats()
        assert "global_stats" in stats
    
    @pytest.mark.asyncio
    async def test_concurrent_rate_limiting_stress(self):
        """Test rate limiter under concurrent stress"""
        rate_limiter = RateLimiter(requests_per_second=10.0)
        
        async def make_request(domain, request_id):
            await rate_limiter.acquire(f"example{domain}.com")
            return request_id
        
        # Create many concurrent requests
        tasks = [make_request(i % 3, i) for i in range(20)]
        
        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()
        
        # Should complete all requests
        assert len(results) == 20
        
        # Should take some time due to rate limiting
        assert end_time - start_time > 0.1


class TestRetryMechanismErrors:
    """Test retry mechanism error scenarios"""
    
    @pytest.mark.asyncio
    async def test_retry_with_non_retryable_errors(self):
        """Test that non-retryable errors don't trigger retries"""
        config = RetryConfig(
            max_retries=3,
            retryable_exceptions=(NetworkError,),
            non_retryable_exceptions=(ValueError, TypeError)
        )
        retry_manager = RetryManager(config)
        
        attempt_count = 0
        
        async def failing_function():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Non-retryable error")
        
        with pytest.raises(ValueError):
            await retry_manager.with_retry(failing_function, operation_name="test")
        
        # Should only attempt once (no retries)
        assert attempt_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_exhaustion(self):
        """Test behavior when all retries are exhausted"""
        config = RetryConfig(max_retries=2, base_delay=0.01)  # Fast for testing
        retry_manager = RetryManager(config)
        
        attempt_count = 0
        
        async def always_failing_function():
            nonlocal attempt_count
            attempt_count += 1
            raise NetworkError(f"Attempt {attempt_count} failed")
        
        with pytest.raises(NetworkError) as exc_info:
            await retry_manager.with_retry(always_failing_function, operation_name="test")
        
        # Should attempt max_retries + 1 times (initial + retries)
        assert attempt_count == 3
        assert "Attempt 3 failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test successful retry after some failures"""
        config = RetryConfig(max_retries=3, base_delay=0.01)
        retry_manager = RetryManager(config)
        
        attempt_count = 0
        
        async def eventually_succeeding_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise NetworkError(f"Attempt {attempt_count} failed")
            return f"Success on attempt {attempt_count}"
        
        result = await retry_manager.with_retry(
            eventually_succeeding_function, 
            operation_name="test"
        )
        
        assert result == "Success on attempt 3"
        assert attempt_count == 3


class TestResourceLeakScenarios:
    """Test scenarios that could cause resource leaks"""
    
    @pytest.mark.asyncio
    async def test_http_client_cleanup_on_errors(self):
        """Test that HTTP client properly cleans up on errors"""
        http_client = AsyncHttpClient(max_concurrent=2)
        
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            # Mock exception during request
            mock_client.get.side_effect = Exception("Network error")
            
            # Make multiple failing requests
            for i in range(5):
                with pytest.raises(MCPError):
                    await http_client.get(f"https://example.com/error{i}")
            
            # Cleanup should work without issues
            await http_client.close()
            
            # Verify executor was shut down
            assert http_client.executor._shutdown
    
    @pytest.mark.asyncio
    async def test_scraping_service_cleanup_on_errors(self):
        """Test that scraping service cleans up properly after errors"""
        with patch('recipe_discovery_mcp.scraper.get_config'):
            with patch('recipe_discovery_mcp.scraper.scrape_me') as mock_scrape_me:
                service = RecipeScrapingService(max_concurrent=2)
                
                # Mock exception
                mock_scrape_me.side_effect = Exception("Scraping error")
                
                # Make multiple failing requests
                urls = [f"https://example.com/recipe{i}" for i in range(5)]
                results = await service.scrape_batch(urls)
                
                # All should fail
                assert all(not r.success for r in results)
                
                # Cleanup should work
                await service.close()


class TestEdgeCaseScenarios:
    """Test various edge cases and boundary conditions"""
    
    @pytest.mark.asyncio
    async def test_empty_batch_scraping(self):
        """Test batch scraping with empty input"""
        with patch('recipe_discovery_mcp.scraper.get_config'):
            service = RecipeScrapingService()
            
            results = await service.scrape_batch([])
            assert results == []
    
    @pytest.mark.asyncio
    async def test_extremely_large_batch(self):
        """Test handling of extremely large batches"""
        with patch('recipe_discovery_mcp.scraper.get_config'):
            with patch('recipe_discovery_mcp.scraper.scrape_me') as mock_scrape_me:
                service = RecipeScrapingService(max_concurrent=2)
                
                # Mock successful scraper
                mock_scraper = MagicMock()
                mock_scraper.title.return_value = "Test Recipe"
                mock_scraper.ingredients.return_value = ["ingredient1"]
                mock_scraper.instructions.return_value = "Instructions"
                mock_scrape_me.return_value = mock_scraper
                
                # Create large batch (but not huge to avoid test timeout)
                urls = [f"https://example.com/recipe{i}" for i in range(50)]
                
                results = await service.scrape_batch(urls, batch_size=5)
                
                assert len(results) == 50
                assert all(r.success for r in results)
    
    @pytest.mark.asyncio
    async def test_invalid_url_formats(self):
        """Test handling of various invalid URL formats"""
        with patch('recipe_discovery_mcp.scraper.get_config'):
            service = RecipeScrapingService()
            
            invalid_urls = [
                "",
                "not-a-url",
                "ftp://example.com",
                "javascript:alert('test')",
                "mailto:test@example.com",
                "file:///etc/passwd",
                "   ",  # Whitespace
                None    # This would be handled by the calling code
            ]
            
            for url in invalid_urls:
                if url is None:
                    continue  # Skip None as it would cause TypeError
                
                result = await service.scrape_recipe(url)
                # Most should fail, but the service should handle them gracefully
                if not result.success:
                    assert result.error is not None


class TestConcurrencyErrorScenarios:
    """Test error scenarios under concurrent load"""
    
    @pytest.mark.asyncio
    async def test_concurrent_failures_isolation(self):
        """Test that concurrent failures don't affect each other"""
        with patch('recipe_discovery_mcp.scraper.get_config'):
            with patch('recipe_discovery_mcp.scraper.scrape_me') as mock_scrape_me:
                service = RecipeScrapingService(max_concurrent=3)
                
                def mock_scraper_side_effect(url):
                    if "fail" in url:
                        raise Exception(f"Failed: {url}")
                    else:
                        mock_scraper = MagicMock()
                        mock_scraper.title.return_value = f"Recipe: {url}"
                        mock_scraper.ingredients.return_value = ["ingredient"]
                        mock_scraper.instructions.return_value = "instructions"
                        return mock_scraper
                
                mock_scrape_me.side_effect = mock_scraper_side_effect
                
                # Mix of successful and failing URLs
                urls = [
                    "https://example.com/recipe1",
                    "https://example.com/fail1",
                    "https://example.com/recipe2",
                    "https://example.com/fail2",
                    "https://example.com/recipe3"
                ]
                
                # Process concurrently
                tasks = [service.scrape_recipe(url) for url in urls]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Check that exceptions didn't propagate to other tasks
                assert len(results) == 5
                
                success_count = sum(1 for r in results if isinstance(r, RecipeData) and r.success)
                fail_count = sum(1 for r in results if isinstance(r, RecipeData) and not r.success)
                
                assert success_count == 3  # recipe1, recipe2, recipe3
                assert fail_count == 2     # fail1, fail2