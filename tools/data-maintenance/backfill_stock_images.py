#!/usr/bin/env python3
"""
Backfill: replace AI-generated hero images with vetted, license-free real photos.

For each official (non user-created) global recipe, search Pexels + Pixabay, vet
candidates with a vision model, and IF a real photo passes vetting:
    1. upload it     POST /global-recipes/{id}/images   (image_type=hero, source=pexels|pixabay)
    2. set thumbnail POST /photos/{new_id}/set-thumbnail {recipe_id}
    3. delete old AI DELETE /images/{old_thumbnail_id}
If nothing passes vetting, the recipe is left untouched (keeps its AI image).

AI images were always placeholders, so the old photo is deleted (not kept) to keep
it out of any future multi-image gallery.

SAFETY: dry-run by default. It only mutates the catalog with --execute, and even
then prompts for confirmation unless --yes is passed.

Usage:
    # dry run — reports the achievable replacement rate, writes nothing:
    ./venv/bin/python tools/data-maintenance/backfill_stock_images.py --limit 25

    # real run on 25 recipes (smoke test), with confirmation:
    ./venv/bin/python tools/data-maintenance/backfill_stock_images.py --limit 25 --execute

    # full catalog:
    ./venv/bin/python tools/data-maintenance/backfill_stock_images.py --execute --yes

Env (auto-loaded from local.env if present):
    EKITCHEN_BASE_URL, EKITCHEN_ADMIN_EMAIL, EKITCHEN_ADMIN_PASSWORD
    PEXELS_API_KEY, PIXABAY_API_KEY, OPENAI_API_KEY
"""

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Repo root is three levels up: tools/data-maintenance/<this file>.
_REPO_ROOT = Path(__file__).resolve().parents[2]
# Make `services` importable regardless of CWD.
sys.path.insert(0, str(_REPO_ROOT))


def load_local_env():
    env_path = _REPO_ROOT / "local.env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


load_local_env()

from services.stock_image import StockImageFinder  # noqa: E402


@dataclass
class Stats:
    scanned: int = 0
    eligible: int = 0
    matched: int = 0          # stock photo passed vetting
    replaced: int = 0         # uploaded + thumbnail set
    old_deleted: int = 0
    skipped_user: int = 0     # user-created, left alone
    no_match: int = 0         # no vetted stock -> kept AI
    errors: List[str] = field(default_factory=list)


