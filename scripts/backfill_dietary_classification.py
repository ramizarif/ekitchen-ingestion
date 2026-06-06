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
    safety_net_overrides: int = 0
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
        backoffs = [2, 4, 8]
        batch = None
        for attempt in range(len(backoffs) + 1):
            try:
                resp = requests.get(
                    f"{base_url}/global-recipes/",
                    params={"limit": batch_size, "offset": offset},
                    headers=headers,
                    timeout=60,
                )
                resp.raise_for_status()
                batch = resp.json()
                break
            except (requests.Timeout, requests.ConnectionError) as e:
                if attempt < len(backoffs):
                    print(f"  Fetch timeout, retrying in {backoffs[attempt]}s")
                    time.sleep(backoffs[attempt])
                    continue
                raise

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
    """PATCH a global recipe with dietary_classification, retrying on transient errors."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    update_data = {
        "id": recipe_id,
        "dietary_classification": classification,
    }
    backoffs = [1, 2, 4]
    for attempt in range(len(backoffs) + 1):
        try:
            resp = requests.patch(
                f"{base_url}/global-recipes/{recipe_id}",
                json=update_data,
                headers=headers,
                timeout=60,
            )
            if resp.status_code < 400:
                return True
            if resp.status_code >= 500 or resp.status_code == 429:
                if attempt < len(backoffs):
                    print(f"    PATCH {resp.status_code}, retrying in {backoffs[attempt]}s")
                    time.sleep(backoffs[attempt])
                    continue
            print(f"    PATCH failed ({resp.status_code}): {resp.text[:200]}")
            return False
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < len(backoffs):
                print(f"    PATCH timeout/conn-err, retrying in {backoffs[attempt]}s ({type(e).__name__})")
                time.sleep(backoffs[attempt])
                continue
            print(f"    PATCH gave up after retries: {e}")
            return False
    return False


# ── Classification logic ────────────────────────────────────────────────────────

# Hierarchy from most-restrictive to least-restrictive. Indices used for max(...).
TIER_ORDER = ["vegan", "vegetarian", "pescatarian", "omnivore"]

# Keyword sets used by the safety net. Each set names a tier-floor: if any
# keyword is present (as a whole word), the final classification cannot be MORE
# restrictive than that tier. Whole-word matching prevents false positives like
# "buttercup squash" triggering "butter".
#
# Conservative on dairy/eggs to avoid false-positives on plant-based products
# whose names contain "milk"/"butter"/"cheese". We only flag a recipe as
# non-vegan when an UNAMBIGUOUS animal-derived keyword appears. The complement
# of these sets is intentional — we accept false-negatives (a recipe with a
# subtle dairy ingredient slipping through to vegan) over false-positives.

ANIMAL_FLESH_WORDS = {
    # Specific cuts/preparations only — bare "steak" excluded because fish steaks
    # exist (tuna steak, marlin steak, swordfish steak).
    "beef", "ribeye", "sirloin", "brisket", "veal", "hamburger", "meatball", "meatballs", "ground beef",
    "pork", "bacon", "ham", "sausage", "sausages", "prosciutto", "pancetta", "chorizo", "salami", "pepperoni", "carnitas", "pulled pork",
    "chicken", "turkey", "duck", "goose", "quail", "poultry",
    "lamb", "mutton", "venison", "bison", "rabbit", "goat",
    "hot dog", "hot dogs", "frankfurter", "frankfurters", "kielbasa", "bratwurst",
}

FISH_SEAFOOD_WORDS = {
    "fish", "salmon", "tuna", "cod", "halibut", "mackerel", "sardine", "sardines",
    "anchovy", "anchovies", "herring", "trout", "tilapia", "marlin", "swordfish",
    "shrimp", "prawn", "prawns", "lobster", "crab", "crawfish", "crayfish",
    "scallop", "scallops", "mussel", "mussels", "clam", "clams", "oyster", "oysters",
    "squid", "calamari", "octopus", "caviar", "roe", "snapper", "bass", "haddock",
}

# Unambiguous dairy/egg/honey words. Bare "milk", "butter", "cream", "cheese"
# are intentionally excluded because plant analogues exist; we list common
# specific forms instead.
DAIRY_EGG_WORDS = {
    "egg", "eggs", "egg yolk", "egg yolks", "egg white", "egg whites",
    "honey",
    "buttermilk", "yogurt", "yoghurt",
    "parmesan", "parmigiano", "mozzarella", "cheddar", "ricotta", "feta", "gouda", "brie", "camembert", "gruyere",
    "ghee",
    "whey", "casein",
    "heavy cream", "sour cream", "whipping cream",
    "cream cheese", "cottage cheese",
}

# Modifiers that, when adjacent to a borderline word like "milk", indicate the plant version.
VEGAN_MODIFIERS = {"almond", "soy", "oat", "coconut", "cashew", "rice", "hemp", "non-dairy", "nondairy", "vegan", "plant", "plant-based"}


def _whole_word_match(text: str, words: set) -> Optional[str]:
    """Return the first matching word found as a whole-word match in lowered text."""
    import re
    for w in words:
        # Use word boundaries; allow multi-word phrases like "ground beef".
        pattern = r"\b" + re.escape(w) + r"\b"
        if re.search(pattern, text):
            return w
    return None


def _has_unmodified_dairy_keyword(text: str) -> Optional[str]:
    """
    Check for dairy/egg/honey keywords. For ambiguous bare words like "milk"
    or "butter" or "cream" or "cheese", require the absence of a vegan modifier
    in the same sentence (we approximate with same comma-delimited fragment).
    """
    import re
    # First, unambiguous dairy/egg words
    hit = _whole_word_match(text, DAIRY_EGG_WORDS)
    if hit:
        return hit
    # Then, ambiguous bare words — only flag if no vegan modifier nearby
    for ambiguous in ("milk", "butter", "cream", "cheese"):
        for m in re.finditer(r"\b" + ambiguous + r"\b", text):
            # Inspect ~30 chars before the match for a vegan modifier
            window = text[max(0, m.start() - 40):m.start()]
            if any(mod in window for mod in VEGAN_MODIFIERS):
                continue
            return ambiguous
    return None


def apply_safety_net(initial: str, search_text: str) -> tuple[str, Optional[str]]:
    """
    Override the GPT classification when ingredients/title/instructions contain
    unambiguous animal-derived keywords inconsistent with the GPT answer.

    Returns (final_tier, override_reason). override_reason is None when no
    override was applied.

    Hierarchy (most -> least restrictive): vegan > vegetarian > pescatarian > omnivore.
    A keyword "raises the floor" — final tier cannot be MORE restrictive than the floor.
    """
    text = search_text.lower()

    flesh = _whole_word_match(text, ANIMAL_FLESH_WORDS)
    if flesh and initial != "omnivore":
        return "omnivore", f"keyword '{flesh}' forces omnivore"

    fish = _whole_word_match(text, FISH_SEAFOOD_WORDS)
    if fish and initial in ("vegan", "vegetarian"):
        return "pescatarian", f"keyword '{fish}' forces pescatarian"

    if initial == "vegan":
        dairy = _has_unmodified_dairy_keyword(text)
        if dairy:
            return "vegetarian", f"keyword '{dairy}' forces vegetarian (not vegan)"

    return initial, None


def classify_dietary(
    recipe: Dict[str, Any], openai_client: OpenAI
) -> tuple[Optional[str], Optional[str]]:
    """
    Classify a recipe's dietary level. Returns (tier, override_reason).

    1. Run GPT-4o-mini with a strict prompt that forces meat-presence
       reasoning before emitting the tier.
    2. Run a keyword safety net over title + ingredients + instructions.
    3. If the safety net contradicts GPT, the safety net wins and the
       reason is recorded in the second return value.
    """
    title = recipe.get("name", "Unknown")
    description = recipe.get("description", "")
    ingredients = recipe.get("ingredients", [])
    instructions = recipe.get("steps", [])

    ingredient_list = []
    if isinstance(ingredients, list):
        for ing in ingredients:
            if isinstance(ing, dict):
                ingredient_list.append(ing.get("name", ""))
            elif isinstance(ing, str):
                ingredient_list.append(ing)

    instruction_list = []
    if isinstance(instructions, list):
        for step in instructions:
            if isinstance(step, dict):
                instruction_list.append(step.get("template", ""))
            elif isinstance(step, str):
                instruction_list.append(step)

    # Refined prompt: explicit decision-tree, with examples on common failure
    # cases the original prompt got wrong (chicken-named recipes mistakenly
    # vegan, classic egg/dairy desserts mistakenly omnivore).
    prompt = f"""You classify a recipe by its highest dietary restriction tier.

