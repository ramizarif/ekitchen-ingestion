#!/usr/bin/env python3
"""
Backfill enrichment for global ingredients with missing nutrition/cost data.

Fetches all global ingredients from the eKitchen backend, identifies those
with missing calories, cost, or category data, and re-enriches them using
the existing Spoonacular + AI pipeline from ingredient_processor.py.

Usage:
    source local.env
    python scripts/backfill_enrichment.py

    # Dry-run mode (no updates, just report what would change):
    python scripts/backfill_enrichment.py --dry-run

    # Limit to N ingredients:
    python scripts/backfill_enrichment.py --limit 10

Environment variables required:
    EKITCHEN_BASE_URL       - eKitchen backend URL
    EKITCHEN_ADMIN_EMAIL    - Admin email for authentication
    EKITCHEN_ADMIN_PASSWORD - Admin password for authentication
    SPOONACULAR_API_KEY     - Spoonacular API key (via RapidAPI or direct)
    OPENAI_API_KEY          - OpenAI API key (for AI fallback)

Optional:
    SPOONACULAR_BASE_URL              - Spoonacular base URL
    SPOONACULAR_RATE_LIMIT_PER_MINUTE - Rate limit (default 150)
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

# Add parent directory to path so we can import the ingredient processor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.ingredient_processor import DirectIngredientProcessor


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class EnrichmentStats:
    total_fetched: int = 0
    total_needing_enrichment: int = 0
    enriched_spoonacular: int = 0
    enriched_ai_only: int = 0
    skipped_already_good: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def total_enriched(self) -> int:
        return self.enriched_spoonacular + self.enriched_ai_only


# ── Backend API helpers ──────────────────────────────────────────────────────

def login(base_url: str, email: str, password: str) -> str:
    """Authenticate with eKitchen backend and return Bearer token."""
    resp = requests.post(
        f"{base_url}/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("Login succeeded but no access_token in response")
    return token


def fetch_all_ingredients(base_url: str, token: str) -> List[Dict[str, Any]]:
    """Fetch all global ingredients from the backend, paginating as needed."""
    headers = {"Authorization": f"Bearer {token}"}
    all_ingredients: List[Dict[str, Any]] = []
    offset = 0
    page_size = 200

    while True:
        resp = requests.get(
            f"{base_url}/global-ingredients/",
            params={"limit": page_size, "offset": offset},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()

        if not batch:
            break

        all_ingredients.extend(batch)
        print(f"  Fetched {len(all_ingredients)} ingredients so far...")

        if len(batch) < page_size:
            break
        offset += page_size

    return all_ingredients


def update_ingredient(base_url: str, token: str, ingredient_id: str,
                      update_data: Dict[str, Any]) -> bool:
    """PATCH a global ingredient with enrichment data."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    # Backend requires ID in both URL and payload
    update_data["id"] = ingredient_id
    resp = requests.patch(
        f"{base_url}/global-ingredients/{ingredient_id}",
        json=update_data,
        headers=headers,
        timeout=30,
    )
    if resp.status_code >= 400:
        print(f"    PATCH failed ({resp.status_code}): {resp.text[:200]}")
        return False
    return True


# ── Enrichment logic ────────────────────────────────────────────────────────

def needs_enrichment(ingredient: Dict[str, Any]) -> bool:
    """Determine whether an ingredient needs re-enrichment."""
    calories = ingredient.get("calories", 0) or 0
    cost = ingredient.get("estimated_cost_value", 0) or 0
    category = (ingredient.get("category") or "other").lower()

    return calories == 0 or cost == 0 or category == "other"


def describe_gaps(ingredient: Dict[str, Any]) -> str:
    """Return a short description of what data is missing."""
    gaps = []
    if (ingredient.get("calories", 0) or 0) == 0:
        gaps.append("calories")
    if (ingredient.get("estimated_cost_value", 0) or 0) == 0:
        gaps.append("cost")
    if (ingredient.get("category") or "other").lower() == "other":
        gaps.append("category")
    return ", ".join(gaps) if gaps else "none"