# ── backend helpers ──────────────────────────────────────────────────────────
def login(base: str, email: str, password: str) -> str:
    r = requests.post(f"{base}/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    tok = r.json().get("access_token")
    if not tok:
        raise RuntimeError("login ok but no access_token")
    return tok


def fetch_all(base: str, token: str, hard_cap: int = 5000) -> List[Dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"}
    out, offset, size = [], 0, 200
    while len(out) < hard_cap:
        r = requests.get(f"{base}/global-recipes/", params={"limit": size, "offset": offset},
                         headers=headers, timeout=60)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < size:
            break
        offset += size
    return out


def upload_image(base: str, token: str, recipe_id: str, jpeg: bytes, source: str) -> Optional[str]:
    files = {"image": (f"{source}_hero.jpg", jpeg, "image/jpeg")}
    data = {"image_type": "hero", "source": source}
    r = requests.post(f"{base}/global-recipes/{recipe_id}/images",
                      headers={"Authorization": f"Bearer {token}"},
                      files=files, data=data, timeout=60)
    r.raise_for_status()
    return r.json().get("id")


def set_thumbnail(base: str, token: str, photo_id: str, recipe_id: str) -> None:
    r = requests.post(f"{base}/photos/{photo_id}/set-thumbnail",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"recipe_id": recipe_id}, timeout=30)
    r.raise_for_status()


def delete_image(base: str, token: str, image_id: str) -> None:
    r = requests.delete(f"{base}/images/{image_id}",
                        headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="cap recipes processed (0 = all)")
    ap.add_argument("--offset", type=int, default=0, help="skip the first N eligible recipes")
    ap.add_argument("--execute", action="store_true", help="actually mutate the catalog (default: dry run)")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    ap.add_argument("--keep-old", action="store_true", help="do not delete the old AI image")
    ap.add_argument("--max-replacements", type=int, default=0,
                    help="stop after N actual replacements (0 = unlimited); useful for a single-recipe smoke test")
    ap.add_argument("--pace", type=float, default=0.4, help="seconds between recipes")
    args = ap.parse_args()

    base = os.environ["EKITCHEN_BASE_URL"].rstrip("/")
    mode = "EXECUTE (live writes)" if args.execute else "DRY RUN (no writes)"
    print(f"Backend: {base}")
    print(f"Mode:    {mode}")

    if args.execute and not args.yes:
        ans = input(f"\n⚠️  This will REPLACE AI images and DELETE the old ones on {base}.\n"
                    f"    Type 'yes' to proceed: ").strip().lower()
        if ans != "yes":
            print("Aborted.")
            return

    finder = StockImageFinder(log=lambda m: None)  # quiet; we print our own per-recipe lines
    if not finder.enabled:
        print("❌ Stock finder not enabled (missing PEXELS/PIXABAY/OPENAI keys).")
        sys.exit(1)

    token = login(base, os.environ["EKITCHEN_ADMIN_EMAIL"], os.environ["EKITCHEN_ADMIN_PASSWORD"])
    recipes = fetch_all(base, token)
    print(f"Fetched {len(recipes)} recipes\n")

    st = Stats()
    eligible_seen = 0
    for row in recipes:
        st.scanned += 1
        if row.get("user_created"):
            st.skipped_user += 1
            continue

        eligible_seen += 1
        if eligible_seen <= args.offset:
            continue
        if args.limit and st.eligible >= args.limit:
            break
        st.eligible += 1

        rid = row["id"]
        name = (row.get("name") or "").strip()
        cuisine = row.get("cuisine") or ""
        old_thumb = row.get("thumbnail_photo_id")

        try:
            stock = finder.find(name, cuisine)
        except Exception as e:
            st.errors.append(f"{name}: find error: {e}")
            print(f"  �— {name[:40]:40} ERROR finding: {e}")
            continue

        if not stock:
            st.no_match += 1
            print(f"  ·  {name[:40]:40} no vetted stock → keep AI")
            continue

        st.matched += 1
        tag = f"{stock.source}/{stock.confidence:.2f}"
        if not args.execute:
            print(f"  ✓  {name[:40]:40} WOULD replace with {tag} (q='{stock.query}')")
            time.sleep(args.pace)
            continue

        # live writes
        try:
            new_id = upload_image(base, token, rid, stock.jpeg_bytes, stock.source)
            if not new_id:
                raise RuntimeError("upload returned no id")
            set_thumbnail(base, token, new_id, rid)
            st.replaced += 1
            deleted = ""
            if old_thumb and old_thumb != new_id and not args.keep_old:
                try:
                    delete_image(base, token, old_thumb)
                    st.old_deleted += 1
                    deleted = " (old deleted)"
                except Exception as e:
                    st.errors.append(f"{name}: delete old {old_thumb}: {e}")
                    deleted = f" (old delete FAILED: {e})"
            print(f"  ✓  {name[:40]:40} replaced with {tag}{deleted}")
        except Exception as e:
            st.errors.append(f"{name}: replace error: {e}")
            print(f"  ✗  {name[:40]:40} REPLACE FAILED: {e}")

        if args.max_replacements and st.replaced >= args.max_replacements:
            print(f"\n⏹  Reached --max-replacements={args.max_replacements}, stopping.")
            break
        time.sleep(args.pace)

    # summary
    print("\n" + "=" * 60)
    print(f"Scanned:           {st.scanned}")
    print(f"Skipped (user):    {st.skipped_user}")
    print(f"Eligible processed:{st.eligible}")
    print(f"Stock matched:     {st.matched}  ({100*st.matched/max(st.eligible,1):.0f}% of eligible)")
    print(f"Kept AI (no match):{st.no_match}")
    if args.execute:
        print(f"Replaced:          {st.replaced}")
        print(f"Old AI deleted:    {st.old_deleted}")
    if st.errors:
        print(f"\nErrors ({len(st.errors)}):")
        for e in st.errors[:20]:
            print(f"  - {e}")
    if not args.execute:
        print("\n(DRY RUN — nothing changed. Re-run with --execute to apply.)")


if __name__ == "__main__":
    main()
