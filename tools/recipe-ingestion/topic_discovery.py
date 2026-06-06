#!/usr/bin/env python3
"""
READ-ONLY discovery: find Tasty listing endpoints that return lots of recipes, and prove
that scroll-to-load multiplies per-page yield. Writes nothing, spends nothing.

Outputs:
  1. All /topic/<slug> and /compilation/<slug> listing URLs found in Tasty's rendered DOM
     (homepage + nav), which become seed listing_urls for harvest_ingest.
  2. A scroll-yield curve on /latest and /topic/dinner: how many unique /recipe/ URLs we
     get after 0,3,6,10 scrolls — quantifies the scroll lever.

Usage:
  ../../venv/bin/python -u topic_discovery.py
"""
import re
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

TASTY_RECIPE = re.compile(r"^/recipe/[a-z0-9][a-z0-9-]+/?$", re.I)
TASTY_LISTING = re.compile(r"^/(topic|compilation)/[a-z0-9][a-z0-9_-]+/?$", re.I)

SCROLL_PAGES = ["https://tasty.co/latest", "https://tasty.co/topic/dinner"]
SEED_PAGES = ["https://tasty.co/", "https://tasty.co/latest", "https://tasty.co/topic/dinner"]


def _hrefs(page):
    return page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))") or []


def discover_listing_urls(page) -> set:
    found = set()
    for url in SEED_PAGES:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            for _ in range(3):  # a few scrolls to surface lazy nav / cards
                page.mouse.wheel(0, 12000)
                page.wait_for_timeout(1200)
            for h in _hrefs(page):
                if not h:
                    continue
                path = urlparse(h).path
                if TASTY_LISTING.match(path) and "community" not in path:
                    found.add(f"https://tasty.co{path}")
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️  {url}: {str(e)[:70]}")
    return found


def scroll_yield(page, url: str, scroll_points=(0, 3, 6, 10)) -> dict:
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3000)
    curve, scrolls_done = {}, 0
    max_scroll = max(scroll_points)
    for target in scroll_points:
        while scrolls_done < target:
            page.mouse.wheel(0, 15000)
            page.wait_for_timeout(1500)
            scrolls_done += 1
        recs = set()
        for h in _hrefs(page):
            if h and TASTY_RECIPE.match(urlparse(h).path):
                recs.add(urlparse(h).path)
        curve[target] = len(recs)
    return curve


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("=" * 70)
        print("1) DISCOVERED TASTY LISTING ENDPOINTS (/topic, /compilation)")
        print("=" * 70)
        listings = sorted(discover_listing_urls(page))
        for u in listings:
            print(f"   {u}")
        print(f"   -> {len(listings)} listing endpoints discovered")

        print("\n" + "=" * 70)
        print("2) SCROLL-YIELD CURVE (unique /recipe/ URLs after N scrolls)")
        print("=" * 70)
        for url in SCROLL_PAGES:
            curve = scroll_yield(page, url)
            print(f"   {url}")
            print("   " + "  ".join(f"{k}scroll={v}" for k, v in curve.items()))

        browser.close()


if __name__ == "__main__":
    main()
