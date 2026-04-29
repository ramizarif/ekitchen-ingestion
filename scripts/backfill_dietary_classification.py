#!/usr/bin/env python3
"""
Backfill dietary_classification for global recipes missing it.

Fetches all global recipes with dietary_classification IS NULL from the eKitchen
backend, classifies each one using GPT-4o-mini (diet-only prompt, not full
enrichment), and PATCHes back the dietary_classification field.

Usage:
    source local.env
    python scripts/backfill_dietary_classification.py                # Full run
    python scripts/backfill_dietary_classification.py --dry-run      # Preview only
    python scripts/backfill_dietary_classification.py --limit 50     # Process only 50
    python scripts/backfill_dietary_classification.py --batch-size 100  # 100 recipes per batch

Environment variables required:
    EKITCHEN_BASE_URL       - eKitchen backend URL
    EKITCHEN_ADMIN_EMAIL    - Admin email for authentication
    EKITCHEN_ADMIN_PASSWORD - Admin password for authentication
    OPENAI_API_KEY          - OpenAI API key (for dietary classification)

Optional:
    None

Cost estimate: ~$0.001 per recipe with GPT-4o-mini. Full corpus (~10K recipes) ≈ $10.
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
from openai import OpenAI

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class BackfillStats:
    total_fetched: int = 0
    total_needing_classification: int = 0
    classified: int = 0
    skipped_already_good: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return self.classified + self.failed


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


def fetch_recipes_needing_classification(
    base_url: str, token: str, limit: int = 0, batch_size: int = 200
) -> List[Dict[str, Any]]:
    """
    Fetch all global recipes with dietary_classification IS NULL.
    Paginates automatically.
    """
    headers = {"Authorization": f"Bearer {token}"}
    all_recipes: List[Dict[str, Any]] = []
    offset = 0

    while True:
        resp = requests.get(
            f"{base_url}/global-recipes/",
            params={
                "limit": batch_size,
                "offset": offset,
                # Filter for recipes with NULL dietary_classification
            },
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()

        if not batch:
            break

        # Filter for recipes with NULL dietary_classification
        needing_classification = [
            r for r in batch if r.get("dietary_classification") is None
        ]
        all_recipes.extend(needing_classification)

        print(f"  Fetched {len(all_recipes)} recipes needing classification so far...")

        # Apply limit if set
        if limit > 0 and len(all_recipes) >= limit:
            all_recipes = all_recipes[:limit]
            break

        if len(batch) < batch_size:
            break

        offset += batch_size

    return all_recipes


def patch_recipe_dietary_classification(
    base_url: str, token: str, recipe_id: str, classification: str
) -> bool:
    """PATCH a global recipe with dietary_classification data."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    update_data = {
        "id": recipe_id,
        "dietary_classification": classification,
    }
    resp = requests.patch(
        f"{base_url}/global-recipes/{recipe_id}",
        json=update_data,
        headers=headers,
        timeout=30,
    )
    if resp.status_code >= 400:
        print(f"    PATCH failed ({resp.status_code}): {resp.text[:200]}")
        return False
    return True


# ── Classification logic ────────────────────────────────────────────────────────