TIERS (most -> least restrictive): vegan > vegetarian > pescatarian > omnivore.

DECISION RULES (apply in order; first match wins):

1. Does the recipe contain ANY meat from a mammal or bird (beef, pork, chicken,
   turkey, duck, lamb, bacon, ham, sausage, prosciutto, pepperoni, etc.)?
   -> omnivore. The TITLE alone is enough: "Cashew Chicken" contains chicken.

2. Otherwise, does it contain ANY fish, shellfish, or seafood (salmon, tuna,
   shrimp, lobster, anchovy, sardine, etc.)?
   -> pescatarian.

3. Otherwise, does it contain ANY dairy, eggs, honey, or other non-flesh
   animal product (milk, cheese, butter, yogurt, cream, eggs)?
   -> vegetarian. Most baked goods, custards, flans, macarons, croissants,
   pastries, cheesecakes, profiteroles, and ice creams are vegetarian, not vegan.

4. Otherwise, no animal products of any kind?
   -> vegan.

EXAMPLES (memorize these, they were misclassified before):
- "Cashew Chicken" -> omnivore (chicken in title)
- "French Macarons" -> vegetarian (egg whites, almond flour)
- "Pain au Chocolat" -> vegetarian (butter pastry, no meat)
- "Profiteroles" -> vegetarian (cream + choux, no meat)
- "Mexican Flan" -> vegetarian (eggs + milk + sugar, no meat)
- "Vegan Black Bean Burgers" -> vegan
- "Bacon-Wrapped Asparagus" -> omnivore (bacon)

