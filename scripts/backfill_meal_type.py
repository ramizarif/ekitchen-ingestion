#!/usr/bin/env python3
"""
Meal-Type Backfill (F2)

Classifies every global recipe into a single primary meal_type
(breakfast/lunch/dinner/dessert/snack/appetizer/side) for the composable discover feed.

Two-pass to minimize AI cost:
  1. SEED from existing recipe tags — ~42% of recipes already carry a meal-type tag
     ("dinner", "main course", "dessert", "brunch", ...). Normalize those to the canonical
     set for free (no AI call).
  2. AI-classify the rest from name + description (gpt-4o-mini), mirroring
     backfill_dietary_classification.py.

Applies via the dedicated admin endpoint:
    POST /admin/global-recipes/{id}/meal-type?meal_type=<value>

Requires the backend deployed with the meal_type column + endpoint (F1).

Usage:
    python3 scripts/backfill_meal_type.py --dry-run            # classify, no writes
    python3 scripts/backfill_meal_type.py --dry-run --limit 20
    python3 scripts/backfill_meal_type.py --apply              # classify + persist all
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.ingredient_processor import DirectIngredientProcessor, load_env_file

CANONICAL_MEAL_TYPES = {"breakfast", "lunch", "dinner", "dessert", "snack", "appetizer", "side"}

# Raw recipe-tag -> canonical meal_type (mirrors the meal-type facet of the backend's
# vibe_tags canonical map; folds noisy synonyms like "main course"/"entree" into "dinner").
MEALTYPE_TAG_MAP = {
    "dinner": "dinner", "main course": "dinner", "main dish": "dinner", "entree": "dinner", "entrée": "dinner",
    "dessert": "dessert",
    "breakfast": "breakfast", "brunch": "breakfast",
    "lunch": "lunch",
    "appetizer": "appetizer", "starter": "appetizer", "appetizers": "appetizer",
    "snack": "snack",
    "side dish": "side", "side": "side",
}
# When a recipe carries multiple meal-type tags, pick the most "primary" one.
MEALTYPE_PRIORITY = ["dinner", "lunch", "breakfast", "dessert", "appetizer", "snack", "side"]


def seed_from_tags(tag_names: List[str]) -> Optional[str]:
    found = set()
    for t in tag_names or []:
        canon = MEALTYPE_TAG_MAP.get(str(t).strip().lower())
        if canon:
            found.add(canon)
    for mt in MEALTYPE_PRIORITY:
        if mt in found:
            return mt
    return None


class MealTypeBackfiller:
    def __init__(self, log_to_file: bool = True):
        self.processor = DirectIngredientProcessor(log_to_file=log_to_file)
        self.log_to_file = log_to_file
        self.logger = self._setup_logging(log_to_file)
        self.stats = {
            "total_recipes": 0,
            "seeded_from_tags": 0,
            "ai_classified": 0,
            "applied": 0,
            "errors": 0,
            "unclassifiable": 0,
        }
        self.distribution: Dict[str, int] = {}

    def _setup_logging(self, log_to_file: bool) -> logging.Logger:
        logger = logging.getLogger("meal_type_backfill")
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        if log_to_file:
            log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
            os.makedirs(log_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fh = logging.FileHandler(os.path.join(log_dir, f"meal_type_backfill_{ts}.log"))
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            logger.addHandler(fh)
            print(f"📝 Logging to: logs/meal_type_backfill_{ts}.log")
        return logger

    def _log(self, message: str, level: str = "info"):
        print(message)
        if self.log_to_file:
            getattr(self.logger, level if level in ("debug", "error", "warning") else "info")(message)

    def authenticate(self) -> bool:
        env_vars = load_env_file(os.path.join(os.path.dirname(__file__), "..", "local.env"))
        email = env_vars.get("EKITCHEN_ADMIN_EMAIL")
        password = env_vars.get("EKITCHEN_ADMIN_PASSWORD")
        if not email or not password:
            self._log("❌ Missing eKitchen admin credentials in local.env", "error")
            return False
        return self.processor.authenticate_ekitchen(email, password)

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.processor.access_token}", "Content-Type": "application/json"}

    def get_all_recipes(self) -> List[Dict[str, Any]]:
        self._log("🔍 Fetching all global recipes...")
        recipes: List[Dict[str, Any]] = []
        offset, limit = 0, 50
        while True:
            try:
                url = f"{self.processor.ekitchen_base_url}/global-recipes?limit={limit}&offset={offset}"
                resp = requests.get(url, headers=self._headers(), timeout=30)
                if resp.status_code != 200:
                    self._log(f"❌ Failed to fetch recipes: {resp.status_code}", "error")
                    break
                data = resp.json()
                batch = data if isinstance(data, list) else data.get("recipes", [])
                if not batch:
                    break
                recipes.extend(batch)
                if len(batch) < limit:
                    break
                offset += limit
            except Exception as e:  # noqa: BLE001
                self._log(f"❌ Error fetching recipes: {e}", "error")
                break
        self._log(f"✅ Fetched {len(recipes)} recipes")
        return recipes

    def classify_with_ai(self, name: str, description: str) -> Optional[str]:
        client = self.processor.openai_client
        if not client:
            self._log("   ⚠️ OpenAI not available", "warning")
            return None
        try:
            prompt = f"""Classify this recipe into exactly ONE meal type.

