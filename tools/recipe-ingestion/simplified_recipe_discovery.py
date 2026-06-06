#!/usr/bin/env python3
"""
Simplified Recipe URL Discovery
Reads dish names from txt files, discovers recipe URLs from sites, outputs clean JSON
No image scraping - just URL discovery for the enhanced batch processor
"""

import json
import os
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse
from typing import List, Dict, Optional

# Per-site patterns matching a *recipe page* path (not category/search/collection
# pages). Sites use different conventions: AllRecipes uses /recipe/<id>/ (singular)
# while FoodNetwork/BBC/Epicurious use /recipes/ (plural) with distinct shapes.
RECIPE_URL_PATTERNS = {
    "allrecipes.com": re.compile(r"^/recipe/\d+/", re.I),
    "foodnetwork.com": re.compile(r"^/recipes/.+-\d{3,}/?$", re.I),
    "bbcgoodfood.com": re.compile(r"^/recipes/[a-z0-9][a-z0-9-]+/?$", re.I),
    "epicurious.com": re.compile(r"^/recipes/food/views/[a-z0-9][a-z0-9-]+/?$", re.I),
}
# Generic fallback for sites without an explicit pattern.
_FALLBACK_PATTERN = re.compile(r"/recipe/|/recipes/[a-z0-9-]+", re.I)
# Path segments that indicate an index/collection/listing page, never a recipe.
_EXCLUDE_SEGMENTS = {
    "search", "collection", "collections", "category", "categories", "cuisine",
    "cuisines", "course", "courses", "howto", "how-to", "budget", "health",
    "occasion", "tag", "tags", "author", "authors", "photos", "packages",
    "videos", "video", "articles", "reviews", "gallery", "a-z", "ingredients",
}