RECIPE:
Title: {title}
Description: {description[:300] if description else '(none)'}
Ingredients: {', '.join(ingredient_list)}

Reply with EXACTLY ONE WORD: omnivore, pescatarian, vegetarian, or vegan."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=5,
        )
        gpt_answer = response.choices[0].message.content.strip().lower()
        valid = {"omnivore", "pescatarian", "vegetarian", "vegan"}
        if gpt_answer not in valid:
            print(f"    Warning: invalid GPT classification: {gpt_answer}")
            return None, None
    except Exception as e:
        print(f"    Error during classification: {e}")
        return None, None

    # Safety net — scan title + description + ingredients + instructions.
    search_text = " ".join([
        title,
        description or "",
        " ".join(ingredient_list),
        " ".join(instruction_list),
    ])
    final, override_reason = apply_safety_net(gpt_answer, search_text)
    return final, override_reason


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

            # Classify (returns tier + optional safety-net override reason)
            classification, override_reason = classify_dietary(recipe, openai_client)
            latency_ms = int((time.time() - recipe_start) * 1000)

            if classification:
                stats.classified += 1
                if override_reason:
                    stats.safety_net_overrides += 1
                status = "[DRY-RUN]" if args.dry_run else "[PATCHED]"
                cls_label = f"{classification}*" if override_reason else classification

                if not args.dry_run:
                    if patch_recipe_dietary_classification(
                        base_url, token, recipe_id, classification
                    ):
                        log_msg(
                            f"{recipe_id:<36} {recipe_title:<50} {cls_label:<15} {status:<10} {latency_ms:<12}"
                        )
                    else:
                        log_msg(
                            f"{recipe_id:<36} {recipe_title:<50} {'ERROR':<15} {'FAILED':<10} {latency_ms:<12}"
                        )
                        stats.failed += 1
                else:
                    log_msg(
                        f"{recipe_id:<36} {recipe_title:<50} {cls_label:<15} {status:<10} {latency_ms:<12}"
                    )
                if override_reason:
                    log_msg(f"    ↳ safety-net override: {override_reason}")
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
        log_msg(f"Safety-net overrides:      {stats.safety_net_overrides} (rows marked with *)")
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
