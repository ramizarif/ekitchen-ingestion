"""
extract_macros must match Spoonacular nutrient names exactly. The order below is how
Spoonacular returns butter (id 1001): "Trans Fat" and "Net Carbohydrates" come AFTER the
real values, which is what let substring matching overwrite them.
"""
from services.nutrition_parsing import extract_macros

BUTTER_NUTRIENTS = [
    {"name": "Calories", "amount": 717.0, "unit": "kcal"},
    {"name": "Fat", "amount": 81.11, "unit": "g"},
    {"name": "Saturated Fat", "amount": 51.37, "unit": "g"},
    {"name": "Mono Unsaturated Fat", "amount": 21.02, "unit": "g"},
    {"name": "Poly Unsaturated Fat", "amount": 3.04, "unit": "g"},
    {"name": "Trans Fat", "amount": 3.28, "unit": "g"},
    {"name": "Carbohydrates", "amount": 0.06, "unit": "g"},
    {"name": "Net Carbohydrates", "amount": 0.06, "unit": "g"},
    {"name": "Sugar", "amount": 0.06, "unit": "g"},
    {"name": "Protein", "amount": 0.85, "unit": "g"},
    {"name": "Cholesterol", "amount": 215.0, "unit": "mg"},
]


def test_fat_is_total_fat_not_trans_fat():
    assert extract_macros(BUTTER_NUTRIENTS)["fat"] == 81.11


def test_carbohydrates_are_total_not_net():
    nutrients = [
        {"name": "Carbohydrates", "amount": 22.8},
        {"name": "Fiber", "amount": 2.6},
        {"name": "Net Carbohydrates", "amount": 20.2},
    ]
    assert extract_macros(nutrients)["carbohydrates"] == 22.8


def test_all_macros_extracted():
    assert extract_macros(BUTTER_NUTRIENTS) == {
        "calories": 717.0,
        "fat": 81.11,
        "carbohydrates": 0.06,
        "sugar": 0.06,
        "protein": 0.85,
    }


def test_missing_macros_are_absent_not_zero():
    # Without calories, nothing else may be read as calories (the old positional bug).
    macros = extract_macros([{"name": "Protein", "amount": 12.6}])
    assert macros == {"protein": 12.6}
    assert "calories" not in macros


def test_tolerates_empty_and_malformed_input():
    assert extract_macros(None) == {}
    assert extract_macros([]) == {}
    assert extract_macros([{"amount": 5}, {"name": None, "amount": 1}]) == {}
