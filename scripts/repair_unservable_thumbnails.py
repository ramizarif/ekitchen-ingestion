#!/usr/bin/env python3
"""
Repair recipes whose thumbnail reference points at an image that cannot be served.

This is the sibling of backfill_recipe_images.py, which handles the *absent*
case: thumbnail_photo_id IS NULL. It cannot help here, because these recipes
have a thumbnail id — the id is simply no longer backed by an object in storage.
Every query that asks "does this recipe have a picture?" answers yes, and the
app then renders a fallback.

Uploading a replacement is not enough on its own: the backend auto-promotes a
new upload to thumbnail only when a recipe has *no* thumbnail, so a recipe with
a dangling one keeps pointing at the dead photo. This script therefore sets the
new photo as the thumbnail explicitly.

    Discover  GET  /global-recipes/            (paginate, keep rows with a thumbnail id)
    Probe     GET  /photos/{thumbnail_photo_id}  -> non-200 means unservable
    Generate  DALL-E 3, re-encoded to JPEG
    Upload    POST /global-recipes/{id}/images   -> new photo id
    Repoint   POST /photos/{new_id}/set-thumbnail {"recipe_id": ...}
    Verify    GET  /photos/{new_id}              -> 200

Usage:
    source local.env    # or prod.env to repair production
    python scripts/repair_unservable_thumbnails.py --scan               # report only, no cost
    python scripts/repair_unservable_thumbnails.py --recipe-ids a,b,c   # repair a known set
    python scripts/repair_unservable_thumbnails.py --scan --repair      # find and fix

Environment:
    EKITCHEN_BASE_URL, EKITCHEN_ADMIN_EMAIL, EKITCHEN_ADMIN_PASSWORD, OPENAI_API_KEY

Cost: ~$0.04 per repaired image (DALL-E 3, standard, 1024x1024). --scan is free.
"""

import argparse
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backfill_recipe_images import (  # noqa: E402
    login,
    build_dalle_prompt,
    generate_jpeg,
    safe_filename,
)


