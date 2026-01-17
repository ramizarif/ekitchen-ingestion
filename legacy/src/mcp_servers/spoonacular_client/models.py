"""Response models for Spoonacular API endpoints

Structured dataclasses for parsing and validating API responses.
Designed for future database integration while being fully functional standalone.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union


@dataclass
class SpoonacularResponse:
    """Base response class with common metadata"""
    raw_data: Dict[str, Any] = field(repr=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create instance from API response dictionary"""
        # Default implementation just stores raw data
        return cls(raw_data=data)


@dataclass 
class NutritionInfo:
    """Nutrition information for an ingredient"""
    name: str
    amount: float
    unit: str
    percent_of_daily_needs: Optional[float] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create NutritionInfo from API data"""
        return cls(
            name=data.get("name", ""),
            amount=data.get("amount", 0.0),
            unit=data.get("unit", ""),
            percent_of_daily_needs=data.get("percentOfDailyNeeds")
        )


@dataclass
class IngredientSearchItem:
    """Individual ingredient from search results"""
    id: int
    name: str
    image: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create IngredientSearchItem from API data"""
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            image=data.get("image")
        )


@dataclass
class IngredientSearchResult(SpoonacularResponse):
    """Response from ingredient search endpoint"""
    results: List[IngredientSearchItem]
    offset: int
    number: int
    total_results: int
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create IngredientSearchResult from API response"""
        results = [
            IngredientSearchItem.from_dict(item) 
            for item in data.get("results", [])
        ]
        
        return cls(
            results=results,
            offset=data.get("offset", 0),
            number=data.get("number", 0),
            total_results=data.get("totalResults", 0),
            raw_data=data
        )


@dataclass
class WeightPerServing:
    """Weight information per serving"""
    amount: float
    unit: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create WeightPerServing from API data"""
        return cls(
            amount=data.get("amount", 0.0),
            unit=data.get("unit", "")
        )


@dataclass
class IngredientInformation(SpoonacularResponse):
    """Detailed ingredient information including nutrition"""
    id: int
    name: str
    original: str
    original_name: str
    amount: float
    unit: str
    unit_short: str
    unit_long: str
    possible_units: List[str]
    estimated_cost: Optional[Dict[str, Union[float, str]]] = None
    consistency: Optional[str] = None
    shopping_list_units: Optional[List[str]] = None
    aisle: Optional[str] = None
    image: Optional[str] = None
    meta: List[str] = field(default_factory=list)
    nutrition: List[NutritionInfo] = field(default_factory=list)
    category_path: List[str] = field(default_factory=list)
    weight_per_serving: Optional[WeightPerServing] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create IngredientInformation from API response"""
        # Parse nutrition data
        nutrition = []
        nutrition_data = data.get("nutrition", {})
        if isinstance(nutrition_data, dict):
            nutrients = nutrition_data.get("nutrients", [])
            nutrition = [NutritionInfo.from_dict(n) for n in nutrients]
        
        # Parse weight per serving
        weight_per_serving = None
        weight_data = data.get("weightPerServing")
        if weight_data:
            weight_per_serving = WeightPerServing.from_dict(weight_data)
        
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            original=data.get("original", ""),
            original_name=data.get("originalName", ""),
            amount=data.get("amount", 0.0),
            unit=data.get("unit", ""),
            unit_short=data.get("unitShort", ""),
            unit_long=data.get("unitLong", ""),
            possible_units=data.get("possibleUnits", []),
            estimated_cost=data.get("estimatedCost"),
            consistency=data.get("consistency"),
            shopping_list_units=data.get("shoppingListUnits"),
            aisle=data.get("aisle"),
            image=data.get("image"),
            meta=data.get("meta", []),
            nutrition=nutrition,
            category_path=data.get("categoryPath", []),
            weight_per_serving=weight_per_serving,
            raw_data=data
        )


@dataclass  
class SubstituteIngredient:
    """Individual substitute suggestion"""
    name: str
    
    @classmethod
    def from_dict(cls, data: Union[str, Dict[str, Any]]):
        """Create SubstituteIngredient from API data
        
        API sometimes returns strings, sometimes objects
        """
        if isinstance(data, str):
            return cls(name=data)
        elif isinstance(data, dict):
            return cls(name=data.get("name", ""))
        else:
            return cls(name=str(data))


@dataclass
class IngredientSubstitutes(SpoonacularResponse):
    """Response from ingredient substitutes endpoint"""
    ingredient: str
    substitutes: List[SubstituteIngredient]
    message: Optional[str] = None
    
    @classmethod 
    def from_dict(cls, data: Dict[str, Any]):
        """Create IngredientSubstitutes from API response"""
        # Parse substitutes list
        substitutes = []
        substitutes_data = data.get("substitutes", [])
        
        for substitute in substitutes_data:
            substitutes.append(SubstituteIngredient.from_dict(substitute))
        
        return cls(
            ingredient=data.get("ingredient", ""),
            substitutes=substitutes,
            message=data.get("message"),
            raw_data=data
        )


# Convenience type aliases for easier imports
IngredientSearch = IngredientSearchResult
IngredientInfo = IngredientInformation
IngredientSubs = IngredientSubstitutes


def parse_api_response(endpoint: str, data: Dict[str, Any]) -> SpoonacularResponse:
    """Parse API response based on endpoint type
    
    Args:
        endpoint: API endpoint path (e.g., '/food/ingredients/search')
        data: Raw API response data
        
    Returns:
        Appropriate response model instance
    """
    if "/search" in endpoint:
        return IngredientSearchResult.from_dict(data)
    elif "/information" in endpoint:
        return IngredientInformation.from_dict(data)
    elif "/substitutes" in endpoint:
        return IngredientSubstitutes.from_dict(data)
    else:
        # Fallback to base response
        return SpoonacularResponse.from_dict(data)