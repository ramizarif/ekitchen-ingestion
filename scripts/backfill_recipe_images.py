#!/usr/bin/env python3
"""
Backfill DALL-E hero images for global recipes that landed in eKitchen without one.

Fetches all global recipes with thumbnail_photo_id IS NULL from the backend,
generates a food-photography prompt from each recipe's name + description +
ingredients, calls DALL-E 3 (quality="standard") to render a 1024x1024 image,
re-encodes it as a JPEG (q=88) to keep payloads small, and POSTs it to
/global-recipes/{id}/images with image_type=hero.

Usage:
    source local.env
    python scripts/backfill_recipe_images.py --dry-run         # list missing-image recipes, no calls
    python scripts/backfill_recipe_images.py --limit 10        # cap to 10 (smoke test)
    python scripts/backfill_recipe_images.py                   # full run, prompts to confirm

Environment variables required:
    EKITCHEN_BASE_URL       - eKitchen backend URL
    EKITCHEN_ADMIN_EMAIL    - Admin email for authentication
    EKITCHEN_ADMIN_PASSWORD - Admin password for authentication
    OPENAI_API_KEY          - OpenAI API key (for DALL-E 3)

Cost: ~$0.04 per image with DALL-E 3 (standard quality, 1024x1024).
Pacing: ~1 image/second to stay well under OpenAI rate limits.
"""

import argparse
import base64
import io
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from openai import OpenAI
from PIL import Image


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class BackfillStats:
    total_fetched: int = 0
    missing_images: int = 0
    generated: int = 0
    uploaded: int = 0
    failed_generation: int = 0
    failed_upload: int = 0
    errors: List[str] = field(default_factory=list)


# ── Backend API helpers ──────────────────────────────────────────────────────

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


def fetch_recipes_missing_images(
    base_url: str, token: str, limit: int = 0, batch_size: int = 200
) -> List[Dict[str, Any]]:
    """Paginate /global-recipes and return rows where thumbnail_photo_id is null."""
    headers = {"Authorization": f"Bearer {token}"}
    missing: List[Dict[str, Any]] = []
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
            except (requests.Timeout, requests.ConnectionError):
                if attempt < len(backoffs):
                    print(f"  Fetch timeout, retrying in {backoffs[attempt]}s")
                    time.sleep(backoffs[attempt])
                    continue
                raise

        if not batch:
            break

        # thumbnail_photo_id is omitempty — absent OR null both mean "no image"
        for r in batch:
            if not r.get("thumbnail_photo_id"):
                missing.append(r)

        print(f"  Scanned {offset + len(batch)} recipes, {len(missing)} missing images so far...")

        if limit > 0 and len(missing) >= limit:
            missing = missing[:limit]
            break

        if len(batch) < batch_size:
            break

        offset += batch_size

    return missing


def upload_recipe_image(
    base_url: str, token: str, recipe_id: str, jpeg_bytes: bytes, filename: str
) -> tuple[bool, Optional[str]]:
    """POST a JPEG to /global-recipes/{id}/images as a hero. Returns (ok, error_msg)."""
    headers = {"Authorization": f"Bearer {token}"}
    files = {"image": (filename, jpeg_bytes, "image/jpeg")}
    data = {"image_type": "hero"}
    backoffs = [1, 2, 4]
    for attempt in range(len(backoffs) + 1):
        try:
            resp = requests.post(
                f"{base_url}/global-recipes/{recipe_id}/images",
                headers=headers,
                files=files,
                data=data,
                timeout=60,
            )
            if resp.status_code < 400:
                return True, None
            if resp.status_code >= 500 or resp.status_code == 429:
                if attempt < len(backoffs):
                    print(f"    Upload {resp.status_code}, retrying in {backoffs[attempt]}s")
                    time.sleep(backoffs[attempt])
                    continue
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < len(backoffs):
                print(f"    Upload timeout/conn-err, retrying in {backoffs[attempt]}s ({type(e).__name__})")
                time.sleep(backoffs[attempt])
                continue
            return False, f"{type(e).__name__}: {e}"
    return False, "exhausted retries"


