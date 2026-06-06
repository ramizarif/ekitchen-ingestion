#!/usr/bin/env python3
"""
Harvest probe (READ-ONLY): validate the "browse the site for popular/trending recipes"
approach. Points the existing PlaywrightRecipeExtractor at Tasty/EatingWell *listing*
pages (topic / trending / category) instead of search pages, and reports how many real
recipe URLs each page yields.

Writes NOTHING to the backend and spends NO OpenAI money — it only scrapes public
listing pages. If yield is good, the same harvested URLs feed straight into
DirectRecipeProcessor.process_recipe_autonomous(url) for ingestion.

Usage:
    ../../venv/bin/python -u harvest_probe.py
"""
import sys
from pathlib import Path
from urllib.parse import urlparse

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT / "legacy/src/discovery"))
from playwright_url_extractor import PlaywrightRecipeExtractor  # noqa: E402

# Listing / browse / topic pages that aggregate popular recipes (NOT search pages).
LISTING_URLS = [
    # Tasty topic feeds (predictable /topic/<slug> structure)
    "https://tasty.co/topic/dinner",
    "https://tasty.co/topic/chicken",
    "https://tasty.co/topic/easy",
    "https://tasty.co/topic/dessert",
    "https://tasty.co/latest",
    # EatingWell category/listing pages (Mediterranean/healthy strength)
    "https://www.eatingwell.com/recipes/",
    "https://www.eatingwell.com/category/4286/dinner-recipes/",
    "https://www.eatingwell.com/category/4305/mediterranean-diet-recipes/",
]

MAX_PER_PAGE = 60


def main() -> None:
    extractor = PlaywrightRecipeExtractor()
    all_urls = set()
    print(f"\n{'='*70}\nHARVEST PROBE — {len(LISTING_URLS)} listing pages\n{'='*70}")
    rows = []
    for url in LISTING_URLS:
        try:
            urls = extractor.extract_recipe_urls_from_search_page(url, MAX_PER_PAGE)
        except Exception as e:  # noqa: BLE001
            print(f"   ERROR on {url}: {str(e)[:80]}")
            urls = []
        uniq = sorted(set(urls))
        all_urls.update(uniq)
        rows.append((url, len(uniq)))
        print(f"\n>>> {url}\n    harvested {len(uniq)} recipe URLs")
        for u in uniq[:5]:
            print(f"      - {u}")

    print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    for url, n in rows:
        host = urlparse(url).netloc.replace("www.", "")
        print(f"   {n:4d}  {host:18} {url}")
    print(f"   {'-'*60}")
    print(f"   {len(all_urls):4d}  UNIQUE recipe URLs across all listing pages")


if __name__ == "__main__":
    main()
