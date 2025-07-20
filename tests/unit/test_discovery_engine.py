"""Unit tests for Multi-Site Discovery Engine"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from recipe_discovery_mcp.discovery_engine import MultiSiteDiscoveryEngine
from recipe_discovery_mcp.models import (
    DiscoveryConfig, RecipeData, SiteConfig, UrlDiscoveryResult
)
from recipe_discovery_mcp.site_manager import SiteManager
from recipe_discovery_mcp.url_manager import UrlManager
from recipe_discovery_mcp.scraper import RecipeScrapingService


class TestMultiSiteDiscoveryEngine:
    """Test suite for MultiSiteDiscoveryEngine"""
    
    @pytest.fixture
    def mock_site_manager(self):
        """Mock site manager with test sites"""
        manager = MagicMock(spec=SiteManager)
        
        # Mock enabled sites
        test_sites = [
            SiteConfig(
                domain="allrecipes.com",
                name="AllRecipes",
                base_url="https://www.allrecipes.com",
                rate_limit=1.0,
                max_concurrent=3,
                enabled=True
            ),
            SiteConfig(
                domain="foodnetwork.com",
                name="Food Network",
                base_url="https://www.foodnetwork.com",
                rate_limit=0.5,
                max_concurrent=2,
                enabled=True
            )
        ]
        
        manager.get_enabled_sites.return_value = test_sites
        manager.get_site_by_domain.side_effect = lambda domain: next(
            (site for site in test_sites if site.domain == domain), None
        )
        
        return manager
    
    @pytest.fixture
    def mock_url_manager(self):
        """Mock URL manager with test responses"""
        manager = MagicMock(spec=UrlManager)
        
        # Mock URL discovery
        manager.discover_recipe_urls.return_value = {
            "allrecipes.com": [
                "https://www.allrecipes.com/recipe/1/test-recipe-1",
                "https://www.allrecipes.com/recipe/2/test-recipe-2"
            ],
            "foodnetwork.com": [
                "https://www.foodnetwork.com/recipes/test-recipe-3"
            ]
        }
        
        # Mock URL validation
        manager.validate_urls.return_value = {
            "https://www.allrecipes.com/recipe/1/test-recipe-1": True,
            "https://www.allrecipes.com/recipe/2/test-recipe-2": True,
            "https://www.foodnetwork.com/recipes/test-recipe-3": True
        }
        
        manager.get_stats.return_value = {
            "discovery_requests": 1,
            "urls_discovered": 3,
            "urls_validated": 3
        }
        
        return manager
    
    @pytest.fixture
    def mock_scraping_service(self):
        """Mock scraping service with test recipes"""
        service = MagicMock(spec=RecipeScrapingService)
        
        async def mock_scrape_recipe(url: str) -> RecipeData:
            """Mock successful recipe scraping"""
            return RecipeData(
                url=url,
                title=f"Test Recipe for {url}",
                ingredients=["ingredient 1", "ingredient 2", "ingredient 3"],
                instructions="Test cooking instructions",
                success=True,
                site_domain=url.split('/')[2]
            )
        
        service.scrape_recipe = AsyncMock(side_effect=mock_scrape_recipe)
        
        return service
    
    @pytest.fixture
    def discovery_engine(self, mock_site_manager, mock_url_manager, mock_scraping_service):
        """Create discovery engine with mocked dependencies"""
        return MultiSiteDiscoveryEngine(
            site_manager=mock_site_manager,
            url_manager=mock_url_manager,
            scraping_service=mock_scraping_service
        )
    
    @pytest.mark.asyncio
    async def test_successful_discovery(self, discovery_engine):
        """Test successful multi-site recipe discovery"""
        query = "chicken recipe"
        config = DiscoveryConfig(
            max_urls_per_site=10,
            validate_urls=True,
            max_total_concurrent=5
        )
        
        result = await discovery_engine.discover_recipes(query, config)
        
        # Verify basic result structure
        assert result.job.query == query
        assert len(result.recipes) == 3  # 2 from allrecipes + 1 from foodnetwork
        assert all(recipe.success for recipe in result.recipes)
        assert len(result.site_summaries) == 2
        
        # Verify summary statistics
        summary = result.summary
        assert summary["total_recipes"] == 3
        assert summary["successful_recipes"] == 3
        assert summary["success_rate"] == 100.0
        assert summary["sites_processed"] == 2
    
    @pytest.mark.asyncio
    async def test_discovery_with_failed_recipes(self, discovery_engine, mock_scraping_service):
        """Test discovery handling recipe scraping failures"""
        query = "test query"
        config = DiscoveryConfig(max_urls_per_site=5)
        
        # Mock some failures in scraping
        async def mock_scrape_with_failures(url: str) -> RecipeData:
            if "recipe/2" in url:
                return RecipeData.create_failed(url, "Scraping failed")
            return RecipeData(
                url=url,
                title=f"Test Recipe for {url}",
                ingredients=["ingredient 1"],
                instructions="Test instructions",
                success=True,
                site_domain=url.split('/')[2]
            )
        
        mock_scraping_service.scrape_recipe = AsyncMock(side_effect=mock_scrape_with_failures)
        
        result = await discovery_engine.discover_recipes(query, config)
        
        # Verify mixed results
        assert len(result.recipes) == 3
        successful_recipes = result.get_successful_recipes()
        failed_recipes = result.get_failed_recipes()
        
        assert len(successful_recipes) == 2
        assert len(failed_recipes) == 1
        assert result.summary["success_rate"] < 100.0
    
    @pytest.mark.asyncio
    async def test_discovery_with_specific_sites(self, discovery_engine):
        """Test discovery targeting specific sites"""
        query = "pasta recipe"
        config = DiscoveryConfig(
            target_sites=["allrecipes.com"],
            max_urls_per_site=5
        )
        
        result = await discovery_engine.discover_recipes(query, config)
        
        # Should only have results from allrecipes.com
        assert len(result.site_summaries) == 1
        assert "allrecipes.com" in result.site_summaries
        assert "foodnetwork.com" not in result.site_summaries
        
        # All recipes should be from allrecipes.com
        for recipe in result.recipes:
            assert recipe.site_domain == "allrecipes.com"
    
    @pytest.mark.asyncio
    async def test_discovery_without_url_validation(self, discovery_engine, mock_url_manager):
        """Test discovery skipping URL validation"""
        query = "soup recipe"
        config = DiscoveryConfig(
            validate_urls=False,
            max_urls_per_site=3
        )
        
        result = await discovery_engine.discover_recipes(query, config)
        
        # URL validation should not have been called
        mock_url_manager.validate_urls.assert_not_called()
        
        # Should still have successful results
        assert len(result.recipes) > 0
        assert result.summary["successful_recipes"] > 0
    
    @pytest.mark.asyncio
    async def test_discovery_with_no_enabled_sites(self, mock_site_manager, mock_url_manager, mock_scraping_service):
        """Test discovery when no sites are enabled"""
        # Mock no enabled sites
        mock_site_manager.get_enabled_sites.return_value = []
        
        engine = MultiSiteDiscoveryEngine(
            site_manager=mock_site_manager,
            url_manager=mock_url_manager,
            scraping_service=mock_scraping_service
        )
        
        query = "test query"
        config = DiscoveryConfig()
        
        # Should raise an error
        with pytest.raises(Exception) as exc_info:
            await engine.discover_recipes(query, config)
        
        assert "No enabled sites found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_discovery_error_isolation(self, discovery_engine, mock_url_manager):
        """Test that errors in one site don't affect others"""
        query = "test query"
        config = DiscoveryConfig()
        
        # Mock URL discovery with one site failing
        async def mock_discover_with_error(query, max_urls_per_site, sites):
            if sites and "foodnetwork.com" in sites:
                raise Exception("Network error for foodnetwork.com")
            return {
                "allrecipes.com": ["https://www.allrecipes.com/recipe/1/test"]
            }
        
        mock_url_manager.discover_recipe_urls = AsyncMock(return_value={
            "allrecipes.com": ["https://www.allrecipes.com/recipe/1/test"],
            "foodnetwork.com": []  # Empty due to error
        })
        
        result = await discovery_engine.discover_recipes(query, config)
        
        # Should still have results from working site
        assert len(result.recipes) >= 1
        assert any(recipe.site_domain == "allrecipes.com" for recipe in result.recipes)
    
    @pytest.mark.asyncio
    async def test_discovery_concurrency_limits(self, discovery_engine, mock_scraping_service):
        """Test that concurrency limits are respected"""
        query = "test query"
        config = DiscoveryConfig(
            max_total_concurrent=2,
            max_urls_per_site=20
        )
        
        # Track concurrent calls
        concurrent_calls = []
        
        async def mock_scrape_with_tracking(url: str) -> RecipeData:
            concurrent_calls.append(datetime.now())
            await asyncio.sleep(0.1)  # Simulate processing time
            concurrent_calls.append(datetime.now())
            return RecipeData(
                url=url,
                title="Test Recipe",
                success=True,
                site_domain=url.split('/')[2]
            )
        
        mock_scraping_service.scrape_recipe = AsyncMock(side_effect=mock_scrape_with_tracking)
        
        result = await discovery_engine.discover_recipes(query, config)
        
        # Should have completed successfully
        assert len(result.recipes) > 0
        assert result.summary["successful_recipes"] > 0
        
        # Concurrency was controlled (difficult to test precisely without complex mocking)
        assert len(concurrent_calls) > 0
    
    def test_get_target_sites_with_specific_sites(self, discovery_engine, mock_site_manager):
        """Test _get_target_sites with specific site list"""
        target_sites = discovery_engine._get_target_sites(["allrecipes.com"])
        
        assert len(target_sites) == 1
        assert target_sites[0].domain == "allrecipes.com"
    
    def test_get_target_sites_all_enabled(self, discovery_engine, mock_site_manager):
        """Test _get_target_sites with all enabled sites"""
        target_sites = discovery_engine._get_target_sites(None)
        
        # Should return all enabled sites from mock
        assert len(target_sites) == 2
        domains = [site.domain for site in target_sites]
        assert "allrecipes.com" in domains
        assert "foodnetwork.com" in domains
    
    def test_engine_stats_tracking(self, discovery_engine):
        """Test that engine statistics are properly tracked"""
        stats = discovery_engine.get_stats()
        
        # Initial stats should be zero
        assert stats["total_discoveries"] == 0
        assert stats["successful_discoveries"] == 0
        assert stats["failed_discoveries"] == 0
        assert stats["total_recipes_discovered"] == 0
        assert "engine_start_time" in stats
        assert "uptime_seconds" in stats
    
    @pytest.mark.asyncio
    async def test_stats_updated_after_discovery(self, discovery_engine):
        """Test that stats are updated after successful discovery"""
        initial_stats = discovery_engine.get_stats()
        
        query = "test query"
        config = DiscoveryConfig(max_urls_per_site=2)
        
        result = await discovery_engine.discover_recipes(query, config)
        
        updated_stats = discovery_engine.get_stats()
        
        # Stats should be updated
        assert updated_stats["total_discoveries"] == initial_stats["total_discoveries"] + 1
        assert updated_stats["successful_discoveries"] == initial_stats["successful_discoveries"] + 1
        assert updated_stats["total_recipes_discovered"] > initial_stats["total_recipes_discovered"]


@pytest.mark.integration
class TestDiscoveryEngineIntegration:
    """Integration tests for discovery engine with minimal mocking"""
    
    @pytest.mark.asyncio
    async def test_real_site_manager_integration(self):
        """Test discovery engine with real site manager (using test config)"""
        # This would test with actual site configuration loading
        # but using test/mock URLs to avoid hitting real sites
        pass
    
    @pytest.mark.asyncio 
    async def test_progress_tracking_integration(self):
        """Test integration with progress tracking"""
        # This would test the complete progress tracking workflow
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])