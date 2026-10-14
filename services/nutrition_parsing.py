"""
Map Spoonacular's ingredient nutrient list onto eKitchen's macro fields.

Names are matched EXACTLY. Substring matching is what broke the catalog: Spoonacular lists
"Fat" and then "Trans Fat", and "Carbohydrates" and then "Net Carbohydrates", so a loose
`'fat' in name` let the trans-fat amount overwrite real fat (butter stored 3.3g/100g instead
of 81g), and net carbs overwrite total carbs.
"""
from typing import Any, Dict, Iterable

# Spoonacular nutrient name (lowercased) -> eKitchen field.
SPOONACULAR_MACRO_NAMES = {
    "calories": "calories",
    "protein": "protein",
    "fat": "fat",
    "carbohydrates": "carbohydrates",
    "sugar": "sugar",
}


def extract_macros(nutrients: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    """Return {field: amount} for the macros present in a Spoonacular `nutrients` list.

    Macros Spoonacular did not report are absent from the result rather than zero, so callers
    can tell "no data" from "none".
    """
    macros: Dict[str, float] = {}
    for nutrient in nutrients or []:
        field = SPOONACULAR_MACRO_NAMES.get((nutrient.get("name") or "").strip().lower())
        if field is not None:
            macros[field] = nutrient.get("amount", 0)
    return macros
