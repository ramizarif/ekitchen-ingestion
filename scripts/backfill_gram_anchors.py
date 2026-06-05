#!/usr/bin/env python3
"""
Gram-Anchor Backfill Script

Recipe nutrition is computed in the backend as (grams_used / base_weight) * per-100g
macro. Converting a recipe's quantity to grams requires the ingredient's `unit_conversions`
to contain a gram entry — and because conversions are stored relative to the cost unit,
adding a single "gram" key makes EVERY unit already in the map gram-convertible.

As of 2026-06-05 only ~60% of ingredients (and ~44% of recipes, per-ingredient weighted)
have a gram anchor, so most recipes can't get confident nutrition. This script closes
that gap:

1. Fetch all global ingredients from eKitchen
2. Find those whose unit_conversions has no gram key (and whose cost_unit isn't already
   a gram unit)
3. Fetch the gram->cost_unit conversion from Spoonacular (reusing the processor's
   get_unit_conversions), with the AI estimate as a fallback
4. PATCH the ingredient's unit_conversions (+ add "gram" to possible_units)

Usage:
    python3 scripts/backfill_gram_anchors.py --dry-run            # preview (counts + sample)
    python3 scripts/backfill_gram_anchors.py --dry-run --limit 5  # cheap preview (5 API calls)
    python3 scripts/backfill_gram_anchors.py --apply              # apply to all

Note: even --dry-run calls Spoonacular to compute the real value it *would* write, so use
--limit while previewing to bound API spend.
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

# Match the canonical scripts/ import style (see backfill_dietary_classification.py).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.ingredient_processor import DirectIngredientProcessor, load_env_file

GRAM_KEYS = {"g", "gram", "grams"}

# Gram conversions are only physically meaningful when the cost unit is a weight or volume.
# For count cost units (pepper/piece/clove/can...) gram->cost_unit is ill-defined, so we
# skip rather than write a bogus AI-guessed factor (a wrong factor is worse than none —
# N1 will just flag the ingredient as uncounted).
WEIGHT_VOLUME_UNITS = {
    "g", "gram", "grams", "kg", "kilogram", "kilograms", "oz", "ounce", "ounces",
    "lb", "pound", "pounds", "mg", "milligram", "milligrams",
    "ml", "milliliter", "milliliters", "l", "liter", "liters", "cup", "cups",
    "tablespoon", "tablespoons", "tbsp", "teaspoon", "teaspoons", "tsp",
    "fl oz", "fluid ounce", "fluid ounces", "pint", "pints", "quart", "quarts",
    "gallon", "gallons",
}


@dataclass
class GramAnchorCandidate:
    id: str
    name: str
    cost_unit: str
    unit_conversions: Dict[str, float]
    possible_units: List[str]


class GramAnchorBackfiller:
    def __init__(self, log_to_file: bool = True):
        self.processor = DirectIngredientProcessor(log_to_file=log_to_file)
        self.log_to_file = log_to_file
        self.logger = self._setup_logging(log_to_file)
        self.stats = {
            "total_ingredients": 0,
            "already_anchored": 0,
            "candidates_found": 0,
            "successfully_fixed": 0,
            "failed_fixes": 0,
            "skipped_no_cost_unit": 0,
            "skipped_count_unit": 0,
        }

    def _setup_logging(self, log_to_file: bool) -> logging.Logger:
        logger = logging.getLogger("gram_anchor_backfill")
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        if log_to_file:
            log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
            os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(log_dir, f"gram_anchor_backfill_{timestamp}.log")
            fh = logging.FileHandler(log_file)
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"))
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

    def get_all_ingredients(self) -> List[Dict[str, Any]]:
        if not self.processor.access_token:
            self._log("❌ Not authenticated with eKitchen", "error")
            return []
        self._log("🔍 Fetching all ingredients from eKitchen...")
        all_ingredients: List[Dict[str, Any]] = []
        offset, limit = 0, 50
        while True:
            try:
                url = f"{self.processor.ekitchen_base_url}/global-ingredients?limit={limit}&offset={offset}"
                headers = {"Authorization": f"Bearer {self.processor.access_token}", "Content-Type": "application/json"}
                resp = requests.get(url, headers=headers, timeout=30)
                if resp.status_code != 200:
                    self._log(f"❌ Failed to fetch ingredients: {resp.status_code}", "error")
                    break
                data = resp.json()
                ingredients = data if isinstance(data, list) else data.get("ingredients", [])
                if not ingredients:
                    break
                all_ingredients.extend(ingredients)
                self._log(f"   📥 Fetched {len(ingredients)} (total: {len(all_ingredients)})")
                if len(ingredients) < limit:
                    break
                offset += limit
            except Exception as e:  # noqa: BLE001
                self._log(f"❌ Error fetching ingredients: {e}", "error")
                break
        self._log(f"✅ Total ingredients fetched: {len(all_ingredients)}")
        return all_ingredients

    @staticmethod
    def _has_gram_anchor(conversions: Dict[str, float], cost_unit: Optional[str]) -> bool:
        if any(k.lower() in GRAM_KEYS for k in conversions.keys()):
            return True
        # Cost unit being grams means the identity conversion already anchors grams.
        return bool(cost_unit and cost_unit.lower() in GRAM_KEYS)

    def analyze(self, ingredient: Dict[str, Any]) -> Optional[GramAnchorCandidate]:
        cost_unit = ingredient.get("estimated_cost_unit")
        try:
            conversions = json.loads(ingredient.get("unit_conversions") or "{}")
        except json.JSONDecodeError:
            conversions = {}
        if not isinstance(conversions, dict):
            conversions = {}

        if self._has_gram_anchor(conversions, cost_unit):
            self.stats["already_anchored"] += 1
            return None

        # Without a cost unit the existing factors have no shared base to anchor against.
        if not cost_unit:
            self.stats["skipped_no_cost_unit"] += 1
            return None

        return GramAnchorCandidate(
            id=ingredient.get("id"),
            name=ingredient.get("name", "Unknown"),
            cost_unit=cost_unit,
            unit_conversions=conversions,
            possible_units=ingredient.get("possible_units", []) or [],
        )

    def _fetch_gram_factor(self, name: str, cost_unit: str) -> Optional[float]:
        """grams anchor = cost-units per 1 gram (so cup->gram works via from/to ratio)."""
        # Primary: Spoonacular convert via the processor (handles rate-limit + headers).
        result = self.processor.get_unit_conversions(name, ["gram"], cost_unit) or {}
        for k, v in result.items():
            if k.lower() in GRAM_KEYS and v and v > 0:
                return float(v)
        # Fallback: AI estimate of 1 gram -> cost_unit, but ONLY for weight/volume cost
        # units. gram->count (pepper/piece/can) is ill-defined; skip so N1 flags it instead
        # of trusting a bogus factor.
        if cost_unit.lower() not in WEIGHT_VOLUME_UNITS:
            self._log(f"   ⏭️  Skipping {name}: count cost_unit '{cost_unit}' has no meaningful gram conversion", "warning")
            return None
        try:
            est = self.processor.estimate_purchase_unit_conversion(name, "gram", cost_unit, 1.0)
            if est and est > 0:
                self._log(f"   🤖 AI-estimated gram factor for {name}: {est}")
                return float(est)
        except Exception as e:  # noqa: BLE001
            self._log(f"   ⚠️ AI estimate failed for {name}: {e}", "warning")
        return None

    def fix(self, candidate: GramAnchorCandidate, dry_run: bool) -> str:
        """Returns 'fixed', 'skipped' (count cost unit), or 'failed'."""
        self._log(f"\n🔧 {'[DRY RUN] ' if dry_run else ''}{candidate.name} (cost_unit={candidate.cost_unit})")

        # Count cost units (pepper/piece/can...) have no meaningful gram conversion — skip
        # rather than guess, so we never write a wrong factor. (Saves the API call too.)
        if candidate.cost_unit.lower() not in WEIGHT_VOLUME_UNITS:
            self._log(f"   ⏭️  Skipping: count cost_unit '{candidate.cost_unit}' — gram conversion not meaningful", "warning")
            return "skipped"

        gram_factor = self._fetch_gram_factor(candidate.name, candidate.cost_unit)
        if gram_factor is None:
            self._log("   ❌ Could not determine a gram conversion", "error")
            return "failed"

        conversions = dict(candidate.unit_conversions)
        conversions["gram"] = gram_factor
        conversions.setdefault(candidate.cost_unit, 1.0)  # keep cost-unit identity
        possible_units = candidate.possible_units.copy()
        if not any(u.lower() in GRAM_KEYS for u in possible_units):
            possible_units.append("gram")

        self._log(f"   ✅ 1 gram = {gram_factor} {candidate.cost_unit}  (now {len(conversions)} conversions)")
        if dry_run:
            return "fixed"
        return "fixed" if self.update_ingredient(candidate.id, possible_units, conversions) else "failed"

    def update_ingredient(self, ingredient_id: str, possible_units: List[str], conversions: Dict[str, float]) -> bool:
        try:
            payload = json.dumps(
                {"id": ingredient_id, "possible_units": possible_units, "unit_conversions": json.dumps(conversions)}
            ).encode("utf-8")
            url = f"{self.processor.ekitchen_base_url}/global-ingredients/{ingredient_id}"
            headers = {"Authorization": f"Bearer {self.processor.access_token}", "Content-Type": "application/json"}
            resp = requests.patch(url, data=payload, headers=headers, timeout=30)
            if resp.status_code == 200:
                return True
            self._log(f"   ❌ Update failed: {resp.status_code} - {resp.text}", "error")
            return False
        except Exception as e:  # noqa: BLE001
            self._log(f"   ❌ Error updating ingredient: {e}", "error")
            return False

    def run(self, dry_run: bool, limit: Optional[int] = None):
        self._log("🚀 Gram-Anchor Backfill")
        self._log("=" * 70)
        self._log(f"Mode: {'DRY RUN (preview only)' if dry_run else 'APPLY CHANGES'}")
        if limit:
            self._log(f"Limit: {limit}")
        self._log("=" * 70)

        if not self.authenticate():
            self._log("❌ Authentication failed", "error")
            return
        ingredients = self.get_all_ingredients()
        if not ingredients:
            return
        self.stats["total_ingredients"] = len(ingredients)

        candidates = [c for c in (self.analyze(i) for i in ingredients) if c]
        self.stats["candidates_found"] = len(candidates)
        self._log(
            f"\n📋 {len(candidates)} ingredients missing a gram anchor "
            f"({self.stats['already_anchored']} already anchored, "
            f"{self.stats['skipped_no_cost_unit']} skipped: no cost_unit)"
        )
        if limit:
            candidates = candidates[:limit]
            self._log(f"🎯 Processing first {len(candidates)} (limit applied)")

        for i, candidate in enumerate(candidates):
            self._log(f"\n--- {i + 1}/{len(candidates)} ---")
            try:
                result = self.fix(candidate, dry_run)
                if result == "fixed":
                    self.stats["successfully_fixed"] += 1
                elif result == "skipped":
                    self.stats["skipped_count_unit"] += 1
                else:
                    self.stats["failed_fixes"] += 1
            except Exception as e:  # noqa: BLE001
                self._log(f"❌ Unexpected error on {candidate.name}: {e}", "error")
                self.stats["failed_fixes"] += 1

        self.summary()

    def summary(self):
        self._log("\n" + "=" * 70)
        self._log("📊 GRAM-ANCHOR BACKFILL SUMMARY")
        self._log("=" * 70)
        for k, v in self.stats.items():
            self._log(f"{k.replace('_', ' ').title()}: {v}")
        attempted = self.stats["successfully_fixed"] + self.stats["failed_fixes"]
        self._log(f"Success rate (of attempted, excl. skips): {self.stats['successfully_fixed'] / (attempted or 1) * 100:.1f}%")
        self._log("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Backfill gram anchors into ingredient unit_conversions")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    parser.add_argument("--limit", type=int, help="Max ingredients to process")
    parser.add_argument("--no-logs", action="store_true", help="Disable file logging")
    args = parser.parse_args()

    if args.dry_run == args.apply:
        print("❌ Specify exactly one of --dry-run or --apply")
        return

    backfiller = GramAnchorBackfiller(log_to_file=not args.no_logs)
    backfiller.run(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
