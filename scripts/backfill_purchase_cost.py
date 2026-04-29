#!/usr/bin/env python3
"""
Backfill purchase_cost for global ingredients missing it in their purchase_info.

Targets two populations:
  1. Ingredients WITH purchase_info but MISSING purchase_cost
     -> Calls GPT to estimate the standard container price
  2. Ingredients with NO cost data at all (estimated_cost_value=0, no purchase_info)
     -> Full cost estimation via GPT (same as normal ingestion)

Usage:
    source local.env
    python scripts/backfill_purchase_cost.py                # Full run
    python scripts/backfill_purchase_cost.py --dry-run      # Preview only
    python scripts/backfill_purchase_cost.py --limit 10     # Process only 10
    python scripts/backfill_purchase_cost.py --prod         # Run against production

Environment variables required:
    EKITCHEN_BASE_URL       - eKitchen backend URL
    EKITCHEN_ADMIN_EMAIL    - Admin email for authentication
    EKITCHEN_ADMIN_PASSWORD - Admin password for authentication
    OPENAI_API_KEY          - OpenAI API key (for cost estimation)
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


@dataclass
class BackfillStats:
    total_fetched: int = 0
    missing_purchase_cost: int = 0
    missing_all_cost_data: int = 0
    already_good: int = 0
    updated: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)


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
    """PATCH a global ingredient with updated data."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
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


