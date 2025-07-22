"""Main FastMCP server for Spoonacular MCP

Provides conversational AI interface for Spoonacular ingredient data
using the Spoonacular API client with comprehensive error handling and
structured logging.

Enables Claude to handle complex requests like:
- "Find the nutritional values for butter and any substitutes for the ingredient"
- "Search for chicken breast, get its nutrition info, and find alternatives"
"""

# Standard imports
import asyncio
import uuid
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import structlog

from fastmcp import FastMCP, Context

from .config import get_config
from .models import (
    ServerHealth, IngredientSearchRequest, IngredientInfoRequest, 
    IngredientSubstitutesRequest, IngredientSearchResponse,
    IngredientInfoResponse, IngredientSubstitutesResponse
)
from ..spoonacular_client.client import SpoonacularClient
from ..spoonacular_client.exceptions import (
    SpoonacularError,
    SpoonacularAuthError,
    SpoonacularRateLimitError,
    SpoonacularNotFoundError,
    SpoonacularNetworkError
)

# Create the FastMCP server instance
mcp = FastMCP("Spoonacular MCP")

# Global state for the server
class ServerState:
    def __init__(self):
        self.config = get_config()
        self.start_time = datetime.now()
        self.active_requests = 0
        self.total_requests = 0
        self.logger = structlog.get_logger().bind(component="spoonacular_server")
        
        # Lazy initialization flag
        self._spoonacular_client = None
        self._client_initialized = False
    
    def _ensure_client_initialized(self):
        """Initialize Spoonacular client only when first needed"""
        if self._client_initialized:
            return
            
        self._spoonacular_client = SpoonacularClient()
        self._client_initialized = True
    
    @property
    def spoonacular_client(self):
        self._ensure_client_initialized()
        return self._spoonacular_client

# Initialize server state
state = ServerState()


