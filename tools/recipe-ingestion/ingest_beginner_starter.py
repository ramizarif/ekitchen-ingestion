#!/usr/bin/env python3
"""
Ingest hand-authored beginner starter recipes via the existing pipeline.

These recipes were authored directly (not scraped) because source recipe sites
lacked the simplest beginner versions. We still run them through the SAME
pipeline as scraped recipes by calling DirectRecipeProcessor.process_parsed_recipe(),
which:
  - AI-standardizes each ingredient string and does get-or-create against
    global_ingredients (Spoonacular enrichment for any that don't exist yet),
  - calculates nutrition,
  - rewrites steps/description into eKitchen's cozy brand voice + derives
    cuisine/difficulty/tags,
  - generates a DALL-E hero image and uploads it,
  - POSTs to /global-recipes (skips by title if already present).

Usage (from repo root, mirrors `make ingest` env wiring):
  cd tools/recipe-ingestion && set -a && source ../../local.env && set +a \
    && PYTHONPATH=../../legacy/src/processing:../../legacy/src/discovery:$PYTHONPATH \
       ../../venv/bin/python3 ingest_beginner_starter.py [--limit N] [--dry-run] [--images DIR]

  --limit N    only process the first N recipes (use --limit 2 for the canary)
  --dry-run    print what would be ingested; do NOT call the pipeline / write to prod
  --images DIR directory for generated hero images (default ./beginner-starter-images)
"""

import os
import sys
import json
import argparse
import time

# NOTE: DirectRecipeProcessor is imported lazily inside main() (only for real runs)
# so that --dry-run works without the full PYTHONPATH / API env wiring.

DEFAULT_RECIPES_JSON = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "beginner-starter", "recipes_parsed.json"
)


def load_recipes(path):
    with open(path) as f:
        data = json.load(f)
    return data.get("recipes", [])


def main():
    ap = argparse.ArgumentParser(description="Ingest beginner starter recipes")
    ap.add_argument("--recipes", default=DEFAULT_RECIPES_JSON, help="Path to recipes_parsed.json")
    ap.add_argument("--limit", type=int, default=0, help="Only process first N (0 = all)")
    ap.add_argument("--dry-run", action="store_true", help="Don't call the pipeline / write to prod")
    ap.add_argument("--images", default="./beginner-starter-images", help="Hero image output dir")
    args = ap.parse_args()

    recipes = load_recipes(args.recipes)
    if args.limit > 0:
        recipes = recipes[: args.limit]

    print("=" * 70)
    print("🍳 BEGINNER STARTER RECIPE INGESTION")
    print("=" * 70)
    print(f"📋 Recipes to process: {len(recipes)}")
    print(f"🎯 Target API: {os.environ.get('EKITCHEN_BASE_URL', '(unset!)')}")
    print(f"🖼️  Image dir: {args.images}")
    print(f"🧪 Dry run: {args.dry_run}")
    print("=" * 70)

    if "railway.app" in os.environ.get("EKITCHEN_BASE_URL", ""):
        print("⚠️  TARGET IS PRODUCTION — recipes will be visible to all users.")

    if args.dry_run:
        for i, r in enumerate(recipes, 1):
            print(f"\n[{i}/{len(recipes)}] {r['name']}  ({r.get('servings','?')} servings, "
                  f"{r.get('total_time_minutes','?')} min)")
            print(f"    ingredients ({len(r['ingredients'])}): {', '.join(r['ingredients'])}")
            print(f"    steps: {len(r['steps'])}")
        print("\n✅ Dry run complete — nothing written.")
        return

    from direct_recipe_processor import DirectRecipeProcessor
    processor = DirectRecipeProcessor(log_to_file=True)
    if not getattr(processor, "ekitchen_token", None):
        print("❌ Not authenticated with eKitchen — check EKITCHEN_ADMIN_EMAIL/PASSWORD. Aborting.")
        sys.exit(1)

    created, skipped, failed = [], [], []
    for i, r in enumerate(recipes, 1):
        print(f"\n{'='*70}\n[{i}/{len(recipes)}] {r['name']}\n{'='*70}")
        parsed = {
            "name": r["name"],
            "description": r.get("description", ""),
            "ingredients": r["ingredients"],
            "steps": r["steps"],
            "servings": r.get("servings", 4),
            "prep_time_minutes": r.get("prep_time_minutes", 0),
            "cook_time_minutes": r.get("cook_time_minutes", 0),
            "total_time_minutes": r.get("total_time_minutes", 0),
            "source_url": "",  # authored, not scraped
        }
        try:
            result = processor.process_parsed_recipe(parsed, save_images_dir=args.images)
            if result.success:
                created.append((r["name"], result.recipe_id))
                print(f"✅ Created: {r['name']} -> {result.recipe_id}")
            elif getattr(result, "skipped", False):
                skipped.append(r["name"])
                print(f"⏭️  Skipped (already exists): {r['name']}")
            else:
                failed.append((r["name"], result.error_message))
                print(f"❌ Failed: {r['name']} — {result.error_message}")
        except Exception as e:
            failed.append((r["name"], str(e)))
            print(f"❌ Exception: {r['name']} — {e}")
        if i < len(recipes):
            time.sleep(3)

    print("\n" + "=" * 70)
    print("📊 INGESTION SUMMARY")
    print("=" * 70)
    print(f"✅ Created: {len(created)}")
    for n, rid in created:
        print(f"   - {n} ({rid})")
    print(f"⏭️  Skipped: {len(skipped)}")
    for n in skipped:
        print(f"   - {n}")
    print(f"❌ Failed: {len(failed)}")
    for n, err in failed:
        print(f"   - {n}: {err}")


if __name__ == "__main__":
    main()
