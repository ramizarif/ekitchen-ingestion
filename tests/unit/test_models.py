"""Unit tests for Recipe Discovery MCP data models"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from recipe_discovery_mcp.models import (
    RecipeData,
    ScrapingRequest,
    ScrapingResponse,
    ServerHealth
)


class TestRecipeData:
    """Test RecipeData model functionality"""
    
    def test_minimal_recipe_data(self):
        """Test creating recipe data with minimal required fields"""
        recipe = RecipeData(url="https://example.com/recipe")
        
        assert recipe.url == "https://example.com/recipe"
        assert recipe.success is True
        assert recipe.ingredients == []
        assert recipe.instructions == ""
        assert isinstance(recipe.scraped_at, datetime)
    
    def test_complete_recipe_data(self):
        """Test creating recipe data with all fields"""
        recipe = RecipeData(
            url="https://example.com/recipe",
            title="Test Recipe",
            ingredients=["1 cup flour", "2 eggs"],
            instructions="Mix and bake",
            total_time=30,
            yields="4 servings",
            prep_time=10,
            cook_time=20
        )
        
        assert recipe.title == "Test Recipe"
        assert len(recipe.ingredients) == 2
        assert recipe.total_time == 30
        assert recipe.yields == "4 servings"
    
    def test_failed_recipe_creation(self):
        """Test creating failed recipe data"""
        recipe = RecipeData.create_failed(
            url="https://example.com/failed",
            error="Connection timeout"
        )
        
        assert recipe.url == "https://example.com/failed"
        assert recipe.success is False
        assert recipe.error == "Connection timeout"
    
    def test_recipe_serialization(self):
        """Test recipe data JSON serialization"""
        recipe = RecipeData(
            url="https://example.com/recipe",
            title="Test Recipe",
            ingredients=["flour", "eggs"]
        )
        
        json_data = recipe.to_json()
        
        assert isinstance(json_data, dict)
        assert json_data["url"] == "https://example.com/recipe"
        assert json_data["title"] == "Test Recipe"
        assert "scraped_at" in json_data


class TestScrapingRequest:
    """Test ScrapingRequest model functionality"""
    
    def test_minimal_scraping_request(self):
        """Test creating scraping request with minimal fields"""
        request = ScrapingRequest(urls=["https://example.com/recipe"])
        
        assert len(request.urls) == 1
        assert request.batch_size == 10  # default
        assert request.timeout == 30  # default
        assert request.retry_failed is True  # default
    
    def test_custom_scraping_request(self):
        """Test creating scraping request with custom settings"""
        request = ScrapingRequest(
            urls=["https://example1.com", "https://example2.com"],
            batch_size=5,
            timeout=60,
            retry_failed=False
        )
        
        assert len(request.urls) == 2
        assert request.batch_size == 5
        assert request.timeout == 60
        assert request.retry_failed is False
    
    def test_empty_urls_validation(self):
        """Test validation with empty URL list"""
        with pytest.raises(ValidationError):
            ScrapingRequest(urls=[])


class TestScrapingResponse:
    """Test ScrapingResponse model functionality"""
    
    def test_scraping_response_creation(self):
        """Test creating scraping response"""
        recipes = [
            RecipeData(url="https://example.com/recipe1"),
            RecipeData.create_failed("https://example.com/recipe2", "Error")
        ]
        
        response = ScrapingResponse(
            total_requested=2,
            successful=1,
            failed=1,
            recipes=recipes,
            processing_time=5.5
        )
        
        assert response.total_requested == 2
        assert response.successful == 1
        assert response.failed == 1
        assert len(response.recipes) == 2
        assert response.processing_time == 5.5
    
    def test_success_rate_calculation(self):
        """Test success rate calculation"""
        # 100% success rate
        response = ScrapingResponse(
            total_requested=2,
            successful=2,
            failed=0,
            recipes=[],
            processing_time=1.0
        )
        assert response.success_rate == 100.0
        
        # 50% success rate
        response.successful = 1
        response.failed = 1
        assert response.success_rate == 50.0
        
        # 0% success rate
        response.successful = 0
        response.failed = 2
        assert response.success_rate == 0.0
        
        # Zero total (edge case)
        response.total_requested = 0
        assert response.success_rate == 0.0


class TestServerHealth:
    """Test ServerHealth model functionality"""
    
    def test_server_health_creation(self):
        """Test creating server health status"""
        health = ServerHealth(
            status="healthy",
            uptime_seconds=3600.5,
            active_requests=3,
            total_requests=100,
            success_rate=95.5
        )
        
        assert health.status == "healthy"
        assert health.uptime_seconds == 3600.5
        assert health.active_requests == 3
        assert health.total_requests == 100
        assert health.success_rate == 95.5
        assert isinstance(health.timestamp, datetime)
        assert health.version == "0.1.0"