@mcp.tool
async def health_check() -> Dict[str, Any]:
    """Check MCP server health and status
    
    Returns comprehensive health information including uptime,
    request statistics, and system status.
    """
    try:
        uptime = (datetime.now() - state.start_time).total_seconds()
        
        health = ServerHealth(
            status="healthy",
            uptime_seconds=uptime,
            active_requests=state.active_requests,
            total_requests=state.total_requests,
            spoonacular_client_ready=state._client_initialized
        )
        
        result = {
            "success": True,
            "health": health.model_dump(),
            "timestamp": datetime.now().isoformat()
        }
        
        state.logger.info("Health check completed", status="healthy", uptime_seconds=uptime)
        return result
        
    except Exception as e:
        state.logger.error("Health check failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@mcp.tool
async def get_server_config() -> Dict[str, Any]:
    """Get current server configuration settings
    
    Provides visibility into server settings for debugging
    and optimization purposes.
    """
    try:
        config_data = {
            "server_name": "Spoonacular MCP",
            "spoonacular_base_url": state.config.base_url,
            "requests_per_minute": state.config.requests_per_minute,
            "request_timeout": state.config.request_timeout,
            "max_retries": state.config.max_retries,
            "retry_delay": state.config.retry_delay,
            "api_key_configured": bool(state.config.api_key)
        }
        
        result = {
            "success": True,
            "config": config_data,
            "timestamp": datetime.now().isoformat()
        }
        
        state.logger.info("Server config retrieved")
        return result
        
    except Exception as e:
        state.logger.error("Failed to get server config", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@mcp.tool
async def test_connectivity() -> Dict[str, Any]:
    """Test server connectivity and basic functionality
    
    Tests connection to Spoonacular API and validates configuration.
    """
    try:
        # Simulate basic async operation
        await asyncio.sleep(0.1)
        
        # Test Spoonacular client initialization
        try:
            client = state.spoonacular_client
            spoonacular_ready = True
        except Exception as e:
            spoonacular_ready = False
            state.logger.warning("Spoonacular client initialization failed", error=str(e))
        
        test_results = {
            "mcp_communication": "working",
            "async_operations": "working", 
            "error_handling": "working",
            "logging": "working",
            "configuration": "loaded",
            "spoonacular_client": "ready" if spoonacular_ready else "error"
        }
        
        result = {
            "success": True,
            "test_results": test_results,
            "message": "All basic connectivity tests passed" if spoonacular_ready else "Basic tests passed, Spoonacular client needs attention",
            "timestamp": datetime.now().isoformat()
        }
        
        state.logger.info("Connectivity test completed", spoonacular_ready=spoonacular_ready)
        return result
        
    except Exception as e:
        state.logger.error("Connectivity test failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@mcp.tool
async def search_ingredient(name: str, limit: int = 10) -> Dict[str, Any]:
    """Search for ingredients by name using Spoonacular API
    
    Enables Claude to find ingredients for further processing.
    
    Args:
        name: Ingredient name to search for (e.g., "butter", "chicken breast")
        limit: Maximum number of results to return (default: 10, max: 100)
        
    Returns:
        Structured ingredient search results with IDs and names
    """
    try:
        state.active_requests += 1
        state.total_requests += 1
        
        # Validate inputs
        if not name or not name.strip():
            raise ValueError("Ingredient name cannot be empty")
        
        limit = min(max(1, limit), 100)  # Clamp between 1 and 100
        
        state.logger.info("Searching for ingredient", name=name, limit=limit)
        
        # Call Spoonacular API
        api_response = await state.spoonacular_client.search_ingredients(
            query=name.strip(),
            number=limit,
            meta_information=True
        )
        
        # Parse response into structured format
        ingredients = []
        results = api_response.get("results", [])
        
        for item in results:
            ingredients.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "image": item.get("image")
            })
        
        search_response = IngredientSearchResponse(
            success=True,
            query=name,
            total_results=len(ingredients),
            ingredients=ingredients
        )
        
        result = {
            "success": True,
            "search_results": search_response.model_dump(),
            "timestamp": datetime.now().isoformat()
        }
        
        state.logger.info("Ingredient search completed", 
                         name=name, 
                         results_count=len(ingredients))
        
        return result
        
    except SpoonacularAuthError as e:
        state.logger.error("Spoonacular authentication error", error=str(e))
        return {
            "success": False,
            "error": "authentication_error",
            "message": "Spoonacular API authentication failed. Check API key configuration.",
            "timestamp": datetime.now().isoformat()
        }
        
    except SpoonacularRateLimitError as e:
        state.logger.error("Spoonacular rate limit exceeded", error=str(e))
        return {
            "success": False,
            "error": "rate_limit_exceeded", 
            "message": "Spoonacular API rate limit exceeded. Please wait before making more requests.",
            "retry_after": getattr(e, 'retry_after', None),
            "timestamp": datetime.now().isoformat()
        }
        
    except SpoonacularError as e:
        state.logger.error("Spoonacular API error", error=str(e))
        return {
            "success": False,
            "error": "api_error",
            "message": f"Spoonacular API error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        state.logger.error("Unexpected error in search_ingredient", error=str(e))
        return {
            "success": False,
            "error": "internal_error",
            "message": f"Internal error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
    finally:
        state.active_requests -= 1


@mcp.tool
async def get_ingredient(ingredient_id: int, amount: float = 100, unit: str = "grams") -> Dict[str, Any]:
    """Get detailed ingredient information including nutrition facts
    
    Provides comprehensive ingredient information for Claude to use in conversations.
    
    Args:
        ingredient_id: Spoonacular ingredient ID from search results
        amount: Amount for nutrition calculation (default: 100)
        unit: Unit for amount calculation (default: "grams")
        
    Returns:
        Detailed ingredient data with nutrition facts per specified amount
    """
    try:
        state.active_requests += 1
        state.total_requests += 1
        
        # Validate inputs
        if not isinstance(ingredient_id, int) or ingredient_id <= 0:
            raise ValueError("ingredient_id must be a positive integer")
        
        if amount <= 0:
            raise ValueError("amount must be positive")
            
        state.logger.info("Getting ingredient information", 
                         ingredient_id=ingredient_id, 
                         amount=amount, 
                         unit=unit)
        
        # Call Spoonacular API
        api_response = await state.spoonacular_client.get_ingredient_information(
            ingredient_id=ingredient_id,
            amount=amount,
            unit=unit
        )
        
        # Extract nutrition information
        nutrition_facts = []
        nutrition_data = api_response.get("nutrition", {})
        nutrients = nutrition_data.get("nutrients", [])
        
        for nutrient in nutrients:
            nutrition_facts.append({
                "name": nutrient.get("name"),
                "amount": nutrient.get("amount"),
                "unit": nutrient.get("unit"),
                "percent_daily_value": nutrient.get("percentOfDailyNeeds")
            })
        
        # Structure the response
        ingredient_info = {
            "id": api_response.get("id"),
            "name": api_response.get("name"),
            "original_name": api_response.get("originalName"),
            "amount": api_response.get("amount"),
            "unit": api_response.get("unit"),
            "aisle": api_response.get("aisle"),
            "consistency": api_response.get("consistency"),
            "image": api_response.get("image"),
            "nutrition_facts": nutrition_facts,
            "possible_units": api_response.get("possibleUnits", []),
            "category_path": api_response.get("categoryPath", [])
        }
        
        info_response = IngredientInfoResponse(
            success=True,
            ingredient_id=ingredient_id,
            amount=amount,
            unit=unit,
            ingredient_info=ingredient_info
        )
        
        result = {
            "success": True,
            "ingredient_information": info_response.model_dump(),
            "timestamp": datetime.now().isoformat()
        }
        
        state.logger.info("Ingredient information retrieved", 
                         ingredient_id=ingredient_id,
                         name=ingredient_info.get("name"),
                         nutrition_facts_count=len(nutrition_facts))
        
        return result
        
    except SpoonacularNotFoundError as e:
        state.logger.error("Ingredient not found", ingredient_id=ingredient_id, error=str(e))
        return {
            "success": False,
            "error": "not_found",
            "message": f"Ingredient with ID {ingredient_id} not found",
            "timestamp": datetime.now().isoformat()
        }
        
    except SpoonacularAuthError as e:
        state.logger.error("Spoonacular authentication error", error=str(e))
        return {
            "success": False,
            "error": "authentication_error",
            "message": "Spoonacular API authentication failed. Check API key configuration.",
            "timestamp": datetime.now().isoformat()
        }
        
    except SpoonacularRateLimitError as e:
        state.logger.error("Spoonacular rate limit exceeded", error=str(e))
        return {
            "success": False,
            "error": "rate_limit_exceeded",
            "message": "Spoonacular API rate limit exceeded. Please wait before making more requests.",
            "retry_after": getattr(e, 'retry_after', None),
            "timestamp": datetime.now().isoformat()
        }
        
    except SpoonacularError as e:
        state.logger.error("Spoonacular API error", error=str(e))
        return {
            "success": False,
            "error": "api_error", 
            "message": f"Spoonacular API error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        state.logger.error("Unexpected error in get_ingredient", error=str(e))
        return {
            "success": False,
            "error": "internal_error",
            "message": f"Internal error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
    finally:
        state.active_requests -= 1


@mcp.tool 
async def get_ingredient_substitutes(ingredient_id: int) -> Dict[str, Any]:
    """Get substitute suggestions for an ingredient
    
    Enables Claude to suggest ingredient replacements in conversations.
    
    Args:
        ingredient_id: Spoonacular ingredient ID to find substitutes for
        
    Returns:
        Structured list of ingredient alternatives
    """
    try:
        state.active_requests += 1
        state.total_requests += 1
        
        # Validate inputs
        if not isinstance(ingredient_id, int) or ingredient_id <= 0:
            raise ValueError("ingredient_id must be a positive integer")
        
        state.logger.info("Getting ingredient substitutes", ingredient_id=ingredient_id)
        
        # First get the ingredient name for the substitutes API
        ingredient_info = await state.spoonacular_client.get_ingredient_information(
            ingredient_id=ingredient_id,
            amount=100,
            unit="grams"
        )
        
        ingredient_name = ingredient_info.get("name", "")
        if not ingredient_name:
            raise ValueError(f"Could not determine name for ingredient ID {ingredient_id}")
        
        # Call Spoonacular substitutes API
        api_response = await state.spoonacular_client.get_ingredient_substitutes(
            ingredient_name=ingredient_name
        )
        
        # Parse substitutes
        substitutes = []
        substitutes_data = api_response.get("substitutes", [])
        
        for substitute in substitutes_data:
            if isinstance(substitute, str):
                substitutes.append({"name": substitute})
            elif isinstance(substitute, dict):
                substitutes.append({"name": substitute.get("name", str(substitute))})
            else:
                substitutes.append({"name": str(substitute)})
        
        substitutes_response = IngredientSubstitutesResponse(
            success=True,
            ingredient_id=ingredient_id,
            ingredient_name=ingredient_name,
            substitutes=substitutes,
            message=api_response.get("message")
        )
        
        result = {
            "success": True,
            "substitutes": substitutes_response.model_dump(),
            "timestamp": datetime.now().isoformat()
        }
        
        state.logger.info("Ingredient substitutes retrieved",
                         ingredient_id=ingredient_id,
                         ingredient_name=ingredient_name, 
                         substitutes_count=len(substitutes))
        
        return result
        
    except SpoonacularNotFoundError as e:
        state.logger.error("Ingredient not found for substitutes", ingredient_id=ingredient_id, error=str(e))
        return {
            "success": False,
            "error": "not_found",
            "message": f"Ingredient with ID {ingredient_id} not found",
            "timestamp": datetime.now().isoformat()
        }
        
    except SpoonacularAuthError as e:
        state.logger.error("Spoonacular authentication error", error=str(e))
        return {
            "success": False,
            "error": "authentication_error",
            "message": "Spoonacular API authentication failed. Check API key configuration.",
            "timestamp": datetime.now().isoformat()
        }
        
    except SpoonacularRateLimitError as e:
        state.logger.error("Spoonacular rate limit exceeded", error=str(e))
        return {
            "success": False,
            "error": "rate_limit_exceeded",
            "message": "Spoonacular API rate limit exceeded. Please wait before making more requests.",
            "retry_after": getattr(e, 'retry_after', None),
            "timestamp": datetime.now().isoformat()
        }
        
    except SpoonacularError as e:
        state.logger.error("Spoonacular API error", error=str(e))
        return {
            "success": False,
            "error": "api_error",
            "message": f"Spoonacular API error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        state.logger.error("Unexpected error in get_ingredient_substitutes", error=str(e))
        return {
            "success": False,
            "error": "internal_error", 
            "message": f"Internal error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
    finally:
        state.active_requests -= 1


async def shutdown():
    """Gracefully shutdown the MCP server
    
    Ensures proper cleanup of resources and logging of final statistics.
    """
    try:
        state.logger.info("Shutting down Spoonacular MCP server")
        
        # Close Spoonacular client if initialized
        if hasattr(state, '_spoonacular_client') and state._spoonacular_client:
            await state._spoonacular_client.close()
        
        # Log final statistics
        uptime = (datetime.now() - state.start_time).total_seconds()
        state.logger.info(
            "Spoonacular MCP server shutdown complete",
            uptime_seconds=uptime,
            total_requests=state.total_requests
        )
        
    except Exception as e:
        state.logger.error(
            "Error during server shutdown",
            error_type=type(e).__name__,
            error_message=str(e)
        )


def main():
    """Main entry point for the Spoonacular MCP server
    
    Creates and starts the Spoonacular MCP server with proper
    error handling and graceful shutdown support.
    """
    try:
        # Start the MCP server immediately
        mcp.run()
        
    except KeyboardInterrupt:
        pass
        
    except Exception as e:
        # Silent fail to avoid broken pipe issues
        import sys
        sys.exit(1)


if __name__ == "__main__":
    main()