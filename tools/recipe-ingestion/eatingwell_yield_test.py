#!/usr/bin/env python3
"""
READ-ONLY: test which EatingWell listing surfaces actually return recipe URLs, and how many.
EatingWell's category-hub pages returned 0 earlier (JS-rendered index links), but its SEARCH
pages are a verified harvest surface. So we probe broad *savory category-term* searches —
effectively browsing EatingWell's savory catalog by theme — plus a couple of hub guesses.

Writes nothing, spends nothing. Output = ranked working EatingWell listing URLs to seed a
savory harvest_ingest config.
"""
import re
from urllib.parse import urlparse, quote
from playwright.sync_api import sync_playwright

EW_RECIPE = re.compile(r"^/recipe/\d+/", re.I)

# Broad savory category terms -> EatingWell search (proven harvest surface).
SAVORY_QUERIES = [
    "chicken dinner", "soup", "salad", "pasta", "vegetarian dinner", "sheet pan dinner",
    "mediterranean", "casserole", "stir fry", "beef dinner", "fish dinner", "rice bowl",
    "stew", "roasted vegetables", "tofu", "lentil", "curry", "one pot",
]
SEARCH = [f"https://www.eatingwell.com/search/?q={quote(q)}" for q in SAVORY_QUERIES]
# Hub/category guesses (may yield 0 if index-only or JS-rendered).
HUBS = [
    "https://www.eatingwell.com/recipes/",
    "https://www.eatingwell.com/category/4286/dinner-recipes/",
    "https://www.eatingwell.com/healthy-recipes/",
]


def recipe_count(page, url: str) -> int:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(2800)
        hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))") or []
        return len({urlparse(h).path for h in hrefs if h and EW_RECIPE.match(urlparse(h).path)})
    except Exception:  # noqa: BLE001
        return -1


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("=== SAVORY SEARCH SURFACES ===")
        for url in SEARCH:
            n = recipe_count(page, url)
            results.append((n, url))
            print(f"   {n:>4}  {url}")
        print("\n=== HUB/CATEGORY GUESSES ===")
        for url in HUBS:
            n = recipe_count(page, url)
            results.append((n, url))
            print(f"   {n:>4}  {url}")
        browser.close()

    working = sorted([(n, u) for n, u in results if n > 0], reverse=True)
    print("\n" + "=" * 70)
    print(f"WORKING EATINGWELL SURFACES: {len(working)}  (~{sum(n for n,_ in working)} recipe-URL slots)")
    print("=" * 70)
    for n, u in working:
        print(f"   {n:>4}  {u}")
    print("\nJSON listing_urls seed:")
    print("[" + ",".join(f'\n  \"{u}\"' for _, u in working) + "\n]")


if __name__ == "__main__":
    main()
