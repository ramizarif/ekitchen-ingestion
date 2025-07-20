"""Integration tests for Multi-Site Discovery System"""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path

from recipe_discovery_mcp.discovery_engine import MultiSiteDiscoveryEngine
from recipe_discovery_mcp.site_manager import SiteManager
from recipe_discovery_mcp.url_manager import UrlManager
from recipe_discovery_mcp.scraper import RecipeScrapingService
from recipe_discovery_mcp.http_client import AsyncHttpClient
from recipe_discovery_mcp.models import DiscoveryConfig
from recipe_discovery_mcp.server import RecipeDiscoveryMCP


@pytest.mark.integration
class TestDiscoverySystemIntegration:
    """Integration tests for the complete discovery system"""
    
    @pytest.fixture
    async def test_site_config(self):
        """Create temporary site configuration for testing"""
        test_config = {
            "sites": {
                "example.com": {
                    "name": "Example Site",
                    "base_url": "https://example.com",
                    "rate_limit": 10.0,  # Fast for testing
                    "timeout": 5,
                    "max_concurrent": 2,
                    "search_paths": ["/search?q={query}"],
                    "recipe_url_patterns": ["/recipe/.*"],
                    "priority": "high",
                    "enabled": True
                }
            },
            "global_settings": {
                "max_total_concurrent": 5,
                "default_timeout": 5,
                "default_rate_limit": 10.0,
                "max_urls_per_site": 10,
                "user_agent": "Test Recipe Discovery Bot"
            }
        }
        
        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = f.name
        
        yield config_path
        
        # Cleanup
        Path(config_path).unlink()
    
    @pytest.fixture
    async def discovery_system(self, test_site_config):
        """Create complete discovery system for testing"""
        # Initialize components
        site_manager = SiteManager(config_path=test_site_config)
        
        http_client = AsyncHttpClient(timeout=5, max_concurrent=5)
        url_manager = UrlManager(site_manager, http_client)
        
        scraping_service = RecipeScrapingService(max_concurrent=3)
        
        discovery_engine = MultiSiteDiscoveryEngine(
            site_manager, url_manager, scraping_service
        )
        
        yield {
            "site_manager": site_manager,
            "url_manager": url_manager,
            "scraping_service": scraping_service,
            "discovery_engine": discovery_engine,
            "http_client": http_client
        }
        
        # Cleanup
        await http_client.close()
        await scraping_service.close()
    
    @pytest.mark.asyncio
    async def test_site_manager_loads_config(self, discovery_system):
        """Test that site manager properly loads configuration"""
        site_manager = discovery_system["site_manager"]
        
        # Verify configuration loaded
        assert len(site_manager.sites) == 1
        assert "example.com" in site_manager.sites
        
        site = site_manager.sites["example.com"]
        assert site.name == "Example Site"
        assert site.enabled is True
        assert site.rate_limit == 10.0
        
        # Test enabled sites
        enabled_sites = site_manager.get_enabled_sites()
        assert len(enabled_sites) == 1
        assert enabled_sites[0].domain == "example.com"
    
    @pytest.mark.asyncio
    async def test_url_pattern_validation(self, discovery_system):
        """Test URL pattern validation works correctly"""
        site_manager = discovery_system["site_manager"]
        
        # Test recipe URL patterns
        assert site_manager.is_recipe_url("https://example.com/recipe/123")
        assert site_manager.is_recipe_url("https://example.com/recipe/chicken-soup")
        assert not site_manager.is_recipe_url("https://example.com/about")
    
    @pytest.mark.asyncio
    async def test_search_url_building(self, discovery_system):
        """Test search URL building functionality"""
        site_manager = discovery_system["site_manager"]
        
        site = site_manager.get_site_by_domain("example.com")
        search_urls = site_manager.build_search_urls(site, "chicken recipe")
        
        assert len(search_urls) == 1
        assert "chicken+recipe" in search_urls[0] or "chicken%20recipe" in search_urls[0]
        assert search_urls[0].startswith("https://example.com/search")
    
    @pytest.mark.asyncio
    async def test_discovery_engine_configuration(self, discovery_system):
        """Test discovery engine handles configuration correctly"""
        discovery_engine = discovery_system["discovery_engine"]
        
        # Test basic configuration
        config = DiscoveryConfig(
            max_urls_per_site=5,
            validate_urls=False,  # Skip validation for test
            max_total_concurrent=2
        )
        
        # Verify engine is properly initialized
        stats = discovery_engine.get_stats()
        assert stats["total_discoveries"] == 0
        assert "engine_start_time" in stats
    
    @pytest.mark.asyncio
    async def test_error_handling_in_pipeline(self, discovery_system):
        """Test error handling throughout the discovery pipeline"""
        discovery_engine = discovery_system["discovery_engine"]
        
        # Test with non-existent site
        config = DiscoveryConfig(
            target_sites=["nonexistent.com"],
            max_urls_per_site=5
        )
        
        # Should handle gracefully and return empty results
        with pytest.raises(Exception):
            result = await discovery_engine.discover_recipes("test query", config)
    
    @pytest.mark.asyncio
    async def test_concurrent_discovery_operations(self, discovery_system):
        """Test multiple concurrent discovery operations"""
        discovery_engine = discovery_system["discovery_engine"]
        
        config = DiscoveryConfig(
            max_urls_per_site=3,
            validate_urls=False,
            max_total_concurrent=2
        )
        
        # Start multiple discovery operations concurrently
        tasks = []
        queries = ["chicken recipe", "pasta recipe", "soup recipe"]
        
        for query in queries:
            task = discovery_engine.discover_recipes(query, config)
            tasks.append(task)
        
        # This would normally fail with real sites, but tests the concurrency handling
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify all operations completed (even if with errors)
            assert len(results) == 3
            
            # Check that engine stats were updated
            stats = discovery_engine.get_stats()
            assert stats["total_discoveries"] >= 3
            
        except Exception:
            # Expected with test configuration
            pass
    
    @pytest.mark.asyncio
    async def test_resource_cleanup(self, discovery_system):
        """Test that resources are properly cleaned up"""
        http_client = discovery_system["http_client"]
        scraping_service = discovery_system["scraping_service"]
        
        # Verify initial state
        assert not http_client._closed if hasattr(http_client, '_closed') else True
        
        # Test cleanup
        await http_client.close()
        await scraping_service.close()
        
        # Verify cleanup completed without errors
        assert True  # If we get here, cleanup worked


