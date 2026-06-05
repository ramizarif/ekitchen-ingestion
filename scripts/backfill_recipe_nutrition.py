#!/usr/bin/env python3
"""
Recipe Nutrition Backfill (N3)

Triggers the backend's recompute-nutrition endpoint for every global recipe, which:
  - computes per-serving macros from ingredient quantities x per-100g nutrition (N1+N5+N6+N7)
  - persists calories/fat/protein/carbohydrates/sugar onto global_recipes
  - syncs the macro-derived diet tags (keto/low-carb/high-protein/low-calorie/low-fat) via
    recipe_tag_links (D2a)

All the math lives in the backend; this script just drives it recipe-by-recipe and reports
the coverage distribution so we can verify the catalog matches the read-only harness numbers.

Requires the backend deployed with the recompute endpoint
(POST /admin/global-recipes/{id}/recompute-nutrition, admin-only).

Usage:
    python3 scripts/backfill_recipe_nutrition.py --dry-run         # list recipes, no writes
    python3 scripts/backfill_recipe_nutrition.py --dry-run --limit 5
    python3 scripts/backfill_recipe_nutrition.py --apply           # recompute + persist all
    python3 scripts/backfill_recipe_nutrition.py --apply --limit 20
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

CONFIDENT_COVERAGE = 0.70  # mirrors backend nutritionCoverageThreshold


class RecipeNutritionBackfiller:
    def __init__(self, log_to_file: bool = True):
        self.processor = DirectIngredientProcessor(log_to_file=log_to_file)
        self.log_to_file = log_to_file
        self.logger = self._setup_logging(log_to_file)
        self.stats = {
            "total_recipes": 0,
            "recomputed": 0,
            "confident": 0,   # coverage >= 0.70
            "estimated": 0,   # coverage < 0.70
            "errors": 0,
        }
        self.coverage_buckets = [0] * 11  # 0-9%,...,100%
        self.tag_counts: Dict[str, int] = {}

    def _setup_logging(self, log_to_file: bool) -> logging.Logger:
        logger = logging.getLogger("recipe_nutrition_backfill")
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        if log_to_file:
            log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
            os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(log_dir, f"recipe_nutrition_backfill_{timestamp}.log")
            fh = logging.FileHandler(log_file)
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            logger.addHandler(fh)
            print(f"📝 Logging to: {log_file}")
        return logger

    def _log(self, message: str, level: str = "info"):
        print(message)
        if self.log_to_file:
            getattr(self.logger, level if level in ("debug", "error", "warning") else "info")(message)

    def authenticate(self) -> bool:
        env_file_path = os.path.join(os.path.dirname(__file__), "..", "local.env")
        env_vars = load_env_file(env_file_path)
        admin_email = env_vars.get("EKITCHEN_ADMIN_EMAIL")
        admin_password = env_vars.get("EKITCHEN_ADMIN_PASSWORD")
        if not admin_email or not admin_password:
            self._log("❌ Missing eKitchen admin credentials in local.env", "error")
            return False
        return self.processor.authenticate_ekitchen(admin_email, admin_password)

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.processor.access_token}", "Content-Type": "application/json"}

    def get_all_recipe_ids(self) -> List[Dict[str, str]]:
        self._log("🔍 Fetching all global recipes...")
        recipes: List[Dict[str, str]] = []
        offset, limit = 0, 50
        while True:
            try:
                url = f"{self.processor.ekitchen_base_url}/global-recipes?limit={limit}&offset={offset}"
                resp = requests.get(url, headers=self._headers(), timeout=30)
                if resp.status_code != 200:
                    self._log(f"❌ Failed to fetch recipes: {resp.status_code} - {resp.text[:200]}", "error")
                    break
                data = resp.json()
                batch = data if isinstance(data, list) else data.get("recipes", [])
                if not batch:
                    break
                for r in batch:
                    recipes.append({"id": r.get("id"), "name": r.get("name", "")})
                if len(batch) < limit:
                    break
                offset += limit
            except Exception as e:  # noqa: BLE001
                self._log(f"❌ Error fetching recipes: {e}", "error")
                break
        self._log(f"✅ Fetched {len(recipes)} recipes")
        return recipes

    def recompute(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.processor.ekitchen_base_url}/admin/global-recipes/{recipe_id}/recompute-nutrition"
        resp = requests.post(url, headers=self._headers(), timeout=30)
        if resp.status_code != 200:
            self._log(f"   ❌ recompute failed: {resp.status_code} - {resp.text[:200]}", "error")
            return None
        return resp.json()

    def run(self, dry_run: bool, limit: Optional[int] = None):
        self._log("🚀 Recipe Nutrition Backfill (N3)")
        self._log("=" * 70)
        self._log(f"Mode: {'DRY RUN (no writes)' if dry_run else 'APPLY (recompute + persist)'}")
        self._log("=" * 70)

        if not self.authenticate():
            self._log("❌ Authentication failed", "error")
            return
        recipes = self.get_all_recipe_ids()
        if not recipes:
            return
        self.stats["total_recipes"] = len(recipes)
        if limit:
            recipes = recipes[:limit]
            self._log(f"🎯 Processing first {len(recipes)} (limit applied)")

        for i, rec in enumerate(recipes):
            if dry_run:
                if i < 10:
                    self._log(f"   [DRY RUN] would recompute {rec['name']} ({rec['id']})")
                continue
            try:
                result = self.recompute(rec["id"])
                if result is None:
                    self.stats["errors"] += 1
                    continue
                self.stats["recomputed"] += 1
                coverage = float(result.get("coverage", 0.0))
                if result.get("is_estimated", True):
                    self.stats["estimated"] += 1
                else:
                    self.stats["confident"] += 1
                b = min(int(coverage * 10), 10)
                self.coverage_buckets[b] += 1
                if (i + 1) % 50 == 0:
                    self._log(f"   ... {i + 1}/{len(recipes)} (confident so far: {self.stats['confident']})")
                time.sleep(0.05)  # gentle on the backend
            except Exception as e:  # noqa: BLE001
                self._log(f"❌ Error on {rec['name']}: {e}", "error")
                self.stats["errors"] += 1

        self.summary(dry_run)

    def summary(self, dry_run: bool):
        self._log("\n" + "=" * 70)
        self._log("📊 RECIPE NUTRITION BACKFILL SUMMARY")
        self._log("=" * 70)
        for k, v in self.stats.items():
            self._log(f"{k.replace('_', ' ').title()}: {v}")
        if not dry_run and self.stats["recomputed"] > 0:
            conf_pct = self.stats["confident"] / self.stats["recomputed"] * 100
            self._log(f"Confident (coverage >= {CONFIDENT_COVERAGE:.0%}): {conf_pct:.1f}%")
            self._log("Coverage histogram:")
            for b in range(11):
                self._log(f"  {b*10:3d}%-{b*10+9:3d}%: {self.coverage_buckets[b]}")
        self._log("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Backfill recipe nutrition via the recompute endpoint")
    parser.add_argument("--dry-run", action="store_true", help="List recipes without recomputing")
    parser.add_argument("--apply", action="store_true", help="Recompute + persist for all recipes")
    parser.add_argument("--limit", type=int, help="Max recipes to process")
    parser.add_argument("--no-logs", action="store_true", help="Disable file logging")
    args = parser.parse_args()

    if args.dry_run == args.apply:
        print("❌ Specify exactly one of --dry-run or --apply")
        return

    RecipeNutritionBackfiller(log_to_file=not args.no_logs).run(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
