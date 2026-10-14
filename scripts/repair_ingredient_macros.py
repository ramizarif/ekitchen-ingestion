#!/usr/bin/env python3
"""
Repair fat / carbohydrates on global ingredients corrupted by the old substring nutrient parser.

Before fix/exact-nutrient-names, Spoonacular's "Trans Fat" overwrote "Fat" and "Net Carbohydrates"
overwrote "Carbohydrates". This script finds ingredients whose stored fat is far below what their
calories imply, re-fetches each one from Spoonacular by its stored external_id (parsed with the
fixed extract_macros), and corrects Fat and Carbohydrates. Nothing else is touched.

A refetch is only trusted when Spoonacular's calories for that ID agree with the stored calories
(within CALORIE_TOLERANCE). Disagreement means the stored row was matched to a different food;
those are reported for hand review, never written.

Dry run by default. Fetched Spoonacular data is cached per ID so a later --apply (or a run
against another environment) does not spend API calls again.

Usage:
    source local.env   # SPOONACULAR_* and EKITCHEN_ADMIN_* for the target
    python scripts/repair_ingredient_macros.py --base-url http://localhost:8081            # dry run
    python scripts/repair_ingredient_macros.py --base-url http://localhost:8081 --apply    # write
"""
import argparse
import csv
import json
import os
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.backfill_enrichment import fetch_all_ingredients, login, update_ingredient  # noqa: E402
from services.ingredient_processor import DirectIngredientProcessor  # noqa: E402

# An ingredient is a candidate when its calories imply at least this much fat per 100g...
MIN_IMPLIED_FAT = 5.0
# ...and its stored fat is below this fraction of that.
BROKEN_FAT_FRACTION = 0.25
# Spoonacular's calories for the stored ID must be within this of the stored calories.
CALORIE_TOLERANCE = 0.15
# A corrected value must differ by at least this many grams to be worth writing.
MIN_CHANGE_G = 0.5

# Rows whose stored Spoonacular ID is a different food from the ingredient (pumpkin seed -> pumpkin
# seed OIL). Their calories already agree with that wrong food, so the calorie check cannot catch
# them; correcting fat would only make the wrong food consistent. They need re-matching, not this.
MISIDENTIFIED = [
    "pumpkin seed", "chicken meat", "ice cream", "chocolate chip", "sun-dried tomato", "sauce", "cha lua",
]

DEFAULT_CACHE = os.path.join(os.path.dirname(__file__), "..", "logs", "spoonacular_macro_cache.json")


