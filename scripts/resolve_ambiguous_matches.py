#!/usr/bin/env python3
"""
Auto-resolve all unresolved ambiguous step matches using GPT-4o-mini.

Fetches unresolved matches from the eKitchen backend, uses GPT-4o-mini to determine
the correct ingredient based on recipe context, and resolves them via the API.

Usage:
    source local.env
    python scripts/resolve_ambiguous_matches.py

Environment variables required:
    EKITCHEN_BASE_URL       - eKitchen backend URL (e.g., http://localhost:8081)
    EKITCHEN_ADMIN_EMAIL    - Admin email for authentication
    EKITCHEN_ADMIN_PASSWORD - Admin password for authentication
    OPENAI_API_KEY          - OpenAI API key
"""

import os
import sys
import time
import requests
from openai import OpenAI


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


def get_unresolved_matches(base_url: str, token: str) -> list:
    """Fetch all unresolved ambiguous step matches."""
    resp = requests.get(
        f"{base_url}/global-recipes/ambiguous-step-matches",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    matches = resp.json()
    # Filter to only unresolved
    return [m for m in matches if not m.get("resolved_match")]


def get_recipe(base_url: str, token: str, recipe_id: str) -> dict:
    """Fetch a global recipe by ID."""
    resp = requests.get(
        f"{base_url}/global-recipes/{recipe_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def resolve_with_ai(client: OpenAI, match: dict, recipe: dict) -> str | None:
    """Use GPT-4o-mini to determine the correct ingredient match."""
    recipe_name = recipe.get("name", "Unknown")

    # Extract ingredient names from the recipe
    ingredients = recipe.get("ingredients", [])
    ingredient_names = [ing.get("ingredient_name", ing.get("name", "")) for ing in ingredients]
    ingredients_list = ", ".join(ingredient_names) if ingredient_names else "N/A"

    step_position = match.get("step_position", "?")
    template = match.get("template", "")
    ambiguous_word = match.get("ambiguous_word", "")
    possible_matches = match.get("possible_matches", [])

    prompt = (
        f"A recipe step contains an ambiguous ingredient reference that could match multiple ingredients.\n\n"
        f"Recipe: {recipe_name}\n"
        f"All ingredients in this recipe: {ingredients_list}\n"
        f"Step {step_position}: \"{template}\"\n"
        f"Ambiguous word in the step: \"{ambiguous_word}\"\n"
        f"Possible ingredient matches: {', '.join(possible_matches)}\n\n"
        f"Based on the cooking context of this step, which specific ingredient does "
        f"\"{ambiguous_word}\" most likely refer to?\n\n"
        f"Respond with ONLY the exact ingredient name from the possible matches list. Nothing else."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt},
        ],
        max_tokens=100,
        temperature=0.0,
    )

    answer = response.choices[0].message.content.strip()

    # Validate the answer is one of the possible matches
    if answer in possible_matches:
        return answer

    # Try case-insensitive match
    for pm in possible_matches:
        if answer.lower() == pm.lower():
            return pm

    # Try partial match as fallback
    for pm in possible_matches:
        if answer.lower() in pm.lower() or pm.lower() in answer.lower():
            return pm

    return None


def resolve_match(base_url: str, token: str, match_id: str, resolved_match: str) -> bool:
    """Resolve an ambiguous step match via the API."""
    resp = requests.patch(
        f"{base_url}/global-recipes/ambiguous-step-matches/{match_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"resolved_match": resolved_match},
        timeout=30,
    )
    resp.raise_for_status()
    return True


def main():
    # Load config from environment
    base_url = os.environ.get("EKITCHEN_BASE_URL")
    admin_email = os.environ.get("EKITCHEN_ADMIN_EMAIL")
    admin_password = os.environ.get("EKITCHEN_ADMIN_PASSWORD")
    openai_api_key = os.environ.get("OPENAI_API_KEY")

    missing = []
    if not base_url:
        missing.append("EKITCHEN_BASE_URL")
    if not admin_email:
        missing.append("EKITCHEN_ADMIN_EMAIL")
    if not admin_password:
        missing.append("EKITCHEN_ADMIN_PASSWORD")
    if not openai_api_key:
        missing.append("OPENAI_API_KEY")

    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        print("Run: source local.env")
        sys.exit(1)

    # Strip trailing slash from base URL
    base_url = base_url.rstrip("/")

    # Authenticate
    print(f"Authenticating with {base_url}...")
    try:
        token = login(base_url, admin_email, admin_password)
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)
    print("Authenticated successfully.")

    # Fetch unresolved matches
    print("Fetching unresolved ambiguous step matches...")
    matches = get_unresolved_matches(base_url, token)
    total = len(matches)
    print(f"Found {total} unresolved matches.")

    if total == 0:
        print("Nothing to resolve.")
        return

    # Initialize OpenAI client
    openai_client = OpenAI(api_key=openai_api_key)

    # Cache recipes to avoid re-fetching
    recipe_cache: dict[str, dict] = {}

    resolved_count = 0
    failed_count = 0

    for i, match in enumerate(matches, 1):
        match_id = match["id"]
        recipe_id = match["recipe_id"]
        ambiguous_word = match.get("ambiguous_word", "?")
        step_position = match.get("step_position", "?")

        try:
            # Fetch recipe (with caching)
            if recipe_id not in recipe_cache:
                recipe_cache[recipe_id] = get_recipe(base_url, token, recipe_id)
            recipe = recipe_cache[recipe_id]
            recipe_name = recipe.get("name", "Unknown")

            # Resolve with AI
            resolved = resolve_with_ai(openai_client, match, recipe)

            if resolved is None:
                print(f"[{i}/{total}] SKIP: Could not resolve \"{ambiguous_word}\" "
                      f"in step {step_position} of \"{recipe_name}\"")
                failed_count += 1
                time.sleep(0.2)
                continue

            # Submit resolution
            resolve_match(base_url, token, match_id, resolved)
            resolved_count += 1
            print(f"[{i}/{total}] Resolved: \"{ambiguous_word}\" -> \"{resolved}\" "
                  f"in step {step_position} of \"{recipe_name}\"")

        except Exception as e:
            failed_count += 1
            print(f"[{i}/{total}] ERROR: Match {match_id} failed: {e}")

        # Rate limiting
        time.sleep(0.2)

    # Summary
    print(f"\nDone. Resolved: {resolved_count}/{total}, Failed/Skipped: {failed_count}/{total}")


if __name__ == "__main__":
    main()
