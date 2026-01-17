"""Spoonacular API client for ingredient data retrieval

This package provides an async HTTP client for the Spoonacular API,
implementing ingredient search, information retrieval, and substitutes endpoints.
"""

from .client import SpoonacularClient
from .models import (
    IngredientSearchResult,
    IngredientInformation,
    IngredientSubstitutes,
    SpoonacularResponse
)
from .exceptions import (
    SpoonacularError,
    SpoonacularAuthError,
    SpoonacularRateLimitError,
    SpoonacularNotFoundError
)

__version__ = "1.0.0"
__all__ = [
    "SpoonacularClient",
    "IngredientSearchResult",
    "IngredientInformation", 
    "IngredientSubstitutes",
    "SpoonacularResponse",
    "SpoonacularError",
    "SpoonacularAuthError",
    "SpoonacularRateLimitError",
    "SpoonacularNotFoundError"
]