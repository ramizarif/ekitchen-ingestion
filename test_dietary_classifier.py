#!/usr/bin/env python3
"""
Quick test script to validate the dietary classification prompt on sample recipes.
Tests with mixed-signal recipes to ensure correct classification.
"""

import json
import os
import sys
from typing import Any, Dict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from services.recipe_processor import DirectRecipeProcessor


def test_dietary_classification():
    """Test the dietary classification on mixed-signal recipes."""

    # Test recipes with mixed dietary signals
    test_recipes = [
        {
            "title": "Vegetable Soup with Chicken Broth",
            "description": "A simple vegetable soup",
            "ingredients": [
                "carrots",
                "celery",
                "onions",
                "chicken broth",
                "tomatoes",
                "salt",
                "pepper"
            ],
            "instructions": ["Chop vegetables", "Add broth", "Simmer for 20 minutes"],
            "prep_time": 10,
            "cook_time": 25,
            "total_time": 35,
            "yields": 4
        },
        {
            "title": "Vegan Buddha Bowl",
            "description": "Nutritious plant-based meal",
            "ingredients": [
                "quinoa",
                "roasted chickpeas",
                "kale",
                "sweet potato",
                "tahini",
                "lemon juice",
                "garlic",
                "olive oil"
            ],
            "instructions": ["Cook quinoa", "Roast chickpeas", "Assemble bowl"],
            "prep_time": 15,
            "cook_time": 30,
            "total_time": 45,
            "yields": 2
        },
        {
            "title": "Pesto Pasta with Anchovies",
            "description": "Traditional Italian pasta",
            "ingredients": [
                "pasta",
                "fresh basil",
                "garlic",
                "pine nuts",
                "parmesan cheese",
                "olive oil",
                "anchovies",
                "salt"
            ],
            "instructions": ["Make pesto", "Cook pasta", "Toss together"],
            "prep_time": 10,
            "cook_time": 15,
            "total_time": 25,
            "yields": 4
        },
        {
            "title": "Grilled Salmon with Lemon",
            "description": "Healthy fish meal",
            "ingredients": [
                "salmon fillets",
                "lemon",
                "olive oil",
                "garlic",
                "dill",
                "salt",
                "pepper"
            ],
            "instructions": ["Season salmon", "Grill for 10 minutes", "Serve with lemon"],
            "prep_time": 10,
            "cook_time": 12,
            "total_time": 22,
            "yields": 2
        },
        {
            "title": "Greek Salad",
            "description": "Vegetarian Mediterranean salad",
            "ingredients": [
                "tomatoes",
                "cucumbers",
                "red onion",
                "kalamata olives",
                "feta cheese",
                "olive oil",
                "lemon juice",
                "oregano"
            ],
            "instructions": ["Chop vegetables", "Mix with dressing", "Serve cold"],
            "prep_time": 15,
            "cook_time": 0,
            "total_time": 15,
            "yields": 4
        },
        {
            "title": "Mushroom Stew",
            "description": "Hearty vegan meal",
            "ingredients": [
                "mushrooms",
                "onions",
                "garlic",
                "potatoes",
                "vegetable broth",
                "thyme",
                "bay leaf",
                "olive oil",
                "salt",
                "pepper"
            ],
            "instructions": ["Sauté mushrooms", "Add vegetables", "Simmer 30 minutes"],
            "prep_time": 15,
            "cook_time": 35,
            "total_time": 50,
            "yields": 4
        },
    ]

    # Initialize processor (requires env vars)
    base_url = os.environ.get("EKITCHEN_BASE_URL", "http://localhost:8081")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not openai_key:
        print("ERROR: OPENAI_API_KEY not set. Please source local.env")
        sys.exit(1)

    print("=" * 70)
    print("DIETARY CLASSIFICATION TEST")
    print("=" * 70)
    print(f"Testing {len(test_recipes)} recipes with mixed dietary signals...\n")

    try:
        processor = DirectRecipeProcessor(ekitchen_base_url=base_url)

        results = []
        for i, recipe in enumerate(test_recipes, 1):
            print(f"[{i}/{len(test_recipes)}] Testing: {recipe['title']}")

            ai_decisions = processor.generate_ai_decisions(recipe)

            if ai_decisions:
                classification = ai_decisions.get('dietary_classification', 'N/A')
                print(f"  -> dietary_classification: {classification}")
                results.append({
                    "recipe": recipe['title'],
                    "classification": classification,
                    "status": "OK"
                })
            else:
                print(f"  -> ERROR: Failed to get AI decisions")
                results.append({
                    "recipe": recipe['title'],
                    "classification": "ERROR",
                    "status": "FAILED"
                })
            print()

        # Summary
        print("=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        for result in results:
            status = "✅" if result['status'] == "OK" else "❌"
            print(f"{status} {result['recipe']}: {result['classification']}")

        success_count = sum(1 for r in results if r['status'] == "OK")
        print(f"\nPassed: {success_count}/{len(results)}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    test_dietary_classification()
