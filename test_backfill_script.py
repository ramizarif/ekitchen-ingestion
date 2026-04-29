#!/usr/bin/env python3
"""
Local test of the backfill_dietary_classification.py script logic.
Simulates the API and classification flow without needing a live backend.
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from openai import OpenAI

# Sample recipes that would be returned from the API
SAMPLE_RECIPES = [
    {
        "id": "recipe-001",
        "name": "Chicken Piccata with Lemon",
        "ingredients": [
            {"name": "chicken breasts"},
            {"name": "lemon juice"},
            {"name": "capers"},
            {"name": "butter"},
            {"name": "flour"},
            {"name": "salt"},
        ],
        "steps": [
            {"template": "Pound chicken breasts thin"},
            {"template": "Flour and season chicken"},
            {"template": "Cook in butter until golden"},
            {"template": "Add lemon juice and capers"},
        ],
        "dietary_classification": None,
    },
    {
        "id": "recipe-002",
        "name": "Tofu Stir Fry",
        "ingredients": [
            {"name": "firm tofu"},
            {"name": "broccoli"},
            {"name": "soy sauce"},
            {"name": "garlic"},
            {"name": "ginger"},
            {"name": "sesame oil"},
        ],
        "steps": [
            {"template": "Press and cube tofu"},
            {"template": "Heat oil in wok"},
            {"template": "Stir fry vegetables"},
            {"template": "Add tofu and sauce"},
        ],
        "dietary_classification": None,
    },
    {
        "id": "recipe-003",
        "name": "Salmon with Dill",
        "ingredients": [
            {"name": "salmon fillet"},
            {"name": "fresh dill"},
            {"name": "lemon"},
            {"name": "olive oil"},
            {"name": "salt"},
            {"name": "pepper"},
        ],
        "steps": [
            {"template": "Season salmon"},
            {"template": "Place on lemon slices"},
            {"template": "Bake at 400°F for 12 minutes"},
        ],
        "dietary_classification": None,
    },
    {
        "id": "recipe-004",
        "name": "Greek Salad",
        "ingredients": [
            {"name": "tomatoes"},
            {"name": "cucumbers"},
            {"name": "red onion"},
            {"name": "feta cheese"},
            {"name": "kalamata olives"},
            {"name": "olive oil"},
            {"name": "oregano"},
        ],
        "steps": [
            {"template": "Chop all vegetables"},
            {"template": "Combine in bowl"},
            {"template": "Dress with oil and oregano"},
        ],
        "dietary_classification": None,
    },
    {
        "id": "recipe-005",
        "name": "Eggplant Parmesan",
        "ingredients": [
            {"name": "eggplant"},
            {"name": "marinara sauce"},
            {"name": "mozzarella cheese"},
            {"name": "parmesan cheese"},
            {"name": "eggs"},
            {"name": "breadcrumbs"},
            {"name": "olive oil"},
        ],
        "steps": [
            {"template": "Slice eggplant"},
            {"template": "Bread and fry slices"},
            {"template": "Layer with sauce and cheese"},
            {"template": "Bake until bubbly"},
        ],
        "dietary_classification": None,
    },
    {
        "id": "recipe-006",
        "name": "Vegan Chocolate Cake",
        "ingredients": [
            {"name": "flour"},
            {"name": "cocoa powder"},
            {"name": "sugar"},
            {"name": "baking soda"},
            {"name": "salt"},
            {"name": "vegetable oil"},
            {"name": "water"},
            {"name": "vanilla extract"},
            {"name": "vinegar"},
        ],
        "steps": [
            {"template": "Mix dry ingredients"},
            {"template": "Combine wet ingredients"},
            {"template": "Combine wet and dry"},
            {"template": "Bake at 350°F for 30 minutes"},
        ],
        "dietary_classification": None,
    },
    {
        "id": "recipe-007",
        "name": "Shrimp Pasta Carbonara",
        "ingredients": [
            {"name": "pasta"},
            {"name": "shrimp"},
            {"name": "bacon"},
            {"name": "egg yolks"},
            {"name": "parmesan cheese"},
            {"name": "black pepper"},
        ],
        "steps": [
            {"template": "Cook pasta"},
            {"template": "Fry bacon and shrimp"},
            {"template": "Toss pasta with sauce"},
        ],
        "dietary_classification": None,
    },
    {
        "id": "recipe-008",
        "name": "Vegetable Soup",
        "ingredients": [
            {"name": "carrots"},
            {"name": "celery"},
            {"name": "onions"},
            {"name": "potatoes"},
            {"name": "vegetable broth"},
            {"name": "tomatoes"},
            {"name": "herbs"},
        ],
        "steps": [
            {"template": "Chop vegetables"},
            {"template": "Sauté aromatics"},
            {"template": "Add broth and vegetables"},
            {"template": "Simmer 30 minutes"},
        ],
        "dietary_classification": None,
    },
    {
        "id": "recipe-009",
        "name": "Mushroom Risotto",
        "ingredients": [
            {"name": "arborio rice"},
            {"name": "mushrooms"},
            {"name": "onions"},
            {"name": "garlic"},
            {"name": "vegetable broth"},
            {"name": "white wine"},
            {"name": "parmesan cheese"},
            {"name": "butter"},
        ],
        "steps": [
            {"template": "Sauté mushrooms"},
            {"template": "Cook rice with broth"},
            {"template": "Stir in wine"},
            {"template": "Finish with cheese and butter"},
        ],
        "dietary_classification": None,
    },
    {
        "id": "recipe-010",
        "name": "Beef Stew",
        "ingredients": [
            {"name": "beef chuck"},
            {"name": "potatoes"},
            {"name": "carrots"},
            {"name": "celery"},
            {"name": "beef broth"},
            {"name": "red wine"},
            {"name": "tomato paste"},
            {"name": "onions"},
        ],
        "steps": [
            {"template": "Brown beef"},
            {"template": "Sauté vegetables"},
            {"template": "Combine with broth and wine"},
            {"template": "Simmer 2 hours"},
        ],
        "dietary_classification": None,
    },
]


def classify_dietary(recipe: Dict[str, Any], openai_client: OpenAI) -> Optional[str]:
    """Classify a recipe's dietary level using GPT-4o-mini."""
    title = recipe.get("name", "Unknown")
    ingredients = recipe.get("ingredients", [])
    instructions = recipe.get("steps", [])

    # Extract ingredient names
    ingredient_list = []
    if isinstance(ingredients, list):
        for ing in ingredients:
            if isinstance(ing, dict):
                ingredient_list.append(ing.get("name", ""))
            elif isinstance(ing, str):
                ingredient_list.append(ing)

    # Extract instruction text
    instruction_list = []
    if isinstance(instructions, list):
        for step in instructions:
            if isinstance(step, dict):
                instruction_list.append(step.get("template", ""))
            elif isinstance(step, str):
                instruction_list.append(step)

    prompt = f"""Classify this recipe by the highest dietary restriction level it satisfies:
- vegan = no animal products of any kind (no meat, fish, dairy, eggs, honey)
- vegetarian = no meat or fish, but allows dairy/eggs/honey
- pescatarian = no meat (mammals/birds), but allows fish/seafood, dairy, eggs
- omnivore = contains meat (beef, chicken, pork, lamb, etc.) OR cannot be classified as more restrictive

RECIPE:
Title: {title}
Ingredients: {', '.join(ingredient_list)}

Output ONLY the single word: omnivore, pescatarian, vegetarian, or vegan"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0,
            max_tokens=5,
        )

        classification = response.choices[0].message.content.strip().lower()

        valid_values = {"omnivore", "pescatarian", "vegetarian", "vegan"}
        if classification in valid_values:
            return classification
        else:
            print(f"    Warning: Invalid classification returned: {classification}")
            return None

    except Exception as e:
        print(f"    Error during classification: {e}")
        return None


def main():
    """Run classification on sample recipes."""
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        print("ERROR: OPENAI_API_KEY not set")
        sys.exit(1)

    openai_client = OpenAI(api_key=openai_key)

    # Create logs directory
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # Setup logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"backfill_dietary_classification_{timestamp}.log")

    with open(log_file, "w") as log_handle:

        def log_msg(msg: str):
            print(msg)
            log_handle.write(msg + "\n")
            log_handle.flush()

        log_msg("=" * 70)
        log_msg("DIETARY CLASSIFICATION BACKFILL (DRY-RUN TEST)")
        log_msg("=" * 70)
        log_msg(f"Sample recipes: {len(SAMPLE_RECIPES)}")
        log_msg(f"Log file: {log_file}\n")

        log_msg(
            f"{'ID':<20} {'Title':<40} {'Classification':<15} {'Latency (ms)':<12}"
        )
        log_msg("-" * 87)

        classified = 0
        failed = 0

        for recipe in SAMPLE_RECIPES:
            import time

            recipe_id = recipe.get("id", "unknown")
            recipe_title = recipe.get("name", "Unknown")[:37]

            recipe_start = time.time()
            classification = classify_dietary(recipe, openai_client)
            latency_ms = int((time.time() - recipe_start) * 1000)

            if classification:
                classified += 1
                log_msg(
                    f"{recipe_id:<20} {recipe_title:<40} {classification:<15} {latency_ms:<12}"
                )
            else:
                failed += 1
                log_msg(
                    f"{recipe_id:<20} {recipe_title:<40} {'ERROR':<15} {latency_ms:<12}"
                )

        log_msg("\n" + "=" * 70)
        log_msg("SUMMARY")
        log_msg("=" * 70)
        log_msg(f"Total recipes tested:      {len(SAMPLE_RECIPES)}")
        log_msg(f"Successfully classified:   {classified}")
        log_msg(f"Failed:                    {failed}")
        estimated_cost = classified * 0.001
        log_msg(f"Estimated cost:            ${estimated_cost:.2f} (GPT-4o-mini)")
        log_msg("=" * 70 + "\n")

        print(f"\nLog written to: {log_file}")


if __name__ == "__main__":
    main()