def num(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def implied_fat(ing: Dict[str, Any]) -> float:
    return (num(ing.get("calories")) - 4 * num(ing.get("protein")) - 4 * num(ing.get("carbohydrates"))) / 9.0


def is_candidate(ing: Dict[str, Any]) -> bool:
    ext = str(ing.get("external_id") or "").strip()
    if not ext.isdigit() or num(ing.get("calories")) <= 0:
        return False
    imp = implied_fat(ing)
    return imp > MIN_IMPLIED_FAT and num(ing.get("fat")) < BROKEN_FAT_FRACTION * imp


def load_cache(path: str) -> Dict[str, Any]:
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_cache(path: str, cache: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(cache, fh, indent=1, sort_keys=True)


def fetch_macros(processor: DirectIngredientProcessor, cache: Dict[str, Any], ext_id: str, name: str) -> Optional[Dict[str, Any]]:
    if ext_id in cache:
        return cache[ext_id]
    data = processor.get_spoonacular_nutrition_enhanced(int(ext_id), name)
    if data is None:
        return None
    cache[ext_id] = {
        "name": data.name,
        "calories": data.calories,
        "protein": data.protein,
        "fat": data.fat,
        "carbohydrates": data.carbohydrates,
    }
    return cache[ext_id]


def plan_repair(ing: Dict[str, Any], fetched: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    row = {
        "id": ing.get("id"),
        "name": ing.get("name"),
        "external_id": ing.get("external_id"),
        "spoonacular_name": (fetched or {}).get("name", ""),
        "calories": num(ing.get("calories")),
        "spoon_calories": num((fetched or {}).get("calories")),
        "fat_before": num(ing.get("fat")),
        "fat_after": None,
        "carbs_before": num(ing.get("carbohydrates")),
        "carbs_after": None,
        "action": "",
    }
    if fetched is None:
        row["action"] = "skip: spoonacular fetch failed"
        return row
    if fetched.get("fat") is None:
        row["action"] = "skip: spoonacular reports no fat"
        return row
    cal, spoon_cal = row["calories"], row["spoon_calories"]
    if spoon_cal <= 0 or abs(spoon_cal - cal) > CALORIE_TOLERANCE * max(cal, spoon_cal):
        row["action"] = "review: calories disagree (stored row may be a different food)"
        return row

    update: Dict[str, Any] = {}
    if abs(num(fetched["fat"]) - row["fat_before"]) >= MIN_CHANGE_G:
        row["fat_after"] = num(fetched["fat"])
        update["fat"] = row["fat_after"]
    if fetched.get("carbohydrates") is not None and abs(num(fetched["carbohydrates"]) - row["carbs_before"]) >= MIN_CHANGE_G:
        row["carbs_after"] = num(fetched["carbohydrates"])
        update["carbohydrates"] = row["carbs_after"]
    row["action"] = "update" if update else "skip: already correct"
    row["_update"] = update
    return row


def confirm_remote(base_url: str) -> bool:
    host = urlparse(base_url).hostname or base_url
    if host in ("localhost", "127.0.0.1"):
        return True
    answer = input(f"About to WRITE to {host}. Type the host name to continue: ").strip()
    return answer == host


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", required=True, help="eKitchen backend to read from and (with --apply) write to")
    parser.add_argument("--apply", action="store_true", help="write the corrections (default: dry run)")
    parser.add_argument("--cache", default=DEFAULT_CACHE, help="Spoonacular response cache (JSON)")
    parser.add_argument("--out", default=None, help="CSV report path (default: logs/macro_repair_<host>.csv)")
    parser.add_argument("--limit", type=int, default=0, help="only process the first N candidates")
    parser.add_argument("--skip", default=",".join(MISIDENTIFIED),
                        help="comma-separated ingredient names to leave alone (default: known misidentified rows)")
    args = parser.parse_args()

    email = os.environ.get("EKITCHEN_ADMIN_EMAIL")
    password = os.environ.get("EKITCHEN_ADMIN_PASSWORD")
    if not email or not password:
        print("ERROR: EKITCHEN_ADMIN_EMAIL / EKITCHEN_ADMIN_PASSWORD must be set for the target backend.")
        return 2
    if args.apply and not confirm_remote(args.base_url):
        print("Aborted.")
        return 1

    host = urlparse(args.base_url).hostname or "target"
    out = args.out or os.path.join(os.path.dirname(__file__), "..", "logs", f"macro_repair_{host}.csv")

    token = login(args.base_url, email, password)
    ingredients = fetch_all_ingredients(args.base_url, token)
    skip = {n.strip().lower() for n in args.skip.split(",") if n.strip()}
    candidates = [i for i in ingredients if is_candidate(i) and str(i.get("name", "")).lower() not in skip]
    candidates.sort(key=lambda i: str(i.get("name")))
    if args.limit:
        candidates = candidates[: args.limit]
    print(f"{len(ingredients)} ingredients, {len(candidates)} candidates with broken fat")

    processor = DirectIngredientProcessor(log_to_file=True)
    cache = load_cache(args.cache)
    rows: List[Dict[str, Any]] = []
    try:
        for ing in candidates:
            fetched = fetch_macros(processor, cache, str(ing["external_id"]).strip(), str(ing.get("name")))
            rows.append(plan_repair(ing, fetched))
    finally:
        save_cache(args.cache, cache)

    written = failed = 0
    if args.apply:
        for row in rows:
            if row["action"] != "update":
                continue
            payload = dict(row["_update"])
            payload["update_mask"] = [{"fat": "Fat", "carbohydrates": "Carbohydrates"}[k] for k in row["_update"]]
            if update_ingredient(args.base_url, token, row["id"], payload):
                written += 1
                row["action"] = "updated"
            else:
                failed += 1
                row["action"] = "update failed"

    os.makedirs(os.path.dirname(out), exist_ok=True)
    fields = ["id", "name", "external_id", "spoonacular_name", "calories", "spoon_calories",
              "fat_before", "fat_after", "carbs_before", "carbs_after", "action"]
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    tally: Dict[str, int] = {}
    for row in rows:
        tally[row["action"]] = tally.get(row["action"], 0) + 1
    print("\nResult:")
    for action, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {n:4d}  {action}")
    if args.apply:
        print(f"\nwrote {written}, failed {failed}")
    else:
        print("\nDry run — nothing written. Re-run with --apply to write.")
    print(f"report: {os.path.abspath(out)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
