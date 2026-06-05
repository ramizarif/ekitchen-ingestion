#!/usr/bin/env python3
"""
Volume-Anchor Backfill Script (N7b)

After the gram-anchor (N0/N6b) and serving (N6a) passes, the biggest remaining
nutrition-coverage gap is ingredients measured by VOLUME (cup/tablespoon/teaspoon)
that have a gram anchor but no volume->gram density — so "1 cup sugar" can't be
converted to grams. These are concentrated staples: sugar, parsley, pepper, onion,
broths, cornstarch, brown sugar, sesame seed, tomato paste, baking powder, ...

Recipe nutrition converts a recipe unit -> grams via the ingredient's unit_conversions.
The conversions are mutually proportional (relative to the gram anchor / cost unit), so
adding a single "cup" key equal to (grams_per_cup * existing_gram_factor) is consistent
with both cost and nutrition. With "cup" present, the backend's unit bridge derives
tablespoon/teaspoon/fluid-ounce automatically (cup is reachable from any volume unit via
the standard volume table), so we only need to anchor cup.

For each candidate (nutrition present, no "cup" key, has a gram reference):
1. AI-estimate grams per US cup (skips non-volume items: AI returns 0)
2. cup_factor = grams_per_cup * gram_factor   (gram_factor = conv[gram] or 1.0 if cost_unit=gram)
3. Add cup (+ tablespoon/teaspoon/fluid ounce if missing) and "gram" if cost_unit is gram
4. PATCH unit_conversions (+ add the new units to possible_units)

Usage:
    python3 scripts/backfill_volume_anchors.py --dry-run            # preview (counts + sample)
    python3 scripts/backfill_volume_anchors.py --dry-run --limit 5  # cheap preview (5 AI calls)
    python3 scripts/backfill_volume_anchors.py --apply              # apply to all

Note: even --dry-run calls OpenAI to compute the value it *would* write; use --limit
while previewing to bound API spend.
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.ingredient_processor import DirectIngredientProcessor, load_env_file

GRAM_KEYS = {"g", "gram", "grams"}
# Standard fractions of a US cup, used to derive the smaller volume keys from cup.
CUP_SUBUNITS = {"tablespoon": 1.0 / 16.0, "teaspoon": 1.0 / 48.0, "fluid ounce": 1.0 / 8.0}


@dataclass
class VolumeAnchorCandidate:
    id: str
    name: str
    cost_unit: str
    unit_conversions: Dict[str, float]
    possible_units: List[str]
    gram_factor: float  # the existing gram reference (conv[gram] or 1.0 when cost_unit is gram)


class VolumeAnchorBackfiller:
    def __init__(self, log_to_file: bool = True):
        self.processor = DirectIngredientProcessor(log_to_file=log_to_file)
        self.log_to_file = log_to_file
        self.logger = self._setup_logging(log_to_file)
        self.stats = {
            "total_ingredients": 0,
            "already_has_cup": 0,
            "skipped_no_nutrition": 0,
            "skipped_no_gram_ref": 0,
            "candidates_found": 0,
            "successfully_fixed": 0,
            "failed_fixes": 0,
        }

    def _setup_logging(self, log_to_file: bool) -> logging.Logger:
        logger = logging.getLogger("volume_anchor_backfill")
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        if log_to_file:
            log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
            os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(log_dir, f"volume_anchor_backfill_{timestamp}.log")
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
                if len(ingredients) < limit:
                    break
                offset += limit
            except Exception as e:  # noqa: BLE001
                self._log(f"❌ Error fetching ingredients: {e}", "error")
                break
        self._log(f"✅ Total ingredients fetched: {len(all_ingredients)}")
        return all_ingredients

    @staticmethod
    def _gram_factor(conversions: Dict[str, float], cost_unit: Optional[str]) -> Optional[float]:
        """The existing gram reference: conv[gram] if present, else 1.0 when cost_unit is gram."""
        for k, v in conversions.items():
            if k.lower() in GRAM_KEYS and v and v > 0:
                return float(v)
        if cost_unit and cost_unit.lower() in GRAM_KEYS:
            return 1.0
        return None

    def analyze(self, ingredient: Dict[str, Any]) -> Optional[VolumeAnchorCandidate]:
        cost_unit = ingredient.get("estimated_cost_unit") or ""
        try:
            conversions = json.loads(ingredient.get("unit_conversions") or "{}")
        except json.JSONDecodeError:
            conversions = {}
        if not isinstance(conversions, dict):
            conversions = {}

        # Already cup-convertible.
        if any(k.lower() == "cup" for k in conversions.keys()):
            self.stats["already_has_cup"] += 1
            return None

        # Needs nutrition to be worth anchoring (no-nutrition ingredients contribute nothing).
        cal = ingredient.get("calories") or 0
        fat = ingredient.get("fat") or 0
        pro = ingredient.get("protein") or 0
        carb = ingredient.get("carbohydrates") or 0
        sug = ingredient.get("sugar") or 0
        if cal <= 0 and fat <= 0 and pro <= 0 and carb <= 0 and sug <= 0:
            self.stats["skipped_no_nutrition"] += 1
            return None

        gram_factor = self._gram_factor(conversions, cost_unit)
        if gram_factor is None:
            # No gram reference and cost_unit isn't gram — can't place a cup key consistently.
            self.stats["skipped_no_gram_ref"] += 1
            return None

        return VolumeAnchorCandidate(
            id=ingredient.get("id"),
            name=ingredient.get("name", "Unknown"),
            cost_unit=cost_unit,
            unit_conversions=conversions,
            possible_units=ingredient.get("possible_units", []) or [],
            gram_factor=gram_factor,
        )

    def fix(self, candidate: VolumeAnchorCandidate, dry_run: bool) -> str:
        """Returns 'fixed' or 'failed'."""
        self._log(f"\n🔧 {'[DRY RUN] ' if dry_run else ''}{candidate.name} (cost_unit={candidate.cost_unit})")

        grams_per_cup = self.processor.estimate_grams_per_cup(candidate.name)
        if not grams_per_cup or grams_per_cup <= 0:
            self._log("   ⏭️  Not volume-measured / no density — skipping", "warning")
            return "failed"

        conversions = dict(candidate.unit_conversions)
        cup_factor = grams_per_cup * candidate.gram_factor
        conversions["cup"] = cup_factor
        # Derive the smaller volume units (only if absent — never clobber existing data).
        for unit, frac in CUP_SUBUNITS.items():
            if unit not in conversions:
                conversions[unit] = cup_factor * frac
        # Ensure a gram key exists so cup->gram resolves directly (cost_unit=gram case).
        if not any(k.lower() in GRAM_KEYS for k in conversions):
            conversions["gram"] = 1.0

        possible_units = candidate.possible_units.copy()
        for u in ("cup", "tablespoon", "teaspoon"):
            if u not in possible_units:
                possible_units.append(u)

        self._log(f"   ✅ 1 cup = {grams_per_cup:.0f}g  -> cup_factor={cup_factor:.3f} (gram_ref={candidate.gram_factor})")
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
        self._log("🚀 Volume-Anchor Backfill (N7b)")
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
            f"\n📋 {len(candidates)} candidates missing a cup anchor "
            f"({self.stats['already_has_cup']} already cup-convertible, "
            f"{self.stats['skipped_no_nutrition']} no-nutrition, "
            f"{self.stats['skipped_no_gram_ref']} no gram reference)"
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
                else:
                    self.stats["failed_fixes"] += 1
            except Exception as e:  # noqa: BLE001
                self._log(f"❌ Unexpected error on {candidate.name}: {e}", "error")
                self.stats["failed_fixes"] += 1

        self.summary()

    def summary(self):
        self._log("\n" + "=" * 70)
        self._log("📊 VOLUME-ANCHOR BACKFILL SUMMARY")
        self._log("=" * 70)
        for k, v in self.stats.items():
            self._log(f"{k.replace('_', ' ').title()}: {v}")
        attempted = self.stats["successfully_fixed"] + self.stats["failed_fixes"]
        self._log(f"Success rate (of attempted): {self.stats['successfully_fixed'] / (attempted or 1) * 100:.1f}%")
        self._log("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Backfill volume (cup) anchors into ingredient unit_conversions")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    parser.add_argument("--limit", type=int, help="Max ingredients to process")
    parser.add_argument("--no-logs", action="store_true", help="Disable file logging")
    args = parser.parse_args()

    if args.dry_run == args.apply:
        print("❌ Specify exactly one of --dry-run or --apply")
        return

    backfiller = VolumeAnchorBackfiller(log_to_file=not args.no_logs)
    backfiller.run(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