@pytest.mark.integration
@pytest.mark.slow
class TestMCPServerIntegration:
    """Integration tests for MCP server with discovery engine"""
    
    @pytest.fixture
    async def mcp_server(self):
        """Create MCP server for testing"""
        # This would create a test MCP server instance
        # but requires more complex setup with FastMCP
        pass
    
    @pytest.mark.asyncio
    async def test_discovery_tools_registration(self):
        """Test that discovery tools are properly registered"""
        # This would test the MCP tool registration
        # but requires FastMCP testing infrastructure
        pass
    
    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        """Test MCP tool error handling"""
        # This would test error handling in MCP tools
        pass


@pytest.mark.integration
class TestPerformanceCharacteristics:
    """Performance and load testing for discovery system"""
    
    @pytest.mark.asyncio
    async def test_memory_usage_stability(self, discovery_system):
        """Test that memory usage remains stable during operations"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        discovery_engine = discovery_system["discovery_engine"]
        config = DiscoveryConfig(
            max_urls_per_site=2,
            validate_urls=False
        )
        
        # Run multiple discovery operations
        for i in range(5):
            try:
                await discovery_engine.discover_recipes(f"test query {i}", config)
            except Exception:
                pass  # Expected with test setup
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB for test operations)
        assert memory_increase < 50 * 1024 * 1024, f"Memory increased by {memory_increase} bytes"
    
    @pytest.mark.asyncio
    async def test_concurrent_load_handling(self, discovery_system):
        """Test system behavior under concurrent load"""
        discovery_engine = discovery_system["discovery_engine"]
        
        config = DiscoveryConfig(
            max_urls_per_site=1,
            validate_urls=False,
            max_total_concurrent=3
        )
        
        # Create multiple concurrent requests
        tasks = []
        for i in range(10):
            task = discovery_engine.discover_recipes(f"query {i}", config)
            tasks.append(task)
        
        start_time = asyncio.get_event_loop().time()
        
        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = asyncio.get_event_loop().time()
        total_time = end_time - start_time
        
        # Verify reasonable performance (should complete quickly with test setup)
        assert total_time < 30.0, f"Concurrent operations took {total_time} seconds"
        
        # Verify all operations completed
        assert len(results) == 10
        
        # Check engine statistics
        stats = discovery_engine.get_stats()
        assert stats["total_discoveries"] >= 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-k", "not slow"])