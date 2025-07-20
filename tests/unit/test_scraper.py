"""Unit tests for Recipe Scraping Service

Tests the core scraping functionality with mocked external dependencies
to ensure reliable, fast unit tests.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from recipe_discovery_mcp.scraper import RecipeScrapingService
from recipe_discovery_mcp.models import RecipeData, ScrapingStatus
from recipe_discovery_mcp.config import Config


class TestRecipeScrapingService:
    """Test suite for RecipeScrapingService"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing"""
        config = MagicMock(spec=Config)
        config.max_concurrent_requests = 5
        config.request_timeout = 30
        config.requests_per_second = 2.0
        config.max_retries = 3
        config.user_agent = "Test Bot"
        return config
    
    @pytest.fixture
    def scraping_service(self, mock_config):
        """Create scraping service with mocked dependencies"""
        with patch('recipe_discovery_mcp.scraper.get_config', return_value=mock_config):
            with patch('recipe_discovery_mcp.scraper.scrape_me') as mock_scrape_me:
                service = RecipeScrapingService(max_concurrent=5)
                service.mock_scrape_me = mock_scrape_me
                return service
    
    def create_mock_scraper(self, **kwargs):
        """Create a mock scraper object with configurable return values"""
        mock_scraper = MagicMock()
        
        # Default values
        defaults = {
            'title': 'Test Recipe',
            'ingredients': ['1 cup flour', '2 eggs', '1 cup milk'],
            'instructions': 'Mix ingredients and bake at 350°F for 30 minutes.',
            'total_time': 45,
            'prep_time': 15,
            'cook_time': 30,
            'yields': '4 servings',
            'image': 'https://example.com/image.jpg',
            'description': 'A delicious test recipe',
            'author': 'Test Chef',
            'cuisine': 'Test Cuisine',
            'category': 'Test Category'
        }
        
        # Update with provided kwargs
        defaults.update(kwargs)
        
        # Configure mock methods
        for key, value in defaults.items():
            if key == 'image':
                setattr(mock_scraper, key, MagicMock(return_value=value))
            else:
                setattr(mock_scraper, key, MagicMock(return_value=value))
        
        return mock_scraper
    
    @pytest.mark.asyncio
    async def test_scrape_single_recipe_success(self, scraping_service):
        """Test successful single recipe scraping"""
        # Setup mock
        mock_scraper = self.create_mock_scraper()
        scraping_service.mock_scrape_me.return_value = mock_scraper
        
        # Test
        result = await scraping_service.scrape_recipe("https://example.com/recipe")
        
        # Assertions
        assert result.success
        assert result.status == ScrapingStatus.SUCCESS
        assert result.title == "Test Recipe"
        assert len(result.ingredients) == 3
        assert result.total_time == 45
        assert result.site_domain == "example.com"
        assert result.ingredient_count == 3
        assert result.has_timing
        assert result.has_image
        
        # Verify mock was called
        scraping_service.mock_scrape_me.assert_called_once_with("https://example.com/recipe")
    
    @pytest.mark.asyncio
    async def test_scrape_single_recipe_failure(self, scraping_service):
        """Test handling of scraping failures"""
        # Setup mock to raise exception
        scraping_service.mock_scrape_me.side_effect = Exception("Network error")
        
        # Test
        result = await scraping_service.scrape_recipe("https://example.com/recipe")
        
        # Assertions
        assert not result.success
        assert result.status == ScrapingStatus.FAILED
        assert "Network error" in result.error
        assert result.title is None
        assert len(result.ingredients) == 0
    
    @pytest.mark.asyncio
    async def test_scrape_recipe_invalid_data(self, scraping_service):
        """Test handling of recipes with missing essential data"""
        # Setup mock with incomplete data
        mock_scraper = self.create_mock_scraper(
            title=None,  # Missing title
            ingredients=[]  # No ingredients
        )
        scraping_service.mock_scrape_me.return_value = mock_scraper
        
        # Test
        result = await scraping_service.scrape_recipe("https://example.com/recipe")
        
        # Assertions
        assert not result.success
        assert "No title or ingredients found" in result.error
        assert not result.is_valid_recipe()
    
    @pytest.mark.asyncio
    async def test_scrape_batch_success(self, scraping_service):
        """Test successful batch scraping"""
        # Setup mock
        mock_scraper = self.create_mock_scraper()
        scraping_service.mock_scrape_me.return_value = mock_scraper
        
        urls = [
            "https://example.com/recipe1",
            "https://example.com/recipe2",
            "https://example.com/recipe3"
        ]
        
        # Test
        results = await scraping_service.scrape_batch(urls)
        
        # Assertions
        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.title == "Test Recipe" for r in results)
        
        # Verify all URLs were processed
        call_args = [call[0][0] for call in scraping_service.mock_scrape_me.call_args_list]
        assert set(call_args) == set(urls)
    
    @pytest.mark.asyncio
    async def test_scrape_batch_mixed_results(self, scraping_service):
        """Test batch scraping with mixed success/failure"""
        def mock_scraper_side_effect(url):
            if "fail" in url:
                raise Exception("Simulated failure")
            return self.create_mock_scraper()
        
        scraping_service.mock_scrape_me.side_effect = mock_scraper_side_effect
        
        urls = [
            "https://example.com/recipe1",
            "https://example.com/recipe-fail",
            "https://example.com/recipe3"
        ]
        
        # Test
        results = await scraping_service.scrape_batch(urls)
        
        # Assertions
        assert len(results) == 3
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        
        assert len(successful_results) == 2
        assert len(failed_results) == 1
        assert "Simulated failure" in failed_results[0].error
    
    @pytest.mark.asyncio
    async def test_scrape_batch_empty_list(self, scraping_service):
        """Test batch scraping with empty URL list"""
        results = await scraping_service.scrape_batch([])
        assert results == []
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, scraping_service):
        """Test that rate limiting is applied during scraping"""
        # Setup mock
        mock_scraper = self.create_mock_scraper()
        scraping_service.mock_scrape_me.return_value = mock_scraper
        
        # Test multiple requests to same domain
        urls = [
            "https://example.com/recipe1",
            "https://example.com/recipe2"
        ]
        
        start_time = asyncio.get_event_loop().time()
        results = await scraping_service.scrape_batch(urls, batch_size=1)
        end_time = asyncio.get_event_loop().time()
        
        # Should take at least the rate limit interval
        # With 2 req/sec rate limit, should take at least 0.5 seconds
        assert end_time - start_time >= 0.4  # Allow some tolerance
        assert len(results) == 2
        assert all(r.success for r in results)
    
    @pytest.mark.asyncio
    async def test_concurrent_request_limiting(self, scraping_service):
        """Test that concurrent requests are properly limited"""
        mock_scraper = self.create_mock_scraper()
        scraping_service.mock_scrape_me.return_value = mock_scraper
        
        # Create more URLs than max_concurrent
        urls = [f"https://example{i}.com/recipe" for i in range(10)]
        
        # Test - should not fail despite more URLs than concurrent limit
        results = await scraping_service.scrape_batch(urls)
        
        assert len(results) == 10
        assert all(r.success for r in results)
    
    @pytest.mark.asyncio
    async def test_statistics_tracking(self, scraping_service):
        """Test that service statistics are properly tracked"""
        # Initial stats
        initial_stats = scraping_service.get_stats()
        assert initial_stats["total_requests"] == 0
        assert initial_stats["successful_requests"] == 0
        assert initial_stats["failed_requests"] == 0
        
        # Setup mock for success
        mock_scraper = self.create_mock_scraper()
        scraping_service.mock_scrape_me.return_value = mock_scraper
        
        # Make successful request
        await scraping_service.scrape_recipe("https://example.com/recipe")
        
        # Check stats updated
        stats = scraping_service.get_stats()
        assert stats["total_requests"] == 1
        assert stats["successful_requests"] == 1
        assert stats["failed_requests"] == 0
        
        # Setup mock for failure
        scraping_service.mock_scrape_me.side_effect = Exception("Test error")
        
        # Make failing request
        await scraping_service.scrape_recipe("https://example.com/recipe2")
        
        # Check stats updated
        final_stats = scraping_service.get_stats()
        assert final_stats["total_requests"] == 2
        assert final_stats["successful_requests"] == 1
        assert final_stats["failed_requests"] == 1
        assert final_stats["success_rate"] == 50.0
    
    @pytest.mark.asyncio
    async def test_service_cleanup(self, scraping_service):
        """Test proper resource cleanup"""
        # Mock the HTTP client close method
        scraping_service.http_client.close = AsyncMock()
        
        # Test cleanup
        await scraping_service.close()
        
        # Verify cleanup was called
        scraping_service.http_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_test_scraping_service(self, scraping_service):
        """Test the built-in service test functionality"""
        # Setup mock
        mock_scraper = self.create_mock_scraper()
        scraping_service.mock_scrape_me.return_value = mock_scraper
        
        # Test
        test_results = await scraping_service.test_scraping_service()
        
        # Assertions
        assert test_results["service_status"] == "operational"
        assert "test_summary" in test_results
        assert test_results["test_summary"]["total_tests"] > 0
        assert test_results["test_summary"]["successful"] > 0
        assert len(test_results["successful_recipes"]) > 0


