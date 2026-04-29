#!/bin/bash
cd /Users/ramiz/ekitchen/ekitchen-ingestion
source local.env
source venv/bin/activate
python3 << 'PYTEST'
import json
import os
import sys
from services.recipe_processor import DirectRecipeProcessor

# Test recipes with mixed dietary signals
test_recipes = [
    {
        "title": "Vegetable Soup with Chicken Broth",
        "description": "A simple vegetable soup",
        "ingredients": [
            "carrots", "celery", "onions", "chicken broth", "tomatoes", "salt", "pepper"
        ],
        "instructions": ["Chop vegetables", "Add broth", "Simmer for 20 minutes"],
        "prep_time": 10, "cook_time": 25, "total_time": 35, "yields": 4, "url": "http://test.local"
    },
    {
        "title": "Vegan Buddha Bowl",
        "description": "Nutritious plant-based meal",
        "ingredients": [
            "quinoa", "roasted chickpeas", "kale", "sweet potato", "tahini", "lemon juice", "garlic", "olive oil"
        ],
        "instructions": ["Cook quinoa", "Roast chickpeas", "Assemble bowl"],
        "prep_time": 15, "cook_time": 30, "total_time": 45, "yields": 2, "url": "http://test.local"
    },
    {
        "title": "Pesto Pasta with Anchovies",
        "description": "Traditional Italian pasta",
        "ingredients": [
            "pasta", "fresh basil", "garlic", "pine nuts", "parmesan cheese", "olive oil", "anchovies", "salt"
        ],
        "instructions": ["Make pesto", "Cook pasta", "Toss together"],
        "prep_time": 10, "cook_time": 15, "total_time": 25, "yields": 4, "url": "http://test.local"
    },
    {
        "title": "Grilled Salmon with Lemon",
        "description": "Healthy fish meal",
        "ingredients": [
            "salmon fillets", "lemon", "olive oil", "garlic", "dill", "salt", "pepper"
        ],
        "instructions": ["Season salmon", "Grill for 10 minutes", "Serve with lemon"],
        "prep_time": 10, "cook_time": 12, "total_time": 22, "yields": 2, "url": "http://test.local"
    },
    {
        "title": "Greek Salad",
        "description": "Vegetarian Mediterranean salad",
        "ingredients": [
            "tomatoes", "cucumbers", "red onion", "kalamata olives", "feta cheese", "olive oil", "lemon juice", "oregano"
        ],
        "instructions": ["Chop vegetables", "Mix with dressing", "Serve cold"],
        "prep_time": 15, "cook_time": 0, "total_time": 15, "yields": 4, "url": "http://test.local"
    },
    {
        "title": "Mushroom Stew",
        "description": "Hearty vegan meal",
        "ingredients": [
            "mushrooms", "onions", "garlic", "potatoes", "vegetable broth", "thyme", "bay leaf", "olive oil", "salt", "pepper"
        ],
        "instructions": ["Sauté mushrooms", "Add vegetables", "Simmer 30 minutes"],
        "prep_time": 15, "cook_time": 35, "total_time": 50, "yields": 4, "url": "http://test.local"
    },
]

print("=" * 70)
print("DIETARY CLASSIFICATION TEST (LOCAL PROMPT VALIDATION)")
print("=" * 70)
print(f"Testing {len(test_recipes)} recipes with mixed dietary signals...\n")

try:
    processor = DirectRecipeProcessor(log_to_file=False)
    results = []

    for i, recipe in enumerate(test_recipes, 1):
        print(f"[{i}/{len(test_recipes)}] {recipe['title']}")
        ai_decisions = processor.generate_ai_decisions(recipe)

        if ai_decisions:
            classification = ai_decisions.get('dietary_classification', 'N/A')
            print(f"  ✓ dietary_classification: {classification}\n")
            results.append({"recipe": recipe['title'], "classification": classification, "status": "OK"})
        else:
            print(f"  ✗ Failed to get AI decisions\n")
            results.append({"recipe": recipe['title'], "classification": "ERROR", "status": "FAILED"})

    # Summary
    print("=" * 70)
    print("SUMMARY")
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
PYTEST