class SimplifiedRecipeDiscovery:
    def __init__(self, sites_config_path="src/mcp_servers/recipe_discovery_mcp/config/sites.json"):
        self.sites_config_path = sites_config_path
        self.sites = self.load_sites_config()
        
    def load_sites_config(self) -> Dict:
        """Load the sites configuration"""
        if not os.path.exists(self.sites_config_path):
            print(f"❌ Sites config not found: {self.sites_config_path}")
            # Fallback to basic config
            return {
                "allrecipes.com": {
                    "name": "AllRecipes",
                    "base_url": "https://www.allrecipes.com",
                    "search_paths": ["/search?q={query}"],
                    "enabled": True,
                    "priority": "high",
                    "rate_limit": 2.0
                },
                "foodnetwork.com": {
                    "name": "Food Network", 
                    "base_url": "https://www.foodnetwork.com",
                    "search_paths": ["/search/{query}-"],
                    "enabled": True,
                    "priority": "medium",
                    "rate_limit": 2.0
                }
            }
        
        with open(self.sites_config_path, 'r') as f:
            config = json.load(f)
        return config.get('sites', {})
    
    def get_search_url(self, site_domain: str, query: str) -> Optional[str]:
        """Generate search URL for a site and query"""
        if site_domain not in self.sites:
            return None
            
        site_config = self.sites[site_domain]
        if not site_config.get('enabled', True):
            return None
            
        base_url = site_config['base_url']
        search_paths = site_config['search_paths']
        
        # Use the first search path
        search_path = search_paths[0].format(query=query.replace(' ', '+'))
        return f"{base_url}{search_path}"
    
    def extract_recipe_urls_from_search(self, search_url: str, site_domain: str) -> List[str]:
        """Extract recipe URLs from search results page using Playwright"""
        print(f"  🔍 Searching: {search_url}")
        
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Set timeout and navigate
                page.set_default_timeout(30000)
                page.goto(search_url, wait_until="domcontentloaded")
                
                # Wait for search results to load
                page.wait_for_timeout(3000)
                
                # Grab every link on the page; filter in Python with per-site patterns.
                all_hrefs = page.eval_on_selector_all(
                    "a[href]", "elements => elements.map(el => el.href)"
                )
                browser.close()

                base_domain = urlparse(search_url).netloc
                site_pattern = RECIPE_URL_PATTERNS.get(site_domain, _FALLBACK_PATTERN)

                recipe_urls = []
                for url in all_hrefs:
                    if not url or not url.startswith("http"):
                        continue
                    parsed = urlparse(url)
                    # Same site only (allow www / bare-domain variants)
                    if parsed.netloc.replace("www.", "") != base_domain.replace("www.", ""):
                        continue
                    path = parsed.path
                    # Skip index/collection/listing pages
                    if any(seg in _EXCLUDE_SEGMENTS for seg in path.lower().split("/")):
                        continue
                    # Must match this site's recipe-page shape
                    if not site_pattern.search(path):
                        continue
                    recipe_urls.append(url.split("?")[0])  # drop query/tracking params

                unique_urls = list(dict.fromkeys(recipe_urls))
                print(f"  ✅ Found {len(unique_urls)} recipe URLs")
                return unique_urls[:3]  # Return first 3 unique URLs
                
            except Exception as e:
                print(f"  ❌ Error extracting URLs from {search_url}: {e}")
                if 'browser' in locals():
                    browser.close()
                return []
    
    def find_recipe_url(self, dish_name: str) -> Optional[str]:
        """Find a recipe URL by searching through configured sites"""
        print(f"\n🍽️  Searching for: {dish_name}")
        
        # Sort sites by priority
        sorted_sites = sorted(
            self.sites.items(),
            key=lambda x: {'high': 1, 'medium': 2, 'low': 3}.get(x[1].get('priority', 'medium'), 2)
        )
        
        for site_domain, site_config in sorted_sites:
            if not site_config.get('enabled', True):
                continue
                
            print(f"  📍 Trying: {site_config['name']}")
            
            # Generate search URL
            search_url = self.get_search_url(site_domain, dish_name)
            if not search_url:
                continue
            
            # Extract recipe URLs from search results
            recipe_urls = self.extract_recipe_urls_from_search(search_url, site_domain)
            
            if recipe_urls:
                best_url = recipe_urls[0]  # Take the first (most relevant) result
                print(f"  ✅ Found recipe: {best_url}")
                return best_url
            
            # Rate limiting between sites
            time.sleep(site_config.get('rate_limit', 1.0))
        
        print(f"  ❌ No recipe found for: {dish_name}")
        return None
    
    def discover_urls_for_cuisine(self, dish_file_path: str, cuisine_name: str, 
                                 max_dishes: Optional[int] = None) -> Dict[str, str]:
        """
        Discover URLs for all dishes in a cuisine file
        
        Args:
            dish_file_path: Path to dish-names.txt file
            cuisine_name: Name of cuisine (for logging)
            max_dishes: Maximum dishes to process (for testing)
            
        Returns:
            Dict mapping dish names to recipe URLs
        """
        print(f"🚀 Discovering URLs for cuisine: {cuisine_name}")
        print(f"📋 Reading dishes from: {dish_file_path}")
        
        # Read dish names
        with open(dish_file_path, 'r') as f:
            dish_names = [line.strip() for line in f if line.strip()]
        
        if max_dishes:
            dish_names = dish_names[:max_dishes]
            print(f"🧪 Test mode: Processing first {max_dishes} dishes")
        
        print(f"📊 Found {len(dish_names)} dishes to process")
        
        discovered_urls = {}
        successful_discoveries = 0
        failed_discoveries = []
        
        for i, dish_name in enumerate(dish_names, 1):
            print(f"\n{'='*60}")
            print(f"🔄 Processing {i}/{len(dish_names)}: {dish_name}")
            
            # Find recipe URL
            recipe_url = self.find_recipe_url(dish_name)
            
            if recipe_url:
                discovered_urls[dish_name] = recipe_url
                successful_discoveries += 1
                print(f"  ✅ Success: {dish_name}")
            else:
                failed_discoveries.append(dish_name)
                print(f"  ❌ Failed: {dish_name}")
            
            # Be nice to servers
            time.sleep(1)
        
        # Final report
        print(f"\n{'='*60}")
        print(f"📊 URL Discovery Results for {cuisine_name}:")
        print(f"✅ Successful discoveries: {successful_discoveries}")
        print(f"❌ Failed discoveries: {len(failed_discoveries)}")
        
        if failed_discoveries:
            print(f"Failed dishes: {', '.join(failed_discoveries[:5])}...")
        
        return discovered_urls
    
    def save_discovered_urls(self, discovered_urls: Dict[str, str], cuisine_name: str, 
                           output_dir: str = "./discovered-urls") -> str:
        """
        Save discovered URLs to JSON file for enhanced batch processor
        
        Args:
            discovered_urls: Dict mapping dish names to URLs
            cuisine_name: Name of cuisine
            output_dir: Directory to save results
            
        Returns:
            Path to saved JSON file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Create simple JSON format for enhanced batch processor
        simple_json = {}
        for dish_name, url in discovered_urls.items():
            simple_json[dish_name] = {"url": url}
        
        # Save to file
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        json_filename = f"{cuisine_name}_discovered_recipes_{timestamp}.json"
        json_path = os.path.join(output_dir, json_filename)
        
        with open(json_path, 'w') as f:
            json.dump(simple_json, f, indent=2)
        
        print(f"\n💾 Discovered URLs saved: {json_path}")
        print(f"📋 Format: {len(simple_json)} recipes ready for enhanced batch processor")
        
        return json_path

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Discover recipe URLs from dish names')
    parser.add_argument('--cuisine', required=True, 
                       help='Cuisine name (e.g., italian, thai, mexican, american)')
    parser.add_argument('--dish-file', 
                       help='Path to dish names file (default: cuisines/{cuisine}/dish-names.txt)')
    parser.add_argument('--max-dishes', type=int,
                       help='Maximum number of dishes to process (for testing)')
    parser.add_argument('--test', action='store_true',
                       help='Test mode: only process first 3 dishes')
    parser.add_argument('--output-dir', default='./discovered-urls',
                       help='Output directory for discovered URLs (default: ./discovered-urls)')
    
    args = parser.parse_args()
    
    if args.test:
        args.max_dishes = 3
    
    # Default dish file path
    if not args.dish_file:
        args.dish_file = f"cuisines/{args.cuisine}/dish-names.txt"
    
    if not os.path.exists(args.dish_file):
        print(f"❌ Dish file not found: {args.dish_file}")
        exit(1)
    
    print("🔍 SIMPLIFIED RECIPE URL DISCOVERY")
    print("="*50)
    
    # Create discovery pipeline
    discovery = SimplifiedRecipeDiscovery()
    
    # Discover URLs for the cuisine
    discovered_urls = discovery.discover_urls_for_cuisine(
        args.dish_file, args.cuisine, args.max_dishes
    )
    
    if discovered_urls:
        # Save results
        json_path = discovery.save_discovered_urls(discovered_urls, args.cuisine, args.output_dir)
        
        print(f"\n🎉 Discovery complete!")
        print(f"📊 Ready for enhanced batch processor:")
        print(f"    python3 enhanced_batch_processor.py {json_path}")
    else:
        print(f"\n❌ No URLs discovered for {args.cuisine}")

if __name__ == "__main__":
    main()