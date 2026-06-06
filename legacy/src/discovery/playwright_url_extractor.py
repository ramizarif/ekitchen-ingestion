#!/usr/bin/env python3
"""
Playwright URL Extractor for Recipe Search Pages
Uses Playwright browser automation for intelligent URL extraction from search results
"""

import sys
import os
import json
import re
import time
from typing import List, Optional, Dict
from urllib.parse import urlparse, urljoin

# Per-site patterns matching an INDIVIDUAL recipe-page path (not category/index
# pages). Sites mix conventions — e.g. EatingWell uses /recipe/<id>/ for recipes
# but /recipes/<id>/<category>/ for listings — so a single generic regex isn't
# enough; match each verified site explicitly.
_SITE_RECIPE_PATTERNS = {
    "tasty.co": re.compile(r"^/recipe/[a-z0-9][a-z0-9-]+/?$", re.I),
    "simplyrecipes.com": re.compile(r"^/recipes/[a-z0-9][a-z0-9_-]+/?$", re.I),
    "eatingwell.com": re.compile(r"^/recipe/\d+/", re.I),
    "allrecipes.com": re.compile(r"^/recipe/\d+/", re.I),
    "foodnetwork.com": re.compile(r"^/recipes/.+-\d{3,}/?$", re.I),
    "bbcgoodfood.com": re.compile(r"^/recipes/[a-z0-9][a-z0-9-]+/?$", re.I),
    "epicurious.com": re.compile(r"^/recipes/food/views/[a-z0-9][a-z0-9-]+/?$", re.I),
}
# Generic fallback for sites without an explicit pattern (best-effort).
_RECIPE_PATH = re.compile(r"(^|/)recipe/[a-z0-9]|/recipes/[a-z0-9][a-z0-9_-]{2,}", re.I)
# Path segments that signal an index/listing page, never an individual recipe.
# NOTE: never include 'recipe'/'recipes'/'food'/'views' here — they are part of
# legitimate recipe paths.
_EXCLUDE_SEGMENTS = {
    "search", "collection", "collections", "category", "categories", "cuisine",
    "cuisines", "course", "courses", "howto", "how-to", "occasion", "tag", "tags",
    "author", "authors", "photos", "packages", "videos", "video", "articles",
    "reviews", "gallery", "a-z", "ingredients", "page", "latest", "trending",
    "popular", "profile", "login", "register", "breakfast", "lunch", "dinner",
    "dessert", "desserts", "appetizer", "appetizers", "snacks", "drinks",
    "mains", "sides",
}
_BAD_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif", ".pdf", ".zip")