def classify_dietary(
    recipe: Dict[str, Any], openai_client: OpenAI
) -> Optional[str]:
    """
    Classify a recipe's dietary level using GPT-4o-mini.
    Returns one of: 'omnivore', 'pescatarian', 'vegetarian', 'vegan', or None on error.
    """
    title = recipe.get("name", "Unknown")
    ingredients = recipe.get("ingredients", [])
    instructions = recipe.get("steps", [])

    # Extract ingredient names (ingredients can be objects or strings)
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
            temperature=0,  # Deterministic for consistent classification
            max_tokens=5,
        )

        classification = response.choices[0].message.content.strip().lower()

        # Validate response
        valid_values = {"omnivore", "pescatarian", "vegetarian", "vegan"}
        if classification in valid_values:
            return classification
        else:
            print(f"    Warning: Invalid classification returned: {classification}")
            return None

    except Exception as e:
        print(f"    Error during classification: {e}")
        return None


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Backfill dietary_classification for global recipes with missing data"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be classified without making changes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of recipes to process (0 = all)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Number of recipes to fetch per API call (default 200)",
    )
    args = parser.parse_args()

    # Validate environment
    base_url = os.environ.get("EKITCHEN_BASE_URL")
    admin_email = os.environ.get("EKITCHEN_ADMIN_EMAIL")
    admin_password = os.environ.get("EKITCHEN_ADMIN_PASSWORD")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not all([base_url, admin_email, admin_password, openai_key]):
        print("ERROR: Missing required environment variables.")
        print("  Required: EKITCHEN_BASE_URL, EKITCHEN_ADMIN_EMAIL, EKITCHEN_ADMIN_PASSWORD, OPENAI_API_KEY")
        sys.exit(1)

    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Setup logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"backfill_dietary_classification_{timestamp}.log")
    log_handle = open(log_file, "w")

    def log_msg(msg: str):
        """Log to both stdout and file."""
        print(msg)
        log_handle.write(msg + "\n")
        log_handle.flush()

    log_msg("=" * 70)
    log_msg("DIETARY CLASSIFICATION BACKFILL")
    log_msg("=" * 70)
    log_msg(f"Base URL: {base_url}")
    log_msg(f"Admin: {admin_email}")
    log_msg(f"Dry-run mode: {args.dry_run}")
    log_msg(f"Limit: {args.limit if args.limit > 0 else 'all'}")
    log_msg(f"Batch size: {args.batch_size}")
    log_msg(f"Log file: {log_file}\n")

    try:
        # Authentication
        log_msg("[1/4] Authenticating with eKitchen backend...")
        token = login(base_url, admin_email, admin_password)
        log_msg("✅ Authentication successful\n")

        # Initialize OpenAI client
        log_msg("[2/4] Initializing OpenAI client...")
        openai_client = OpenAI(api_key=openai_key)
        log_msg("✅ OpenAI client initialized\n")

        # Fetch recipes needing classification
        log_msg("[3/4] Fetching recipes with missing dietary_classification...")
        recipes = fetch_recipes_needing_classification(
            base_url, token, limit=args.limit, batch_size=args.batch_size
        )
        log_msg(f"✅ Found {len(recipes)} recipes needing classification\n")

        if not recipes:
            log_msg("Nothing to backfill. All recipes have dietary_classification.")
            log_handle.close()
            return

        # Classify and patch
        log_msg("[4/4] Classifying and patching recipes...\n")
        log_msg(f"{'ID':<36} {'Title':<50} {'Classification':<15} {'Status':<10} {'Latency (ms)':<12}")
        log_msg("-" * 120)

        stats = BackfillStats(total_needing_classification=len(recipes))
        start_time = time.time()

        for idx, recipe in enumerate(recipes, 1):
            recipe_id = recipe.get("id", "unknown")
            recipe_title = recipe.get("name", "Unknown")[:45]
            recipe_start = time.time()

            # Classify
            classification = classify_dietary(recipe, openai_client)
            latency_ms = int((time.time() - recipe_start) * 1000)

            if classification:
                stats.classified += 1
                status = "[DRY-RUN]" if args.dry_run else "[PATCHED]"

                # Only patch if not dry-run
                if not args.dry_run:
                    if patch_recipe_dietary_classification(
                        base_url, token, recipe_id, classification
                    ):
                        log_msg(
                            f"{recipe_id:<36} {recipe_title:<50} {classification:<15} {status:<10} {latency_ms:<12}"
                        )
                    else:
                        log_msg(
                            f"{recipe_id:<36} {recipe_title:<50} {'ERROR':<15} {'FAILED':<10} {latency_ms:<12}"
                        )
                        stats.failed += 1
                else:
                    log_msg(
                        f"{recipe_id:<36} {recipe_title:<50} {classification:<15} {status:<10} {latency_ms:<12}"
                    )
            else:
                stats.failed += 1
                log_msg(
                    f"{recipe_id:<36} {recipe_title:<50} {'N/A':<15} {'FAILED':<10} {latency_ms:<12}"
                )

            # Progress checkpoint every 20 recipes
            if idx % 20 == 0:
                elapsed = time.time() - start_time
                log_msg(
                    f"\n--- Progress: {idx}/{len(recipes)} processed ({elapsed:.1f}s elapsed) ---\n"
                )

        # Summary
        total_elapsed = time.time() - start_time
        log_msg("\n" + "=" * 70)
        log_msg("BACKFILL SUMMARY")
        log_msg("=" * 70)
        log_msg(f"Total recipes fetched:     {stats.total_needing_classification}")
        log_msg(f"Successfully classified:   {stats.classified}")
        log_msg(f"Failed:                    {stats.failed}")
        log_msg(f"Total elapsed time:        {total_elapsed:.1f}s")

        if stats.total_needing_classification > 0:
            avg_cost = stats.classified * 0.001  # Rough estimate: $0.001 per recipe
            log_msg(f"Estimated cost:            ${avg_cost:.2f} (GPT-4o-mini)")

        if args.dry_run:
            log_msg(f"\n** DRY RUN -- no changes were made **")

        log_msg("=" * 70 + "\n")

        if stats.errors:
            log_msg(f"Errors ({len(stats.errors)}):")
            for err in stats.errors[:20]:
                log_msg(f"  - {err}")
            if len(stats.errors) > 20:
                log_msg(f"  ... and {len(stats.errors) - 20} more")

        log_handle.close()

    except Exception as e:
        log_msg(f"ERROR: {e}")
        import traceback

        traceback.print_exc(file=log_handle)
        log_handle.close()
        sys.exit(1)


if __name__ == "__main__":
    main()