def parse_purchase_info(ingredient: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse purchase_info JSON string from ingredient, returns None if missing/invalid."""
    raw = ingredient.get("purchase_info")
    if not raw or raw == "null":
        return None
    try:
        if isinstance(raw, str):
            return json.loads(raw)
        return raw
    except (json.JSONDecodeError, TypeError):
        return None


def needs_purchase_cost_backfill(ingredient: Dict[str, Any]) -> str:
    """
    Determine if ingredient needs purchase_cost backfill.
    Returns:
      'missing_purchase_cost' - has purchase_info but no purchase_cost
      'missing_all_cost'      - no cost data at all
      'ok'                    - already has purchase_cost
    """
    pi = parse_purchase_info(ingredient)
    cost_value = ingredient.get("estimated_cost_value", 0) or 0

    if pi and pi.get("purchase_cost", 0) > 0:
        return "ok"

    if pi and pi.get("purchase_unit"):
        # Has purchase_info structure but missing purchase_cost
        return "missing_purchase_cost"

    if cost_value == 0:
        # No cost data at all
        return "missing_all_cost"

    # Has estimated_cost_value but no purchase_info at all
    return "missing_purchase_cost"


def build_purchase_cost_update(
    ingredient: Dict[str, Any],
    processor: DirectIngredientProcessor,
) -> Optional[Dict[str, Any]]:
    """
    Build PATCH payload to add purchase_cost to an ingredient.
    Uses GPT to estimate the standard retail container price.
    """
    name = ingredient["name"]
    possible_units = ingredient.get("possible_units") or ["cup", "tbsp", "tsp", "oz", "g"]

    # Call GPT to get full purchase info including purchase_cost
    cost_info = processor.estimate_ingredient_cost_with_ai(name, possible_units)
    if not cost_info:
        return None

    update: Dict[str, Any] = {}
    update_mask: List[str] = []

    # Build purchase_info with purchase_cost
    existing_pi = parse_purchase_info(ingredient) or {}

    purchase_info = {
        "purchase_unit": cost_info.get("purchase_unit", existing_pi.get("purchase_unit", "")),
        "purchase_quantity": cost_info.get("purchase_quantity", existing_pi.get("purchase_quantity", 0)),
        "purchase_cost": cost_info["purchase_cost"],
        "min_purchase_threshold": cost_info.get("min_purchase_threshold", existing_pi.get("min_purchase_threshold", 1)),
        "supplier": "AI Estimate (purchase_cost backfill)",
    }
    update["purchase_info"] = json.dumps(purchase_info)
    update_mask.append("PurchaseInfo")

    # Also update estimated_cost_value if currently missing
    current_cost = ingredient.get("estimated_cost_value", 0) or 0
    if current_cost == 0 and cost_info.get("cost_per_unit"):
        update["estimated_cost_value"] = cost_info["cost_per_unit"]
        update["estimated_cost_unit"] = cost_info.get("cost_unit", "gram")
        update_mask.extend(["EstimatedCostValue", "EstimatedCostUnit"])

    # Also update unit_conversions if missing and we have possible_units
    current_conversions = ingredient.get("unit_conversions")
    if not current_conversions or current_conversions == "null":
        # The cost_info doesn't include unit_conversions, but we can note it
        pass

    # Mark as no longer needing enrichment if we now have cost data
    if cost_info.get("purchase_cost", 0) > 0:
        update["needs_enrichment"] = False
        update_mask.append("NeedsEnrichment")

    update["update_mask"] = list(dict.fromkeys(update_mask))
    return update


def main():
    parser = argparse.ArgumentParser(
        description="Backfill purchase_cost for ingredients missing it"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would be updated without making changes"
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Limit number of ingredients to process (0 = all)"
    )
    parser.add_argument(
        "--prod", action="store_true",
        help="Use production environment (EKITCHEN_PROD_BASE_URL)"
    )
    args = parser.parse_args()

    # Validate environment
    if args.prod:
        base_url = os.environ.get("EKITCHEN_PROD_BASE_URL", os.environ.get("EKITCHEN_BASE_URL"))
    else:
        base_url = os.environ.get("EKITCHEN_BASE_URL")
    admin_email = os.environ.get("EKITCHEN_ADMIN_EMAIL")
    admin_password = os.environ.get("EKITCHEN_ADMIN_PASSWORD")

    if not all([base_url, admin_email, admin_password]):
        print("ERROR: Missing required environment variables.")
        print("  Required: EKITCHEN_BASE_URL, EKITCHEN_ADMIN_EMAIL, EKITCHEN_ADMIN_PASSWORD")
        print("  Run: source local.env")
        sys.exit(1)

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        print("ERROR: OPENAI_API_KEY required for cost estimation")
        sys.exit(1)

    # Initialize
    stats = BackfillStats()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*70}")
    print(f"  Purchase Cost Backfill - {timestamp}")
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

    # Step 3: Filter for those needing purchase_cost
    print("[3/4] Identifying ingredients missing purchase_cost...")
    to_backfill = []
    for ing in all_ingredients:
        status = needs_purchase_cost_backfill(ing)
        if status == "missing_purchase_cost":
            stats.missing_purchase_cost += 1
            to_backfill.append(ing)
        elif status == "missing_all_cost":
            stats.missing_all_cost_data += 1
            to_backfill.append(ing)
        else:
            stats.already_good += 1

    total_needing = stats.missing_purchase_cost + stats.missing_all_cost_data
    print(f"  Already have purchase_cost:    {stats.already_good}")
    print(f"  Missing purchase_cost only:    {stats.missing_purchase_cost}")
    print(f"  Missing ALL cost data:         {stats.missing_all_cost_data}")
    print(f"  Total needing backfill:        {total_needing}\n")

    if not to_backfill:
        print("Nothing to backfill. All ingredients have purchase_cost.")
        return

    if args.limit > 0:
        to_backfill = to_backfill[:args.limit]
        print(f"  Processing limited to first {len(to_backfill)} ingredients\n")

    # Step 4: Process each ingredient
    print("[4/4] Estimating purchase costs via GPT...\n")
    processor = DirectIngredientProcessor(log_to_file=True)
    processor.access_token = token
    processor.ekitchen_base_url = base_url

    total = len(to_backfill)

    for idx, ingredient in enumerate(to_backfill, 1):
        ing_id = ingredient["id"]
        ing_name = ingredient["name"]
        status = needs_purchase_cost_backfill(ingredient)
        existing_pi = parse_purchase_info(ingredient)

        print(f"[{idx}/{total}] \"{ing_name}\" ({status})")
        if existing_pi:
            print(f"  Current: unit={existing_pi.get('purchase_unit', 'n/a')}, "
                  f"qty={existing_pi.get('purchase_quantity', 'n/a')}, "
                  f"cost={existing_pi.get('purchase_cost', 'MISSING')}")

        try:
            update_payload = build_purchase_cost_update(ingredient, processor)

            if not update_payload:
                print(f"  -> GPT returned no data, skipping")
                stats.failed += 1
                stats.errors.append(f"{ing_name}: GPT returned no cost data")
                continue

            # Extract new purchase_cost for display
            new_pi = json.loads(update_payload.get("purchase_info", "{}"))
            new_cost = new_pi.get("purchase_cost", 0)
            new_unit = new_pi.get("purchase_unit", "?")
            new_qty = new_pi.get("purchase_quantity", 0)

            if args.dry_run:
                print(f"  -> [DRY RUN] Would set: {new_unit} = ${new_cost:.2f} "
                      f"({new_qty} units per {new_unit})")
            else:
                success = update_ingredient(base_url, token, ing_id, update_payload)
                if success:
                    print(f"  -> Updated: {new_unit} = ${new_cost:.2f} "
                          f"({new_qty} units per {new_unit})")
                    stats.updated += 1
                else:
                    stats.failed += 1
                    stats.errors.append(f"{ing_name}: PATCH failed")
                    continue

        except Exception as e:
            print(f"  -> ERROR: {e}")
            stats.failed += 1
            stats.errors.append(f"{ing_name}: {e}")

        # Rate limiting: 1s between GPT calls
        time.sleep(1.0)

        # Batch progress
        if idx % 25 == 0:
            print(f"\n--- Progress: {idx}/{total} processed "
                  f"({stats.updated} updated, {stats.failed} failed) ---\n")

    # Summary
    print(f"\n{'='*70}")
    print(f"  PURCHASE COST BACKFILL SUMMARY")
    print(f"{'='*70}")
    print(f"  Total ingredients fetched:       {stats.total_fetched}")
    print(f"  Already had purchase_cost:       {stats.already_good}")
    print(f"  Missing purchase_cost only:      {stats.missing_purchase_cost}")
    print(f"  Missing ALL cost data:           {stats.missing_all_cost_data}")
    print(f"  Successfully updated:            {stats.updated}")
    print(f"  Failed:                          {stats.failed}")
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
