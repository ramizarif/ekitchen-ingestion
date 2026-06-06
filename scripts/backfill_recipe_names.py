#!/usr/bin/env python3
"""
Backfill recipe names by stripping publisher attribution suffixes.

Scans all global recipes, applies the same trailer-stripper used during
ingestion (e.g. "Foo Recipe by Tasty" → "Foo"), and PATCHes recipes whose
cleaned name differs from the stored name.

Usage:
    source local.env
    python scripts/backfill_recipe_names.py --dry-run         # preview only
    python scripts/backfill_recipe_names.py --limit 10        # cap to 10 (smoke test)
    python scripts/backfill_recipe_names.py                   # full run, prompts to confirm

Environment variables required:
    EKITCHEN_BASE_URL
    EKITCHEN_ADMIN_EMAIL
    EKITCHEN_ADMIN_PASSWORD

To extend: add publisher names to KNOWN_SOURCES below. Keep this list in sync
with the same constant in legacy/src/processing/direct_recipe_processor.py
so existing data and future ingestion stay aligned.
"""

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


# KEEP IN SYNC across: services/recipe_processor.py,
# legacy/src/processing/direct_recipe_processor.py, scripts/backfill_recipe_names.py
KNOWN_SOURCES = [
    "Tasty", "Simply Recipes", "SimplyRecipes", "EatingWell", "Eating Well",
    "Food Network", "Allrecipes", "All Recipes", "Epicurious", "BBC Good Food",
    "Serious Eats", "Budget Bytes", "Delish", "Bon Appétit", "Bon Appetit",
    "NYT Cooking", "Food.com", "The Kitchn", "Taste of Home",
]


def clean_recipe_title(title: Optional[str]) -> Optional[str]:
    """Strip publisher attribution and a trailing 'Recipe' from a scraped title.
    Handles 'X Recipe by Tasty', 'X by Tasty', 'X | Food Network',
    'X - Simply Recipes', 'X (Epicurious)', 'X from EatingWell', and a bare
    trailing 'Recipe'/'Recipes'. Case-insensitive; never returns empty."""
    if not title:
        return title
    cleaned = title.strip()
    for source in KNOWN_SOURCES:
        s = re.escape(source)
        for pat in (
            rf"\s+Recipes?\s+by\s+{s}\s*$",
            rf"\s+by\s+{s}\s*$",
            rf"\s+from\s+{s}\s*$",
            rf"\s*[|\-–—:]\s*{s}\s*$",
            rf"\s*\(\s*{s}\s*\)\s*$",
        ):
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+Recipes?\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" |-–—:")
    return cleaned.strip() or title.strip()


@dataclass
class BackfillStats:
    total_scanned: int = 0
    needing_cleanup: int = 0
    patched: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)


def login(base_url: str, email: str, password: str) -> str:
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


def fetch_recipes_needing_rename(
    base_url: str, token: str, limit: int = 0, batch_size: int = 200
) -> List[Dict[str, str]]:
    """
    Paginate /global-recipes and return [{id, old, new}] for recipes whose
    cleaned name differs from the stored name.
    """
    headers = {"Authorization": f"Bearer {token}"}
    out: List[Dict[str, str]] = []
    offset = 0
    scanned = 0

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
            except (requests.Timeout, requests.ConnectionError):
                if attempt < len(backoffs):
                    print(f"  Fetch timeout, retrying in {backoffs[attempt]}s")
                    time.sleep(backoffs[attempt])
                    continue
                raise

        if not batch:
            break

        for r in batch:
            scanned += 1
            old = r.get("name") or ""
            new = clean_recipe_title(old) or ""
            if new and new != old:
                out.append({"id": r["id"], "old": old, "new": new})

        print(f"  Scanned {scanned} recipes, {len(out)} needing rename so far...")

        if limit > 0 and len(out) >= limit:
            out = out[:limit]
            break

        if len(batch) < batch_size:
            break

        offset += batch_size

    return out


def patch_recipe_name(base_url: str, token: str, recipe_id: str, new_name: str) -> tuple[bool, Optional[str]]:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"id": recipe_id, "name": new_name}
    backoffs = [1, 2, 4]
    for attempt in range(len(backoffs) + 1):
        try:
            resp = requests.patch(
                f"{base_url}/global-recipes/{recipe_id}",
                json=body,
                headers=headers,
                timeout=60,
            )
            if resp.status_code < 400:
                return True, None
            if resp.status_code >= 500 or resp.status_code == 429:
                if attempt < len(backoffs):
                    print(f"    PATCH {resp.status_code}, retrying in {backoffs[attempt]}s")
                    time.sleep(backoffs[attempt])
                    continue
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < len(backoffs):
                time.sleep(backoffs[attempt])
                continue
            return False, f"{type(e).__name__}: {e}"
    return False, "exhausted retries"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()

    base_url = os.environ.get("EKITCHEN_BASE_URL")
    email = os.environ.get("EKITCHEN_ADMIN_EMAIL")
    password = os.environ.get("EKITCHEN_ADMIN_PASSWORD")

    missing = [k for k, v in {
        "EKITCHEN_BASE_URL": base_url,
        "EKITCHEN_ADMIN_EMAIL": email,
        "EKITCHEN_ADMIN_PASSWORD": password,
    }.items() if not v]
    if missing:
        print(f"❌ Missing env vars: {', '.join(missing)}\n   Run: source local.env")
        sys.exit(1)

    print(f"🍽️  Recipe Name Cleanup — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📡 Target: {base_url}")
    print(f"🧹 Stripping suffixes for sources: {', '.join(KNOWN_SOURCES)}")
    print(f"🔐 Authenticating as {email}...")
    token = login(base_url, email, password)
    print("✅ Authenticated\n")

    print("📋 Scanning global recipes...")
    rows = fetch_recipes_needing_rename(base_url, token, limit=args.limit, batch_size=args.batch_size)
    stats = BackfillStats(needing_cleanup=len(rows))

    if not rows:
        print("\n✅ No recipes need renaming. Nothing to do.")
        return

    print(f"\n🎯 Found {len(rows)} recipes needing rename.\n")
    preview = rows[:50] if not args.dry_run else rows
    for row in preview:
        print(f"  {row['id'][:8]}…  {row['old']!r}\n             → {row['new']!r}")
    if not args.dry_run and len(rows) > 50:
        print(f"  ... and {len(rows) - 50} more")

    if args.dry_run:
        return

    confirm = input(f"\nProceed with renaming {len(rows)} recipes? [y/N]: ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Aborted.")
        return

    start = time.time()
    print(f"\n🚀 Starting rename of {len(rows)} recipes...\n")
    for i, row in enumerate(rows, 1):
        prefix = f"[{i}/{len(rows)}] {row['old'][:60]}"
        ok, err = patch_recipe_name(base_url, token, row["id"], row["new"])
        if ok:
            stats.patched += 1
            print(f"{prefix} → {row['new']}")
        else:
            stats.failed += 1
            stats.errors.append(f"{row['id']}: {err}")
            print(f"{prefix}  ❌ {err}")
        time.sleep(0.2)  # gentle pacing

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print("📊 RENAME SUMMARY")
    print(f"{'=' * 60}")
    print(f"Recipes needing rename:  {stats.needing_cleanup}")
    print(f"Successfully patched:    {stats.patched}")
    print(f"Failed:                  {stats.failed}")
    print(f"Total runtime:           {elapsed:.1f}s")
    if stats.errors:
        print(f"\n⚠️  Errors (first 10):")
        for err in stats.errors[:10]:
            print(f"  • {err}")


if __name__ == "__main__":
    main()