class PlaywrightRecipeExtractor:
    """Extract recipe URLs from search pages using Playwright browser automation"""
    
    def __init__(self):
        self.extracted_urls_cache = {}
    
    def extract_recipe_urls_from_search_page(self, search_url: str, max_urls: int = 10) -> List[str]:
        """
        Extract recipe URLs from a search results page
        
        Args:
            search_url: URL of the search results page
            max_urls: Maximum number of URLs to extract
            
        Returns:
            List of recipe URLs found on the page
        """
        try:
            print(f"🔍 Extracting recipe URLs from: {search_url}")
            print(f"🎯 Target: {max_urls} URLs")
            
            # Parse domain from URL
            parsed_url = urlparse(search_url)
            domain = parsed_url.netloc.replace('www.', '')
            
            print(f"🌐 Domain: {domain}")
            
            # Use Playwright extraction
            return self._playwright_extract(search_url, max_urls)
            
        except Exception as e:
            print(f"❌ URL extraction failed: {e}")
            return []
    
    
    def _playwright_extract(self, search_url: str, max_urls: int) -> List[str]:
        """Playwright-based URL extraction from search results"""
        try:
            # Import playwright
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                print("❌ Playwright not installed. Run: pip install playwright && playwright install")
                return []
            
            print(f"🎭 Starting Playwright URL extraction...")
            
            recipe_urls = []
            
            with sync_playwright() as p:
                # Launch browser with more permissive settings
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-extensions'
                    ]
                )
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    java_script_enabled=True
                )
                page = context.new_page()
                
                # Navigate using the same method as the working script
                print(f"📄 Loading search page...")
                
                # Set timeout and navigate (same as working script)
                page.set_default_timeout(30000)
                page.goto(search_url, wait_until="domcontentloaded")
                
                # Wait for search results to load (same as working script)
                print(f"⏳ Waiting for search results to load...")
                page.wait_for_timeout(3000)
                
                # Check if page loaded successfully
                try:
                    title = page.title()
                    print(f"📄 Page title: {title[:50]}...")
                except Exception:
                    print(f"⚠️  Could not get page title")
                
                # Grab every link on the page (plain JS, no filtering), then filter
                # in Python with per-site-agnostic recipe patterns. This handles both
                # singular '/recipe/' (Tasty, EatingWell) and plural '/recipes/<slug>'
                # (SimplyRecipes, BBC, Epicurious) URL conventions.
                print(f"🔗 Extracting recipe URLs...")
                try:
                    all_hrefs = page.eval_on_selector_all(
                        "a[href]", "elements => elements.map(el => el.href)"
                    )
                    recipe_urls = self._filter_recipe_urls(all_hrefs, search_url, max_urls)
                    print(f"✅ Extraction found {len(recipe_urls)} recipe URLs")
                    for i, url in enumerate(recipe_urls[:5]):
                        print(f"  {i+1}. {url}")
                    if len(recipe_urls) > 5:
                        print(f"  ... and {len(recipe_urls) - 5} more")
                except Exception as e:
                    print(f"❌ Extraction failed: {e}")

                if len(recipe_urls) == 0:
                    print(f"⚠️  No recipe URLs found - trying debug screenshot...")
                    try:
                        page.screenshot(path="debug_no_urls_screenshot.png")
                        print(f"📸 Debug screenshot saved as debug_no_urls_screenshot.png")
                    except Exception:
                        pass
                
                browser.close()
            
            print(f"🎭 Playwright extraction found {len(recipe_urls)} recipe URLs")
            return recipe_urls
            
        except Exception as e:
            print(f"❌ Playwright extraction failed: {e}")
            return []
    
    def _filter_recipe_urls(self, hrefs: List[str], search_url: str, max_urls: int) -> List[str]:
        """Filter a flat list of hrefs down to same-site individual recipe pages."""
        base = urlparse(search_url).netloc.replace("www.", "")
        pattern = _SITE_RECIPE_PATTERNS.get(base, _RECIPE_PATH)
        out: List[str] = []
        for h in hrefs:
            if not h or not h.startswith("http"):
                continue
            parsed = urlparse(h)
            if parsed.netloc.replace("www.", "") != base:
                continue
            path = parsed.path
            segs = {s for s in path.lower().strip("/").split("/") if s}
            if segs & _EXCLUDE_SEGMENTS:
                continue
            if not pattern.search(path):
                continue
            if h.lower().split("?")[0].endswith(_BAD_SUFFIXES):
                continue
            out.append(h.split("?")[0])  # strip query/tracking params
        # de-duplicate, preserve order
        seen, uniq = set(), []
        for u in out:
            if u not in seen:
                seen.add(u)
                uniq.append(u)
        return uniq[:max_urls]

    def _looks_like_recipe_url(self, url: str, base_domain: str) -> bool:
        """Heuristic to determine if a URL looks like a recipe page"""
        try:
            parsed = urlparse(url)
            
            # Must be from the same domain
            if base_domain not in parsed.netloc:
                return False
            
            # Skip obvious non-recipe URLs
            skip_patterns = [
                '/search', '/category', '/tag', '/author', '/page',
                '/login', '/register', '/profile', '/cart', '/checkout',
                '/about', '/contact', '/privacy', '/terms',
                'facebook.com', 'twitter.com', 'instagram.com',
                'pinterest.com', 'youtube.com', 'tiktok.com',
                '.jpg', '.png', '.gif', '.pdf', '.zip'
            ]
            
            url_lower = url.lower()
            if any(pattern in url_lower for pattern in skip_patterns):
                return False
            
            # Look for positive indicators
            recipe_indicators = [
                '/recipe', '/recipes', '/dish', '/food',
                'recipe-', '-recipe', 'recipe_', '_recipe'
            ]
            
            if any(indicator in url_lower for indicator in recipe_indicators):
                return True
            
            # Check path structure - many recipe sites use /some-recipe-name pattern
            path = parsed.path
            if path and path.count('/') <= 3 and len(path) > 10:
                # Looks like it could be a recipe URL
                return True
            
            return False
            
        except Exception:
            return False
    
    def extract_from_multiple_searches(self, url_template: str, queries: List[str], per_query: int = 5) -> Dict[str, List[str]]:
        """
        Extract URLs from multiple search queries using a URL template
        
        Args:
            url_template: URL template with {query} placeholder
            queries: List of search queries
            per_query: Number of URLs to extract per query
            
        Returns:
            Dictionary mapping queries to their extracted URLs
        """
        results = {}
        
        print(f"🎲 Multi-query extraction starting...")
        print(f"   Template: {url_template}")
        print(f"   Queries: {queries}")
        print(f"   Per Query: {per_query}")
        
        for i, query in enumerate(queries, 1):
            print(f"\n🔍 Processing query {i}/{len(queries)}: '{query}'")
            
            try:
                # Generate search URL
                formatted_query = query.replace(' ', '+')
                search_url = url_template.format(query=formatted_query)
                
                print(f"🌐 Search URL: {search_url}")
                
                # Extract URLs for this query
                urls = self.extract_recipe_urls_from_search_page(search_url, per_query)
                results[query] = urls
                
                if urls:
                    print(f"✅ Found {len(urls)} URLs for '{query}'")
                else:
                    print(f"❌ No URLs found for '{query}'")
                
                # Brief pause between queries to be respectful
                if i < len(queries):
                    time.sleep(2)
                    
            except Exception as e:
                print(f"❌ Error processing query '{query}': {e}")
                results[query] = []
        
        total_urls = sum(len(urls) for urls in results.values())
        print(f"\n🎯 Multi-query extraction complete: {total_urls} total URLs from {len(queries)} queries")
        
        return results

def main():
    """Test the URL extractor"""
    extractor = PlaywrightRecipeExtractor()
    
    # Test single search extraction
    test_url = "https://www.allrecipes.com/search/?q=chicken"
    urls = extractor.extract_recipe_urls_from_search_page(test_url, 5)
    
    print(f"\n🧪 Test Results:")
    print(f"   Search URL: {test_url}")
    print(f"   URLs found: {len(urls)}")
    for i, url in enumerate(urls, 1):
        print(f"     {i}. {url}")

if __name__ == "__main__":
    main()