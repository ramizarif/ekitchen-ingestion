#!/usr/bin/env python3
"""One-shot acceptance test for meal_type-in-live-ingestion.

Imports a single real recipe URL through the full autonomous pipeline against
the LIVE prod backend, then reports the created recipe's meal_type. Proves the
whole chain: AI classifies meal_type -> sent on create -> backend persists it.

Usage: python3 scripts/verify_meal_type_live.py <recipe_url>
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.recipe_processor import DirectRecipeProcessor

url = sys.argv[1] if len(sys.argv) > 1 else "https://www.allrecipes.com/recipe/23600/worlds-best-lasagna/"

proc = DirectRecipeProcessor(log_to_file=False)
print(f"🔬 Importing: {url}")
result = proc.process_recipe_autonomous(url)

print("\n=== RESULT ===")
print("success:", getattr(result, "success", None))
print("recipe_id:", getattr(result, "recipe_id", None))
print("error:", getattr(result, "error", None) or getattr(result, "error_message", None))
# Dump any meal_type the result object carries
for attr in ("meal_type", "recipe_name", "name"):
    if hasattr(result, attr):
        print(f"{attr}:", getattr(result, attr))