def fetch_recipes_with_thumbnails(
    base_url: str, token: str, batch_size: int = 200
) -> List[Dict[str, Any]]:
    """Every recipe that claims to have a thumbnail — the candidates for a broken one."""
    headers = {"Authorization": f"Bearer {token}"}
    rows: List[Dict[str, Any]] = []
    offset = 0

    while True:
        resp = requests.get(
            f"{base_url}/global-recipes/",
            params={"limit": batch_size, "offset": offset},
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break

        rows.extend(r for r in batch if r.get("thumbnail_photo_id"))
        print(f"  Scanned {offset + len(batch)} recipes, {len(rows)} with a thumbnail id...")

        if len(batch) < batch_size:
            break
        offset += batch_size

    return rows


def photo_is_servable(base_url: str, token: str, photo_id: str) -> bool:
    """A thumbnail id is only worth anything if the bytes come back."""
    try:
        resp = requests.get(
            f"{base_url}/photos/{photo_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=45,
        )
        return resp.status_code == 200 and len(resp.content) > 0
    except (requests.Timeout, requests.ConnectionError):
        # Treat a transport failure as "unknown", not "broken" — repairing on a
        # flaky connection would regenerate images that were fine all along.
        return True


def upload_image(
    base_url: str, token: str, recipe_id: str, jpeg: bytes, filename: str
) -> Tuple[Optional[str], Optional[str]]:
    """POST a hero image and return its new photo id."""
    resp = requests.post(
        f"{base_url}/global-recipes/{recipe_id}/images",
        headers={"Authorization": f"Bearer {token}"},
        files={"image": (filename, jpeg, "image/jpeg")},
        data={"image_type": "hero"},
        timeout=90,
    )
    if resp.status_code >= 400:
        return None, f"HTTP {resp.status_code}: {resp.text[:200]}"

    try:
        body = resp.json()
    except ValueError:
        return None, f"upload returned non-JSON: {resp.text[:120]}"

    payload = body.get("data", body) if isinstance(body, dict) else body
    photo_id = payload.get("id") or payload.get("photo_id") if isinstance(payload, dict) else None
    if not photo_id:
        return None, f"upload succeeded but no id in response: {str(body)[:160]}"
    return photo_id, None


def set_as_thumbnail(base_url: str, token: str, photo_id: str, recipe_id: str) -> Optional[str]:
    """The step the absent-image backfill never needs: displace the dead reference."""
    resp = requests.post(
        f"{base_url}/photos/{photo_id}/set-thumbnail",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"recipe_id": recipe_id},
        timeout=45,
    )
    if resp.status_code >= 400:
        return f"HTTP {resp.status_code}: {resp.text[:200]}"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scan", action="store_true", help="probe every thumbnail and report")
    ap.add_argument("--repair", action="store_true", help="regenerate what the scan found broken")
    ap.add_argument("--recipe-ids", default="", help="comma-separated ids to repair directly")
    ap.add_argument("--limit", type=int, default=0, help="cap how many are repaired")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = ap.parse_args()

    if not args.scan and not args.recipe_ids:
        ap.error("give --scan, or --recipe-ids with a known set")

    # The backend repo spells these BASEURL/ADMINEMAIL/ADMINPASS; the ingestion
    # repo's own env uses the underscored forms. Accept either.
    base_url = (os.getenv("EKITCHEN_BASE_URL") or os.getenv("EKITCHEN_BASEURL") or "").rstrip("/")
    email = os.getenv("EKITCHEN_ADMIN_EMAIL") or os.getenv("EKITCHEN_ADMINEMAIL")
    password = os.getenv("EKITCHEN_ADMIN_PASSWORD") or os.getenv("EKITCHEN_ADMINPASS")
    if not base_url or not email or not password:
        print("Missing base URL / admin credentials — source local.env or prod.env")
        return 1

    print(f"Backend: {base_url}")
    token = login(base_url, email, password)
    print("Authenticated\n")

    broken: List[Dict[str, Any]] = []

    if args.recipe_ids:
        wanted = {r.strip() for r in args.recipe_ids.split(",") if r.strip()}
        print(f"Fetching {len(wanted)} named recipes...")
        for rid in sorted(wanted):
            resp = requests.get(
                f"{base_url}/global-recipes/{rid}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=45,
            )
            if resp.status_code >= 400:
                print(f"  ⚠️  {rid}: HTTP {resp.status_code}")
                continue
            body = resp.json()
            broken.append(body.get("data", body))
    else:
        print("Scanning for thumbnails that cannot be served...")
        candidates = fetch_recipes_with_thumbnails(base_url, token)
        print(f"\nProbing {len(candidates)} thumbnails (this is the slow part)...\n")
        for i, r in enumerate(candidates, 1):
            if photo_is_servable(base_url, token, r["thumbnail_photo_id"]):
                continue
            broken.append(r)
            print(f"  ✗ {r.get('name', r['id'])[:52]}  ({r['id']})")
            if i % 100 == 0:
                print(f"    ...{i}/{len(candidates)} probed")

    print(f"\n{len(broken)} recipe(s) with an unservable thumbnail.")
    if not broken:
        return 0

    if not args.repair and not args.recipe_ids:
        print("\nScan only. Re-run with --repair to regenerate these.")
        return 0

    targets = broken[: args.limit] if args.limit > 0 else broken
    est = len(targets) * 0.04
    print(f"\nAbout to regenerate {len(targets)} image(s) — roughly ${est:.2f} of DALL-E.")
    if not args.yes:
        if input("Continue? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Nothing done.")
            return 0

    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    repaired, failed = 0, []

    for i, recipe in enumerate(targets, 1):
        name = recipe.get("name") or recipe.get("title") or recipe["id"]
        print(f"\n[{i}/{len(targets)}] {name}")

        try:
            jpeg = generate_jpeg(openai_client, build_dalle_prompt(recipe))
        except Exception as e:  # noqa: BLE001 — one bad recipe must not end the run
            print(f"    generation failed: {type(e).__name__}: {e}")
            failed.append((name, "generate"))
            continue

        photo_id, err = upload_image(
            base_url, token, recipe["id"], jpeg, f"{safe_filename(name)}.jpg"
        )
        if err:
            print(f"    upload failed: {err}")
            failed.append((name, "upload"))
            continue

        err = set_as_thumbnail(base_url, token, photo_id, recipe["id"])
        if err:
            print(f"    uploaded {photo_id} but could not set as thumbnail: {err}")
            failed.append((name, "set-thumbnail"))
            continue

        if not photo_is_servable(base_url, token, photo_id):
            print(f"    set as thumbnail but {photo_id} still will not serve")
            failed.append((name, "verify"))
            continue

        repaired += 1
        print(f"    repaired -> {photo_id}")
        time.sleep(1)  # stay well under the image rate limit

    print(f"\nRepaired {repaired}/{len(targets)}.")
    for name, stage in failed:
        print(f"  failed at {stage}: {name}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
