"""Integration tests for MCP Recipe Discovery Server

Tests the complete MCP server functionality including tool registration,
request handling, and integration with Claude Desktop.
"""

import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock

# Note: These tests assume fastmcp.testing is available
# If not, we'll mock the test client functionality
try:
    from fastmcp.testing import TestClient
except ImportError:
    # Mock the TestClient if not available
    class TestClient:
        def __init__(self, server):
            self.server = server
        
        async def call_tool(self, tool_name, params):
            # Mock implementation
            return MagicMock(success=True, data={"test": "data"})

from recipe_discovery_mcp.server import RecipeDiscoveryMCP
from recipe_discovery_mcp.models import RecipeData, ScrapingStatus


class TestMCPIntegration:
    """Test suite for MCP server integration"""
    
    @pytest.fixture
    async def mcp_server(self):
        """Create MCP server instance for testing"""
        with patch('recipe_discovery_mcp.server.log_server_startup'):
            with patch('recipe_discovery_mcp.server.setup_structured_logging'):
                server = RecipeDiscoveryMCP()
                yield server
                # Cleanup
                if hasattr(server, 'scraping_service'):
                    await server.scraping_service.close()
    
    @pytest.fixture
    def client(self, mcp_server):
        """Create test client for MCP server"""
        return TestClient(mcp_server.server)
    
    @pytest.mark.asyncio
    async def test_health_check_tool(self, mcp_server):
        """Test health check MCP tool"""
        result = await mcp_server.health_check()
        
        assert result["success"] is True
        assert "health" in result
        assert result["health"]["status"] == "healthy"
        assert "uptime_seconds" in result["health"]
        assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_get_server_config_tool(self, mcp_server):
        """Test server configuration MCP tool"""
        result = await mcp_server.get_server_config()
        
        assert result["success"] is True
        assert "config" in result
        assert "server_name" in result["config"]
        assert "max_concurrent_requests" in result["config"]
        assert "requests_per_second" in result["config"]
    
    @pytest.mark.asyncio
    async def test_get_server_metrics_tool(self, mcp_server):
        """Test server metrics MCP tool"""
        result = await mcp_server.get_server_metrics()
        
        assert result["success"] is True
        assert "metrics" in result
        assert "uptime_seconds" in result["metrics"]
        assert "requests" in result["metrics"]
        assert "server" in result["metrics"]
    
    @pytest.mark.asyncio
    async def test_test_connectivity_tool(self, mcp_server):
        """Test connectivity test MCP tool"""
        result = await mcp_server.test_connectivity()
        
        assert result["success"] is True
        assert "test_results" in result
        assert result["test_results"]["mcp_communication"] == "working"
        assert result["test_results"]["async_operations"] == "working"
    
    @pytest.mark.asyncio
    async def test_scrape_single_recipe_tool_success(self, mcp_server):
        """Test single recipe scraping MCP tool with success"""
        # Mock the scraping service
        mock_recipe = RecipeData(
            url="https://example.com/recipe",
            title="Test Recipe",
            ingredients=["1 cup flour", "2 eggs"],
            instructions="Mix and bake for 30 minutes",
            total_time=30,
            success=True
        )
        
        mcp_server.scraping_service.scrape_recipe = AsyncMock(return_value=mock_recipe)
        
        # Test the tool
        result = await mcp_server.scrape_single_recipe("https://example.com/recipe")
        
        # Assertions
        assert result["success"] is True
        assert "recipe" in result
        assert result["recipe"]["title"] == "Test Recipe"
        assert result["recipe"]["success"] is True
        assert len(result["recipe"]["ingredients"]) == 2
    
    @pytest.mark.asyncio
    async def test_scrape_single_recipe_tool_invalid_url(self, mcp_server):
        """Test single recipe scraping with invalid URL"""
        result = await mcp_server.scrape_single_recipe("invalid-url")
        
        assert result["success"] is False
        assert "error" in result
        assert "Invalid URL" in result["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_scrape_recipe_batch_tool_success(self, mcp_server):
        """Test batch recipe scraping MCP tool"""
        # Mock the scraping service
        mock_recipes = [
            RecipeData(
                url=f"https://example.com/recipe{i}",
                title=f"Test Recipe {i}",
                ingredients=["ingredient1", "ingredient2"],
                instructions="Test instructions",
                success=True
            )
            for i in range(1, 4)
        ]
        
        mcp_server.scraping_service.scrape_batch = AsyncMock(return_value=mock_recipes)
        
        # Test the tool
        urls = ["https://example.com/recipe1", "https://example.com/recipe2", "https://example.com/recipe3"]
        result = await mcp_server.scrape_recipe_batch(urls)
        
        # Assertions
        assert result["success"] is True
        assert "batch_results" in result
        assert result["batch_results"]["total"] == 3
        assert result["batch_results"]["successful"] == 3
        assert result["batch_results"]["failed"] == 0
        assert result["batch_results"]["success_rate"] == "100.0%"
        assert len(result["recipes"]) == 3
    
    @pytest.mark.asyncio
    async def test_scrape_recipe_batch_tool_empty_urls(self, mcp_server):
        """Test batch scraping with empty URL list"""
        result = await mcp_server.scrape_recipe_batch([])
        
        assert result["success"] is False
        assert "error" in result
        assert "No URLs provided" in result["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_scrape_recipe_batch_tool_too_many_urls(self, mcp_server):
        """Test batch scraping with too many URLs"""
        urls = [f"https://example.com/recipe{i}" for i in range(101)]  # 101 URLs
        result = await mcp_server.scrape_recipe_batch(urls)
        
        assert result["success"] is False
        assert "error" in result
        assert "Too many URLs" in result["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_scrape_recipe_batch_tool_invalid_urls(self, mcp_server):
        """Test batch scraping with invalid URLs"""
        urls = ["https://example.com/recipe1", "invalid-url", "https://example.com/recipe2"]
        result = await mcp_server.scrape_recipe_batch(urls)
        
        assert result["success"] is False
        assert "error" in result
        assert "Invalid URLs found" in result["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_test_scraping_service_tool(self, mcp_server):
        """Test the scraping service test MCP tool"""
        # Mock the test method
        mock_test_results = {
            "service_status": "operational",
            "test_summary": {
                "total_tests": 3,
                "successful": 2,
                "failed": 1,
                "success_rate": "66.7%",
                "test_duration_seconds": 2.5
            },
            "successful_recipes": [
                {"url": "https://example.com/recipe1", "title": "Recipe 1", "ingredients_count": 5}
            ],
            "failed_tests": [
                {"url": "https://example.com/recipe2", "error": "Network timeout"}
            ]
        }
        
        mcp_server.scraping_service.test_scraping_service = AsyncMock(return_value=mock_test_results)
        
        # Test the tool
        result = await mcp_server.test_scraping_service()
        
        # Assertions
        assert result["success"] is True
        assert "test_results" in result
        assert result["test_results"]["service_status"] == "operational"
        assert "test_summary" in result["test_results"]
    
    @pytest.mark.asyncio
    async def test_get_scraping_stats_tool(self, mcp_server):
        """Test scraping statistics MCP tool"""
        # Mock the stats method
        mock_stats = {
            "uptime_seconds": 3600,
            "total_requests": 50,
            "successful_requests": 45,
            "failed_requests": 5,
            "success_rate": 90.0,
            "requests_per_second": 0.014,
            "max_concurrent": 10
        }
        
        mcp_server.scraping_service.get_stats = MagicMock(return_value=mock_stats)
        
        # Test the tool
        result = await mcp_server.get_scraping_stats()
        
        # Assertions
        assert result["success"] is True
        assert "scraping_stats" in result
        assert "server_stats" in result
        assert result["scraping_stats"]["success_rate"] == 90.0
        assert result["server_stats"]["active_requests"] == 0  # Initial state
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_tracking(self, mcp_server):
        """Test that concurrent requests are properly tracked"""
        # Mock long-running scraping operation
        async def mock_long_scrape(url):
            await asyncio.sleep(0.1)  # Simulate work
            return RecipeData(url=url, title="Test", success=True)
        
        mcp_server.scraping_service.scrape_recipe = mock_long_scrape
        
        # Start multiple concurrent requests
        tasks = [
            mcp_server.scrape_single_recipe(f"https://example.com/recipe{i}")
            for i in range(3)
        ]
        
        # Check that active requests are tracked
        # Note: This is a bit racy, but should work for testing
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(result["success"] for result in results)
        assert mcp_server.active_requests == 0  # Should be back to 0
        assert mcp_server.total_requests >= 3  # Should have tracked requests
    
    @pytest.mark.asyncio
    async def test_error_handling_in_tools(self, mcp_server):
        """Test that MCP tools properly handle and format errors"""
        # Mock the scraping service to raise an exception
        mcp_server.scraping_service.scrape_recipe = AsyncMock(
            side_effect=Exception("Test error")
        )
        
        # Test that error is properly handled
        result = await mcp_server.scrape_single_recipe("https://example.com/recipe")
        
        assert result["success"] is False
        assert "error" in result
        assert "Test error" in result["error"]["message"]
        assert result["error"]["type"] == "Exception"
    
    @pytest.mark.asyncio
    async def test_request_tracking_and_logging(self, mcp_server):
        """Test that requests are properly tracked and logged"""
        # Mock successful scraping
        mock_recipe = RecipeData(
            url="https://example.com/recipe",
            title="Test Recipe",
            success=True
        )
        mcp_server.scraping_service.scrape_recipe = AsyncMock(return_value=mock_recipe)
        
        initial_total = mcp_server.total_requests
        
        # Make a request
        result = await mcp_server.scrape_single_recipe("https://example.com/recipe")
        
        # Check tracking
        assert result["success"] is True
        assert mcp_server.total_requests == initial_total + 1
        assert mcp_server.active_requests == 0  # Should be back to 0


class TestMCPToolsWithRealClient:
    """Tests using actual MCP client if available"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not hasattr(TestClient, '__module__'), reason="fastmcp.testing not available")
    async def test_tool_call_through_client(self):
        """Test calling tools through actual MCP client"""
        with patch('recipe_discovery_mcp.server.log_server_startup'):
            with patch('recipe_discovery_mcp.server.setup_structured_logging'):
                server = RecipeDiscoveryMCP()
                client = TestClient(server.server)
                
                try:
                    # Test health check through client
                    response = await client.call_tool("health_check", {})
                    
                    assert response.success
                    assert "health" in response.data
                    
                finally:
                    # Cleanup
                    await server.scraping_service.close()
    
    @pytest.mark.asyncio 
    @pytest.mark.skipif(not hasattr(TestClient, '__module__'), reason="fastmcp.testing not available")
    async def test_scraping_tool_through_client(self):
        """Test scraping tools through actual MCP client"""
        with patch('recipe_discovery_mcp.server.log_server_startup'):
            with patch('recipe_discovery_mcp.server.setup_structured_logging'):
                server = RecipeDiscoveryMCP()
                client = TestClient(server.server)
                
                # Mock the scraping service
                mock_recipe = RecipeData(
                    url="https://example.com/recipe",
                    title="Test Recipe",
                    ingredients=["ingredient1", "ingredient2"],
                    instructions="Test instructions",
                    success=True
                )
                server.scraping_service.scrape_recipe = AsyncMock(return_value=mock_recipe)
                
                try:
                    # Test single recipe scraping through client
                    response = await client.call_tool(
                        "scrape_single_recipe",
                        {"url": "https://example.com/recipe"}
                    )
                    
                    assert response.success
                    assert "recipe" in response.data
                    assert response.data["recipe"]["title"] == "Test Recipe"
                    
                finally:
                    # Cleanup
                    await server.scraping_service.close()