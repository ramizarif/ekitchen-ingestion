#!/usr/bin/env python3
"""
READ-ONLY: empirically test which Tasty listing endpoints actually return recipes, and how
many. Writes nothing, spends nothing. Output = a ranked list of working listing URLs to
seed harvest_ingest.py.
"""
import re
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

TASTY_RECIPE = re.compile(r"^/recipe/[a-z0-9][a-z0-9-]+/?$", re.I)

# Candidate /topic/<slug> meal-type + category feeds (Tasty's taxonomy is specific —
# /topic/dinner yields, /topic/chicken did not, so test empirically).
TOPICS = [
    "dinner", "lunch", "breakfast", "brunch", "dessert", "desserts", "drinks",
    "appetizers", "snacks", "sides", "side-dish", "salads", "soups", "pasta",
    "pizza", "bbq", "grilling", "vegetarian", "vegan", "seafood", "healthy",
    "comfort-food", "kid-friendly", "baking", "breads", "holiday", "party",
    "quick-easy", "one-pot", "meal-prep", "slow-cooker", "air-fryer", "cookies",
    "cakes", "sandwiches", "tacos", "noodles", "vegetables",
]
EXTRA = [
    "https://tasty.co/latest",
    "https://tasty.co/compilation/4-romantic-dinners-for-date-night",
]


def recipe_urls_on(page, url: str) -> int:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(2500)
        hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))") or []
        return len({urlparse(h).path for h in hrefs if h and TASTY_RECIPE.match(urlparse(h).path)})
    except Exception:  # noqa: BLE001
        return -1


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for slug in TOPICS:
            url = f"https://tasty.co/topic/{slug}"
            n = recipe_urls_on(page, url)
            results.append((n, url))
            print(f"   {n:>4}  {url}")
        for url in EXTRA:
            n = recipe_urls_on(page, url)
            results.append((n, url))
            print(f"   {n:>4}  {url}")
        browser.close()

    working = sorted([(n, u) for n, u in results if n > 0], reverse=True)
    print("\n" + "=" * 70)
    print(f"WORKING LISTING ENDPOINTS: {len(working)}  (total recipe-URL slots ~{sum(n for n,_ in working)})")
    print("=" * 70)
    for n, u in working:
        print(f"   {n:>4}  {u}")
    print("\nJSON listing_urls seed:")
    print("[" + ", ".join(f'\n  \"{u}\"' for _, u in working) + "\n]")


if __name__ == "__main__":
    main()