# ── Prompt builder (ported from direct_recipe_processor._create_recipe_website_prompt) ─────────

def build_dalle_prompt(recipe: Dict[str, Any]) -> str:
    title = recipe.get("name") or "Unknown Recipe"
    description = recipe.get("description") or ""
    ingredients = recipe.get("ingredients") or []
    ingredient_names = []
    for ing in ingredients[:8]:
        if isinstance(ing, dict):
            n = ing.get("name") or ing.get("ingredient_name")
            if n:
                ingredient_names.append(n)
    main_ingredients = ", ".join(ingredient_names) if ingredient_names else "main ingredients"

    title_lower = title.lower()
    if "baked" in title_lower or "roasted" in title_lower:
        texture = "golden and crispy"
    elif "fried" in title_lower:
        texture = "crispy and golden-brown"
    elif "grilled" in title_lower:
        texture = "charred and juicy"
    elif "sauced" in title_lower or "buffalo" in title_lower:
        texture = "coated in glossy sauce"
    else:
        texture = "perfectly prepared"

    composition = "Overhead composition, zoomed in on the serving dish, the food fills the frame with natural presentation"

    if "wings" in title_lower or "buffalo" in title_lower:
        props = ["fresh celery sticks", "a small bowl of ranch dipping sauce", "a pinch bowl of salt", "folded linen napkin with utensils"]
    elif "pasta" in title_lower or "noodles" in title_lower:
        props = ["grated parmesan cheese", "fresh herbs", "a wooden spoon", "linen kitchen towel"]
    elif "soup" in title_lower or "curry" in title_lower or "stew" in title_lower:
        props = ["fresh cilantro garnish", "a ladle", "crusty bread slices", "cloth napkin"]
    elif "salad" in title_lower:
        props = ["wooden serving utensils", "small bowl of dressing", "fresh lemon wedges", "clean kitchen cloth"]
    else:
        props = ["fresh herbs for garnish", "serving utensils", "a folded napkin", "small condiment bowl"]

    supporting = f"Surrounded by {', '.join(props)}"
    lighting = "Soft natural daylight from the side, warm even lighting, vibrant but true-to-life colors, no harsh shadows"
    aesthetic = "Styled like modern recipe blogs, cozy kitchen atmosphere, rustic but clean, highly appetizing presentation"

    return (
        f"{composition} of {title} (key ingredients: {main_ingredients}), {texture}. "
        f"The dish is arranged in a rustic serving dish, {supporting}. {lighting}. {aesthetic}."
    )


# ── DALL-E generation + JPEG re-encoding ─────────────────────────────────────

def generate_jpeg(openai_client: OpenAI, prompt: str) -> bytes:
    """Call gpt-image-1 (high quality), decode base64, re-encode as JPEG q=88, return bytes."""
    response = openai_client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
        quality="medium",
        n=1,
    )
    # gpt-image-1 returns base64-encoded PNG (no URL); dall-e-3 is no longer available.
    image_content = base64.b64decode(response.data[0].b64_json)

    out = io.BytesIO()
    with Image.open(io.BytesIO(image_content)) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(out, format="JPEG", quality=88, optimize=True, progressive=True)
    return out.getvalue()


