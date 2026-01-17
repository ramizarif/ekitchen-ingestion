"""Spoonacular MCP Server

FastMCP server for Spoonacular ingredient data, enabling conversational
AI workflows for nutrition information and ingredient substitutes.
"""

from .server import mcp, main
from .config import get_config, SpoonacularMCPConfig
from .models import (
    ServerHealth,
    IngredientSearchRequest,
    IngredientInfoRequest, 
    IngredientSubstitutesRequest,
    IngredientSearchResponse,
    IngredientInfoResponse,
    IngredientSubstitutesResponse
)

__version__ = "1.0.0"
__all__ = [
    "mcp",
    "main", 
    "get_config",
    "SpoonacularMCPConfig",
    "ServerHealth",
    "IngredientSearchRequest",
    "IngredientInfoRequest",
    "IngredientSubstitutesRequest", 
    "IngredientSearchResponse",
    "IngredientInfoResponse",
    "IngredientSubstitutesResponse"
]