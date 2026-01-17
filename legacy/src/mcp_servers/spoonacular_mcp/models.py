"""Response models for Spoonacular MCP server

Structured Pydantic models for MCP tool requests and responses.
Designed to enable conversational AI workflows with Spoonacular data.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ServerHealth(BaseModel):
    """Server health status model"""
    status: str = Field(description="Server status (healthy/unhealthy)")
    uptime_seconds: float = Field(description="Server uptime in seconds")
    active_requests: int = Field(description="Number of active requests")
    total_requests: int = Field(description="Total requests processed")
    spoonacular_client_ready: bool = Field(description="Whether Spoonacular client is initialized")


class IngredientSearchRequest(BaseModel):
    """Request model for ingredient search"""
    name: str = Field(description="Ingredient name to search for")
    limit: int = Field(default=10, description="Maximum number of results")


class IngredientItem(BaseModel):
    """Individual ingredient from search results"""
    id: int = Field(description="Spoonacular ingredient ID")
    name: str = Field(description="Ingredient name")
    image: Optional[str] = Field(description="Ingredient image URL")


class IngredientSearchResponse(BaseModel):
    """Response model for ingredient search"""
    success: bool = Field(description="Whether the search was successful")
    query: str = Field(description="Original search query")
    total_results: int = Field(description="Number of results found")
    ingredients: List[IngredientItem] = Field(description="List of ingredient results")


class IngredientInfoRequest(BaseModel):
    """Request model for ingredient information"""
    ingredient_id: int = Field(description="Spoonacular ingredient ID")
    amount: float = Field(default=100, description="Amount for nutrition calculation")
    unit: str = Field(default="grams", description="Unit for amount")


class NutritionFact(BaseModel):
    """Individual nutrition fact"""
    name: str = Field(description="Nutrient name")
    amount: float = Field(description="Amount of nutrient")
    unit: str = Field(description="Unit of measurement")
    percent_daily_value: Optional[float] = Field(description="Percent of daily recommended value")


class EstimatedCost(BaseModel):
    """Estimated cost information"""
    value: float = Field(description="Cost value")
    unit: str = Field(description="Cost unit (e.g., 'US Cents')")


class IngredientInformation(BaseModel):
    """Detailed ingredient information"""
    id: int = Field(description="Spoonacular ingredient ID")
    name: str = Field(description="Ingredient name")
    original_name: str = Field(description="Original ingredient name")
    amount: float = Field(description="Amount used for calculations")
    unit: str = Field(description="Unit of measurement")
    aisle: Optional[str] = Field(description="Grocery store aisle")
    consistency: Optional[str] = Field(description="Ingredient consistency")
    image: Optional[str] = Field(description="Ingredient image URL")
    nutrition_facts: List[NutritionFact] = Field(description="Nutrition information")
    possible_units: List[str] = Field(description="Possible units for this ingredient")
    category_path: List[str] = Field(description="Category hierarchy")
    estimated_cost: Optional[EstimatedCost] = Field(description="Estimated cost information")


class IngredientInfoResponse(BaseModel):
    """Response model for ingredient information"""
    success: bool = Field(description="Whether the request was successful")
    ingredient_id: int = Field(description="Spoonacular ingredient ID")
    amount: float = Field(description="Amount used for nutrition calculation")
    unit: str = Field(description="Unit for amount")
    ingredient_info: IngredientInformation = Field(description="Detailed ingredient information")


class IngredientSubstitutesRequest(BaseModel):
    """Request model for ingredient substitutes"""
    ingredient_id: int = Field(description="Spoonacular ingredient ID to find substitutes for")


class SubstituteItem(BaseModel):
    """Individual substitute suggestion"""
    name: str = Field(description="Substitute ingredient name")


class IngredientSubstitutesResponse(BaseModel):
    """Response model for ingredient substitutes"""
    success: bool = Field(description="Whether the request was successful")
    ingredient_id: int = Field(description="Original ingredient ID")
    ingredient_name: str = Field(description="Original ingredient name")
    substitutes: List[SubstituteItem] = Field(description="List of substitute suggestions")
    message: Optional[str] = Field(description="Additional message from API")


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = Field(default=False, description="Always false for errors")
    error: str = Field(description="Error type/code")
    message: str = Field(description="Human-readable error message")
    retry_after: Optional[int] = Field(description="Seconds to wait before retrying (for rate limits)")
    timestamp: str = Field(description="Error timestamp")


# Workflow models for complex conversational patterns
class IngredientWithSubstitutesRequest(BaseModel):
    """Request for ingredient info plus substitutes (convenience model)"""
    ingredient_name: str = Field(description="Ingredient name to search and analyze")
    amount: float = Field(default=100, description="Amount for nutrition calculation")
    unit: str = Field(default="grams", description="Unit for amount")


class IngredientWithSubstitutesResponse(BaseModel):
    """Combined response with ingredient info and substitutes"""
    success: bool = Field(description="Whether the entire workflow was successful")
    search_results: Optional[IngredientSearchResponse] = Field(description="Search results")
    ingredient_info: Optional[IngredientInfoResponse] = Field(description="Ingredient information")
    substitutes: Optional[IngredientSubstitutesResponse] = Field(description="Substitute suggestions")
    workflow_steps: List[str] = Field(description="Steps completed in the workflow")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")


# Tool signature documentation models
class ToolParameter(BaseModel):
    """Tool parameter specification"""
    name: str = Field(description="Parameter name")
    type: str = Field(description="Parameter type")
    required: bool = Field(description="Whether parameter is required")
    default: Optional[Any] = Field(description="Default value if not required")
    description: str = Field(description="Parameter description")


class ToolSpec(BaseModel):
    """Tool specification for documentation"""
    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    purpose: str = Field(description="Tool purpose and use case")
    parameters: List[ToolParameter] = Field(description="Tool parameters")
    returns: str = Field(description="Description of return value")
    example: Optional[str] = Field(description="Example usage")


class ServerCapabilities(BaseModel):
    """Server capabilities and features"""
    tools: List[ToolSpec] = Field(description="Available tools")
    conversational_workflows: List[str] = Field(description="Supported conversational patterns")
    error_handling: List[str] = Field(description="Error handling capabilities")
    rate_limiting: bool = Field(description="Whether rate limiting is implemented")
    structured_responses: bool = Field(description="Whether responses are structured for AI consumption")