Recipe name: "{name}"
Description: "{(description or '')[:300]}"

Allowed meal types: breakfast, lunch, dinner, dessert, snack, appetizer, side

Rules:
- Pick the single most typical meal type for this dish.
- Sweet baked goods / treats -> dessert. Dips/small bites served before a meal -> appetizer.
- Side dishes (not a main) -> side. Light/handheld between-meal food -> snack.
- A substantial savory main -> dinner (default for mains).

Return ONLY the meal type word, nothing else."""
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4,
                temperature=0.0,
            )
            answer = resp.choices[0].message.content.strip().lower().strip(".")
            if answer in CANONICAL_MEAL_TYPES:
                return answer
            # tolerate minor variants
            for mt in CANONICAL_MEAL_TYPES:
                if mt in answer:
                    return mt
            self._log(f"   ⚠️ AI returned unrecognized meal type '{answer}' for '{name}'", "warning")
            return None
        except Exception as e:  # noqa: BLE001
            self._log(f"   ❌ AI classification failed for '{name}': {e}", "error")
            return None

    def apply(self, recipe_id: str, meal_type: str) -> bool:
        url = f"{self.processor.ekitchen_base_url}/admin/global-recipes/{recipe_id}/meal-type?meal_type={meal_type}"
        resp = requests.post(url, headers=self._headers(), timeout=30)
        if resp.status_code == 200:
            return True
        self._log(f"   ❌ apply failed: {resp.status_code} - {resp.text[:160]}", "error")
        return False

    def run(self, dry_run: bool, limit: Optional[int] = None):
        self._log("🚀 Meal-Type Backfill (F2)")
        self._log("=" * 70)
        self._log(f"Mode: {'DRY RUN (no writes)' if dry_run else 'APPLY'}")
        self._log("=" * 70)
        if not self.authenticate():
            self._log("❌ Authentication failed", "error")
            return
        recipes = self.get_all_recipes()
        if not recipes:
            return
        self.stats["total_recipes"] = len(recipes)
        if limit:
            recipes = recipes[:limit]
            self._log(f"🎯 Processing first {len(recipes)} (limit applied)")

        for i, rec in enumerate(recipes):
            rid = rec.get("id")
            name = rec.get("name", "")
            meal_type = seed_from_tags(rec.get("tag_names", []))
            source = "tags"
            if meal_type:
                self.stats["seeded_from_tags"] += 1
            else:
                meal_type = self.classify_with_ai(name, rec.get("description", ""))
                source = "ai"
                if meal_type:
                    self.stats["ai_classified"] += 1
            if not meal_type:
                self.stats["unclassifiable"] += 1
                continue

            self.distribution[meal_type] = self.distribution.get(meal_type, 0) + 1
            if i < 12 or source == "ai":
                self._log(f"   [{source}] {meal_type:9s} <- {name}")
            if not dry_run:
                if self.apply(rid, meal_type):
                    self.stats["applied"] += 1
                else:
                    self.stats["errors"] += 1
                time.sleep(0.03)
            if (i + 1) % 100 == 0:
                self._log(f"   ... {i + 1}/{len(recipes)}")

        self.summary()

    def summary(self):
        self._log("\n" + "=" * 70)
        self._log("📊 MEAL-TYPE BACKFILL SUMMARY")
        self._log("=" * 70)
        for k, v in self.stats.items():
            self._log(f"{k.replace('_', ' ').title()}: {v}")
        self._log("Distribution:")
        for mt in MEALTYPE_PRIORITY:
            self._log(f"  {mt:9s}: {self.distribution.get(mt, 0)}")
        self._log("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Backfill meal_type for global recipes")
    parser.add_argument("--dry-run", action="store_true", help="Classify without writing")
    parser.add_argument("--apply", action="store_true", help="Classify + persist")
    parser.add_argument("--limit", type=int, help="Max recipes to process")
    parser.add_argument("--no-logs", action="store_true", help="Disable file logging")
    args = parser.parse_args()
    if args.dry_run == args.apply:
        print("❌ Specify exactly one of --dry-run or --apply")
        return
    MealTypeBackfiller(log_to_file=not args.no_logs).run(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