def safe_filename(title: str) -> str:
    import re
    slug = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")[:50]
    return f"{slug or 'recipe'}.jpg"


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="List missing-image recipes, no DALL-E calls or uploads")
    parser.add_argument("--limit", type=int, default=0, help="Cap how many recipes to process (0 = no cap)")
    parser.add_argument("--batch-size", type=int, default=200, help="Pagination batch size when listing recipes")
    args = parser.parse_args()

    base_url = os.environ.get("EKITCHEN_BASE_URL")
    email = os.environ.get("EKITCHEN_ADMIN_EMAIL")
    password = os.environ.get("EKITCHEN_ADMIN_PASSWORD")
    openai_key = os.environ.get("OPENAI_API_KEY")

    missing = []
    for var, val in [
        ("EKITCHEN_BASE_URL", base_url),
        ("EKITCHEN_ADMIN_EMAIL", email),
        ("EKITCHEN_ADMIN_PASSWORD", password),
        ("OPENAI_API_KEY", openai_key),
    ]:
        if not val:
            missing.append(var)
    if missing:
        print(f"❌ Missing required env vars: {', '.join(missing)}")
        print("   Run: source local.env")
        sys.exit(1)

    print(f"🍽️  Recipe Image Backfill — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📡 Target: {base_url}")
    print(f"🔐 Authenticating as {email}...")
    token = login(base_url, email, password)
    print("✅ Authenticated\n")

    print("📋 Scanning global recipes for missing images...")
    recipes = fetch_recipes_missing_images(base_url, token, limit=args.limit, batch_size=args.batch_size)
    stats = BackfillStats(missing_images=len(recipes))

    if not recipes:
        print("\n✅ No recipes missing images. Nothing to do.")
        return

    print(f"\n🎯 Found {len(recipes)} recipes missing hero images.")
    if args.dry_run:
        print("\n— DRY RUN — listing only:")
        for r in recipes[:50]:
            print(f"  • {r.get('id')[:8]}…  {r.get('name')}")
        if len(recipes) > 50:
            print(f"  ... and {len(recipes) - 50} more")
        return

    estimated_cost = len(recipes) * 0.04
    estimated_minutes = len(recipes) * 1.0 / 60  # ~1s/recipe
    print(f"💸 Estimated DALL-E cost: ${estimated_cost:.2f}  (${0.04} × {len(recipes)})")
    print(f"⏱  Estimated runtime: ~{estimated_minutes:.1f} minutes (1 req/sec pacing)")
    confirm = input(f"\nProceed with backfill? [y/N]: ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Aborted.")
        return

    openai_client = OpenAI(api_key=openai_key)
    start = time.time()

    print(f"\n🚀 Starting backfill of {len(recipes)} recipes...\n")
    for i, recipe in enumerate(recipes, 1):
        recipe_id = recipe.get("id")
        name = recipe.get("name") or "(unnamed)"
        prefix = f"[{i}/{len(recipes)}] {name[:60]}"

        try:
            prompt = build_dalle_prompt(recipe)
            print(f"{prefix}\n  🎨 Generating DALL-E image...")
            jpeg_bytes = generate_jpeg(openai_client, prompt)
            stats.generated += 1
            kb = len(jpeg_bytes) / 1024
            print(f"  ✅ Generated {kb:.0f} KB JPEG")
        except Exception as e:
            stats.failed_generation += 1
            err = f"{recipe_id}: generation failed — {type(e).__name__}: {e}"
            stats.errors.append(err)
            print(f"  ❌ Generation failed: {e}")
            time.sleep(1.0)
            continue

        try:
            ok, err = upload_recipe_image(base_url, token, recipe_id, jpeg_bytes, safe_filename(name))
            if ok:
                stats.uploaded += 1
                print(f"  📤 Uploaded as hero")
            else:
                stats.failed_upload += 1
                stats.errors.append(f"{recipe_id}: upload failed — {err}")
                print(f"  ❌ Upload failed: {err}")
        except Exception as e:
            stats.failed_upload += 1
            stats.errors.append(f"{recipe_id}: upload exception — {type(e).__name__}: {e}")
            print(f"  ❌ Upload exception: {e}")

        time.sleep(1.0)  # 1 req/sec pacing

    elapsed = time.time() - start
    actual_cost = stats.generated * 0.04

    print(f"\n{'=' * 60}")
    print("📊 BACKFILL SUMMARY")
    print(f"{'=' * 60}")
    print(f"Recipes missing images:   {stats.missing_images}")
    print(f"Images generated:         {stats.generated}")
    print(f"Images uploaded:          {stats.uploaded}")
    print(f"Generation failures:      {stats.failed_generation}")
    print(f"Upload failures:          {stats.failed_upload}")
    print(f"Estimated DALL-E cost:    ${actual_cost:.2f}")
    print(f"Total runtime:            {elapsed:.1f}s ({elapsed/60:.1f} min)")
    if stats.errors:
        print(f"\n⚠️  {len(stats.errors)} errors (first 10):")
        for err in stats.errors[:10]:
            print(f"  • {err}")


if __name__ == "__main__":
    main()