def build_update_payload(ingredient: Dict[str, Any],
                         spoon_data,
                         processor: DirectIngredientProcessor,
                         ) -> Optional[Dict[str, Any]]:
    """
    Build PATCH payload from Spoonacular data and AI fallbacks.
    Returns None if nothing meaningful was enriched.
    """
    update: Dict[str, Any] = {}
    update_mask: List[str] = []
    source = "spoonacular"

    current_calories = ingredient.get("calories", 0) or 0
    current_cost = ingredient.get("estimated_cost_value", 0) or 0
    current_category = (ingredient.get("category") or "other").lower()
    name = ingredient["name"]

    if spoon_data:
        # Nutrition
        if current_calories == 0 and spoon_data.calories is not None and spoon_data.calories > 0:
            update["calories"] = spoon_data.calories
            update_mask.append("Calories")
        if spoon_data.protein is not None:
            update["protein"] = spoon_data.protein
            update_mask.append("Protein")
        if spoon_data.fat is not None:
            update["fat"] = spoon_data.fat
            update_mask.append("Fat")
        if spoon_data.carbohydrates is not None:
            update["carbohydrates"] = spoon_data.carbohydrates
            update_mask.append("Carbohydrates")
        if spoon_data.sugar is not None:
            update["sugar"] = spoon_data.sugar
            update_mask.append("Sugar")

        # Cost
        if current_cost == 0 and spoon_data.estimated_cost_per_unit is not None:
            update["estimated_cost_value"] = spoon_data.estimated_cost_per_unit
            update["estimated_cost_unit"] = spoon_data.cost_unit or "gram"
            update_mask.extend(["EstimatedCostValue", "EstimatedCostUnit"])

        # Purchase info
        if spoon_data.purchase_unit:
            purchase_cost = spoon_data.purchase_cost
            if purchase_cost is None and spoon_data.estimated_cost_per_unit and spoon_data.purchase_quantity:
                purchase_cost = spoon_data.estimated_cost_per_unit * spoon_data.purchase_quantity
            purchase_info = {
                "purchase_unit": spoon_data.purchase_unit,
                "purchase_quantity": spoon_data.purchase_quantity,
                "purchase_cost": purchase_cost,
                "min_purchase_threshold": spoon_data.min_purchase_threshold,
                "supplier": "Spoonacular + AI Estimate (backfill)",
            }
            update["purchase_info"] = json.dumps(purchase_info)
            update_mask.append("PurchaseInfo")

        # Unit conversions
        if spoon_data.unit_conversions:
            update["unit_conversions"] = json.dumps(spoon_data.unit_conversions)
            update_mask.append("UnitConversions")

        # Consistency & possible units
        if spoon_data.consistency:
            update["consistency"] = spoon_data.consistency
            update_mask.append("Consistency")
        if spoon_data.possible_units:
            update["possible_units"] = spoon_data.possible_units
            update_mask.append("PossibleUnits")

        # External ID
        update["external_id"] = str(spoon_data.id)
        update_mask.append("ExternalID")

    # AI fallback for category if still "other"
    if current_category == "other":
        ai_category = processor.categorize_ingredient_with_ai(name)
        if ai_category and ai_category != "other":
            update["category"] = ai_category
            update_mask.append("Category")

    # AI fallback for cost if still missing after Spoonacular
    if current_cost == 0 and "EstimatedCostValue" not in update_mask:
        source = "ai"
        possible_units = ingredient.get("possible_units") or ["cup", "tbsp", "tsp", "oz", "g"]
        cost_info = processor.estimate_ingredient_cost_with_ai(name, possible_units)
        if cost_info:
            update["estimated_cost_value"] = cost_info["cost_per_unit"]
            update["estimated_cost_unit"] = cost_info["cost_unit"]
            update_mask.extend(["EstimatedCostValue", "EstimatedCostUnit"])
            purchase_info = {
                "purchase_unit": cost_info["purchase_unit"],
                "purchase_quantity": cost_info["purchase_quantity"],
                "purchase_cost": cost_info["purchase_cost"],
                "min_purchase_threshold": cost_info["min_purchase_threshold"],
                "supplier": "AI Estimate (backfill)",
            }
            update["purchase_info"] = json.dumps(purchase_info)
            update_mask.append("PurchaseInfo")

    # Decay rate if missing
    current_decay = ingredient.get("default_decay_rate") or ""
    if not current_decay:
        category_for_decay = update.get("category") or ingredient.get("category") or "other"
        decay_rate, shelf_life = processor.determine_decay_rate_and_shelf_life(name, category_for_decay)
        update["default_decay_rate"] = decay_rate
        update["typical_shelf_life_days"] = shelf_life
        update_mask.extend(["DefaultDecayRate", "TypicalShelfLifeDays"])

    # Mark as no longer needing enrichment if we got meaningful data
    has_calories = (update.get("calories") or current_calories) > 0
    has_cost = (update.get("estimated_cost_value") or current_cost) > 0
    if has_calories and has_cost:
        update["needs_enrichment"] = False
        update_mask.append("NeedsEnrichment")

    if not update_mask:
        return None

    # Deduplicate the mask
    update["update_mask"] = list(dict.fromkeys(update_mask))
    return update


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Backfill enrichment for global ingredients with missing data"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would be enriched without making changes"
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Limit number of ingredients to process (0 = all)"
    )
    args = parser.parse_args()

    # Validate environment
    base_url = os.environ.get("EKITCHEN_BASE_URL")
    admin_email = os.environ.get("EKITCHEN_ADMIN_EMAIL")
    admin_password = os.environ.get("EKITCHEN_ADMIN_PASSWORD")

    if not all([base_url, admin_email, admin_password]):
        print("ERROR: Missing required environment variables.")
        print("  Required: EKITCHEN_BASE_URL, EKITCHEN_ADMIN_EMAIL, EKITCHEN_ADMIN_PASSWORD")
        print("  Run: source local.env")
        sys.exit(1)

    spoonacular_key = os.environ.get("SPOONACULAR_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not spoonacular_key:
        print("WARNING: SPOONACULAR_API_KEY not set -- Spoonacular lookups will be skipped")
    if not openai_key:
        print("WARNING: OPENAI_API_KEY not set -- AI fallback will be unavailable")

    # Initialize
    stats = EnrichmentStats()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*70}")
    print(f"  Backfill Enrichment - {timestamp}")
    print(f"  Target: {base_url}")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    if args.limit:
        print(f"  Limit: {args.limit} ingredients")
    print(f"{'='*70}\n")

    # Step 1: Authenticate
    print("[1/4] Authenticating...")
    token = login(base_url, admin_email, admin_password)
    print(f"  Authenticated as {admin_email}\n")

    # Step 2: Fetch all ingredients
    print("[2/4] Fetching all global ingredients...")
    all_ingredients = fetch_all_ingredients(base_url, token)
    stats.total_fetched = len(all_ingredients)
    print(f"  Total ingredients: {stats.total_fetched}\n")

    # Step 3: Filter for those needing enrichment
    print("[3/4] Identifying ingredients needing enrichment...")
    to_enrich = [ing for ing in all_ingredients if needs_enrichment(ing)]
    stats.total_needing_enrichment = len(to_enrich)
    stats.skipped_already_good = stats.total_fetched - stats.total_needing_enrichment

    # Count gap types
    missing_calories = sum(1 for i in to_enrich if (i.get("calories", 0) or 0) == 0)
    missing_cost = sum(1 for i in to_enrich if (i.get("estimated_cost_value", 0) or 0) == 0)
    missing_category = sum(1 for i in to_enrich if (i.get("category") or "other").lower() == "other")

    print(f"  Needing enrichment: {stats.total_needing_enrichment}")
    print(f"    - Missing calories: {missing_calories}")
    print(f"    - Missing cost:     {missing_cost}")
    print(f"    - Category=other:   {missing_category}")
    print(f"  Already good:       {stats.skipped_already_good}\n")

    if not to_enrich:
        print("Nothing to enrich. All ingredients have data.")
        return

    if args.limit > 0:
        to_enrich = to_enrich[:args.limit]
        print(f"  Processing limited to first {len(to_enrich)} ingredients\n")

    # Step 4: Initialize processor and enrich
    print("[4/4] Enriching ingredients...\n")
    processor = DirectIngredientProcessor(log_to_file=True)

    # Authenticate the processor (needed for AI cost estimation internals)
    processor.access_token = token
    processor.ekitchen_base_url = base_url

    total = len(to_enrich)
    batch_size = 50

    for idx, ingredient in enumerate(to_enrich, 1):
        ing_id = ingredient["id"]
        ing_name = ingredient["name"]
        gaps = describe_gaps(ingredient)

        print(f"[{idx}/{total}] Processing \"{ing_name}\" (gaps: {gaps})")

        try:
            # Search Spoonacular for enrichment data
            spoon_data = processor.search_spoonacular_ingredient_enhanced(ing_name)
            source = "spoonacular" if spoon_data else "ai"

            # Build update payload
            update_payload = build_update_payload(ingredient, spoon_data, processor)

            if not update_payload:
                print(f"  -> No enrichment data found, skipping")
                stats.failed += 1
                stats.errors.append(f"{ing_name}: no data from Spoonacular or AI")
                continue

            # Extract key values for display
            new_cal = update_payload.get("calories", ingredient.get("calories", 0) or 0)
            new_cost = update_payload.get("estimated_cost_value", ingredient.get("estimated_cost_value", 0) or 0)
            new_cost_unit = update_payload.get("estimated_cost_unit", ingredient.get("estimated_cost_unit", ""))
            new_category = update_payload.get("category", ingredient.get("category", ""))

            if args.dry_run:
                print(f"  -> [DRY RUN] Would update: "
                      f"calories={new_cal:.0f}, "
                      f"cost=${new_cost:.4f}/{new_cost_unit}, "
                      f"category={new_category} "
                      f"(source: {source})")
            else:
                success = update_ingredient(base_url, token, ing_id, update_payload)
                if success:
                    print(f"  -> Enriched: "
                          f"calories={new_cal:.0f}, "
                          f"cost=${new_cost:.4f}/{new_cost_unit}, "
                          f"category={new_category} "
                          f"(source: {source})")
                else:
                    print(f"  -> FAILED to update")
                    stats.failed += 1
                    stats.errors.append(f"{ing_name}: PATCH failed")
                    continue

            if source == "spoonacular":
                stats.enriched_spoonacular += 1
            else:
                stats.enriched_ai_only += 1

        except Exception as e:
            print(f"  -> ERROR: {e}")
            stats.failed += 1
            stats.errors.append(f"{ing_name}: {e}")

        # Rate limiting: 500ms between calls (Spoonacular limit ~150/min)
        time.sleep(0.5)

        # Batch progress logging
        if idx % batch_size == 0:
            print(f"\n--- Batch progress: {idx}/{total} processed "
                  f"({stats.total_enriched} enriched, {stats.failed} failed) ---\n")

    # Summary
    print(f"\n{'='*70}")
    print(f"  ENRICHMENT SUMMARY")
    print(f"{'='*70}")
    print(f"  Total ingredients fetched:    {stats.total_fetched}")
    print(f"  Already had data (skipped):   {stats.skipped_already_good}")
    print(f"  Needing enrichment:           {stats.total_needing_enrichment}")
    print(f"  Successfully enriched:        {stats.total_enriched}")
    print(f"    - Via Spoonacular:          {stats.enriched_spoonacular}")
    print(f"    - Via AI only:              {stats.enriched_ai_only}")
    print(f"  Failed:                       {stats.failed}")
    if args.dry_run:
        print(f"\n  ** DRY RUN -- no changes were made **")
    print(f"{'='*70}\n")

    if stats.errors:
        print(f"Errors ({len(stats.errors)}):")
        for err in stats.errors[:20]:
            print(f"  - {err}")
        if len(stats.errors) > 20:
            print(f"  ... and {len(stats.errors) - 20} more")
        print()


if __name__ == "__main__":
    main()
