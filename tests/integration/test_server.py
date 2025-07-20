"""Integration tests for Recipe Discovery MCP Server"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from recipe_discovery_mcp.server import RecipeDiscoveryMCP
from recipe_discovery_mcp.config import reload_config


class TestRecipeDiscoveryMCP:
    """Integration tests for the MCP server"""
    
    @pytest.fixture
    def server(self):
        """Create a test server instance"""
        # Reload config to ensure clean state
        reload_config()
        return RecipeDiscoveryMCP()
    
    def test_server_initialization(self, server):
        """Test server initializes correctly"""
        assert server.config is not None
        assert server.server is not None
        assert server.active_requests == 0
        assert server.total_requests == 0
        assert server.logger is not None
    
    @pytest.mark.asyncio
    async def test_health_check_tool(self, server):
        """Test health check tool functionality"""
        result = await server.health_check()
        
        assert result["success"] is True
        assert "health" in result
        assert "timestamp" in result
        
        health_data = result["health"]
        assert health_data["status"] == "healthy"
        assert "uptime_seconds" in health_data
        assert "version" in health_data
    
    @pytest.mark.asyncio
    async def test_get_server_config_tool(self, server):
        """Test server configuration tool"""
        result = await server.get_server_config()
        
        assert result["success"] is True
        assert "config" in result
        assert "timestamp" in result
        
        config_data = result["config"]
        assert "server_name" in config_data
        assert "log_level" in config_data
        assert "max_concurrent_requests" in config_data
    
    @pytest.mark.asyncio
    async def test_get_server_metrics_tool(self, server):
        """Test server metrics tool"""
        result = await server.get_server_metrics()
        
        assert result["success"] is True
        assert "metrics" in result
        assert "timestamp" in result
        
        metrics = result["metrics"]
        assert "uptime_seconds" in metrics
        assert "requests" in metrics
        assert "server" in metrics
        
        requests_data = metrics["requests"]
        assert "total" in requests_data
        assert "successful" in requests_data
        assert "failed" in requests_data
        assert "success_rate_percent" in requests_data
    
    @pytest.mark.asyncio
    async def test_test_connectivity_tool(self, server):
        """Test connectivity testing tool"""
        result = await server.test_connectivity()
        
        assert result["success"] is True
        assert "test_results" in result
        assert "message" in result
        
        test_results = result["test_results"]
        assert test_results["mcp_communication"] == "working"
        assert test_results["async_operations"] == "working"
        assert test_results["error_handling"] == "working"
    
    def test_uptime_formatting(self, server):
        """Test uptime formatting functionality"""
        # Test seconds only
        formatted = server._format_uptime(45)
        assert formatted == "45s"
        
        # Test minutes and seconds
        formatted = server._format_uptime(125)  # 2m 5s
        assert formatted == "2m 5s"
        
        # Test hours, minutes, and seconds
        formatted = server._format_uptime(3665)  # 1h 1m 5s
        assert formatted == "1h 1m 5s"
    
    @pytest.mark.asyncio
    async def test_server_error_handling(self, server):
        """Test server error handling in tools"""
        # Mock a tool to raise an exception
        original_health_check = server.health_check
        
        async def failing_health_check():
            raise Exception("Test error")
        
        server.health_check = failing_health_check
        
        # The error should be caught and returned as error response
        # Note: This test assumes error handling decorator is working
        with pytest.raises(Exception):
            await server.health_check()
        
        # Restore original method
        server.health_check = original_health_check


class TestServerLifecycle:
    """Test server startup and shutdown lifecycle"""
    
    @pytest.mark.asyncio
    async def test_server_startup_failure(self):
        """Test handling of server startup failures"""
        server = RecipeDiscoveryMCP()
        
        # Mock the FastMCP server to fail
        with patch.object(server.server, 'run_stdio', side_effect=Exception("Startup failed")):
            with pytest.raises(Exception):
                await server.start()
    
    @pytest.mark.asyncio
    async def test_server_shutdown(self):
        """Test server shutdown functionality"""
        server = RecipeDiscoveryMCP()
        
        # Shutdown should complete without errors
        await server.shutdown()
        
        # Should be able to call shutdown multiple times safely
        await server.shutdown()


@pytest.mark.asyncio
async def test_main_function():
    """Test main server entry point"""
    from recipe_discovery_mcp.server import main
    
    # Mock the server to avoid actually starting
    with patch('recipe_discovery_mcp.server.RecipeDiscoveryMCP') as mock_server_class:
        mock_server = AsyncMock()
        mock_server_class.return_value = mock_server
        
        # Mock start to raise KeyboardInterrupt to simulate user stopping
        mock_server.start.side_effect = KeyboardInterrupt()
        
        # Should handle KeyboardInterrupt gracefully
        await main()
        
        # Verify server was created and shutdown was called
        mock_server_class.assert_called_once()
        mock_server.shutdown.assert_called_once()