class TestRecipeDataModel:
    """Test suite for RecipeData model"""
    
    def test_recipe_data_creation_success(self):
        """Test creating a successful RecipeData instance"""
        recipe = RecipeData(
            url="https://example.com/recipe",
            title="Test Recipe",
            ingredients=["1 cup flour", "2 eggs"],
            instructions="Mix and bake",
            total_time=30
        )
        
        assert recipe.success
        assert recipe.status == ScrapingStatus.SUCCESS
        assert recipe.site_domain == "example.com"
        assert recipe.ingredient_count == 2
        assert recipe.has_timing
        assert not recipe.has_image  # No image URL provided
        assert recipe.is_valid_recipe()
    
    def test_recipe_data_quality_score(self):
        """Test recipe quality scoring"""
        # High quality recipe
        high_quality = RecipeData(
            url="https://example.com/recipe",
            title="Delicious Test Recipe",
            ingredients=["1 cup flour", "2 eggs", "1 cup milk", "1 tsp salt", "2 tbsp sugar"],
            instructions="Mix all ingredients thoroughly. Bake at 350°F for 30 minutes until golden brown. Let cool before serving.",
            total_time=45,
            image_url="https://example.com/image.jpg",
            yields="4 servings",
            description="A wonderful recipe for testing"
        )
        
        # Low quality recipe
        low_quality = RecipeData(
            url="https://example.com/recipe",
            title="Recipe",
            ingredients=["flour"],
            instructions="Mix"
        )
        
        assert high_quality.get_quality_score() > 0.8
        assert low_quality.get_quality_score() < 0.3
    
    def test_recipe_data_failed_creation(self):
        """Test creating a failed RecipeData instance"""
        failed_recipe = RecipeData.create_failed(
            "https://example.com/recipe",
            "Network timeout",
            ScrapingStatus.TIMEOUT
        )
        
        assert not failed_recipe.success
        assert failed_recipe.status == ScrapingStatus.TIMEOUT
        assert failed_recipe.error == "Network timeout"
        assert not failed_recipe.is_valid_recipe()
    
    def test_recipe_data_validation(self):
        """Test automatic field validation"""
        recipe = RecipeData(
            url="https://example.com/recipe",
            ingredients=["ingredient1", "ingredient2", "ingredient3"],
            instructions="This is a longer instruction that should pass the length check for validity.",
            image_url="https://example.com/image.jpg",
            total_time=30
        )
        
        # Check automatic calculations
        assert recipe.ingredient_count == 3
        assert recipe.instruction_length > 50
        assert recipe.has_image
        assert recipe.has_timing
        assert recipe.site_domain == "example.com"
    
    def test_recipe_data_summary(self):
        """Test recipe summary generation"""
        recipe = RecipeData(
            url="https://example.com/recipe",
            title="Test Recipe",
            ingredients=["ingredient1", "ingredient2"],
            instructions="Test instructions",
            image_url="https://example.com/image.jpg"
        )
        
        summary = recipe.get_summary()
        
        assert summary["url"] == recipe.url
        assert summary["title"] == recipe.title
        assert summary["ingredients_count"] == 2
        assert summary["has_image"]
        assert "quality_score" in summary
        assert "is_valid" in summary
        assert "scraped_at" in summary