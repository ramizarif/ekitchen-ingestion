#!/usr/bin/env python3
"""
Recipe Discovery and Image Scraping Pipeline
Reads dish names from txt files, discovers recipes from sites.json, and scrapes images.
"""

import json
import os
import requests
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin, urlparse
import re
from typing import List, Dict, Optional, Tuple

class RecipeDiscoveryPipeline:
    def __init__(self, sites_config_path="recipe_discovery_mcp/config/sites.json"):
        self.sites_config_path = sites_config_path
        self.sites = self.load_sites_config()
        
    def load_sites_config(self) -> Dict:
        """Load the sites configuration"""
        with open(self.sites_config_path, 'r') as f:
            config = json.load(f)
        return config['sites']
    
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
        print(f"🔍 Searching: {search_url}")
        
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Set timeout and navigate
                page.set_default_timeout(30000)
                page.goto(search_url, wait_until="domcontentloaded")
                
                # Wait for search results to load
                page.wait_for_timeout(3000)
                
                # Get site config for URL patterns
                site_config = self.sites[site_domain]
                recipe_patterns = site_config.get('recipe_url_patterns', ['/recipe/.*', '/recipes/.*'])
                
                # Extract recipe links with more context for better filtering
                recipe_links = page.eval_on_selector_all(
                    "a[href]",
                    """elements => elements
                        .filter(el => {
                            const href = el.href;
                            if (!href || !href.startsWith('http')) return false;
                            
                            // Look for recipe-specific indicators
                            const text = el.textContent?.toLowerCase() || '';
                            const title = el.title?.toLowerCase() || '';
                            const href_lower = href.toLowerCase();
                            
                            // Must contain recipe indicators
                            return href_lower.includes('/recipe/') && 
                                   (text.includes('recipe') || 
                                    text.includes('view') || 
                                    text.includes('see') ||
                                    title.includes('recipe') ||
                                    href_lower.match(/\\/recipe\\/\\d+\\//));
                        })
                        .map(el => el.href)"""
                )
                
                browser.close()
                
                # The JavaScript already filtered, so just clean up
                recipe_urls = []
                base_domain = urlparse(search_url).netloc
                
                for url in recipe_links:
                    parsed_url = urlparse(url)
                    
                    # Must be from the same domain
                    if parsed_url.netloc != base_domain:
                        continue
                    
                    recipe_urls.append(url)
                
                # Remove duplicates and return first few
                unique_urls = list(dict.fromkeys(recipe_urls))
                print(f"✅ Found {len(unique_urls)} recipe URLs")
                return unique_urls[:5]  # Return first 5 unique URLs
                
            except Exception as e:
                print(f"❌ Error extracting URLs from {search_url}: {e}")
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
    
    def scrape_image_urls(self, url: str, timeout=30000) -> List[str]:
        """Extract image URLs from a recipe page using Playwright"""
        print(f"  🖼️  Scraping images from: {url}")
        
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                page.set_default_timeout(timeout)
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                
                # Extract image URLs - focus on likely recipe images
                image_urls = page.eval_on_selector_all(
                    "img",
                    """elements => elements
                        .map(el => el.src)
                        .filter(src => src && !src.includes('data:'))
                        .filter(src => {
                            const lower = src.toLowerCase();
                            return !lower.includes('logo') && 
                                   !lower.includes('avatar') && 
                                   !lower.includes('icon') &&
                                   !lower.includes('banner') &&
                                   !lower.includes('ad') &&
                                   !lower.includes('social') &&
                                   (lower.includes('recipe') || 
                                    lower.includes('food') || 
                                    lower.includes('cooking') ||
                                    src.includes('wp-content') ||
                                    src.includes('uploads') ||
                                    lower.includes('.jpg') || 
                                    lower.includes('.jpeg') || 
                                    lower.includes('.png'))
                        })"""
                )
                
                browser.close()
                print(f"  ✅ Found {len(image_urls)} potential recipe images")
                return image_urls
                
            except Exception as e:
                print(f"  ❌ Error scraping images from {url}: {e}")
                if 'browser' in locals():
                    browser.close()
                return []
    
    def score_and_sort_images(self, image_urls: List[str], recipe_name: str) -> List[Tuple[int, str]]:
        """Score and sort image URLs by relevance and quality"""
        if not image_urls:
            return []
        
        scored_urls = []
        recipe_words = recipe_name.lower().split()
        
        for url in image_urls:
            score = 0
            url_lower = url.lower()
            
            # Higher score for larger dimensions in URL
            if any(dim in url_lower for dim in ['1200', '1024', '800', '600']):
                score += 10
            elif any(dim in url_lower for dim in ['400', '300']):
                score += 5
            
            # Higher score for recipe-related keywords
            if any(word in url_lower for word in recipe_words):
                score += 15
            
            # Higher score for high-quality indicators
            if any(quality in url_lower for quality in ['hero', 'featured', 'main', 'primary']):
                score += 10
            
            # Lower score for thumbnails
            if any(thumb in url_lower for thumb in ['thumb', 'small', 'mini']):
                score -= 5
            
            # Prefer certain file types
            if url_lower.endswith(('.jpg', '.jpeg')):
                score += 3
            elif url_lower.endswith('.png'):
                score += 1
            
            scored_urls.append((score, url))
        
        # Sort by score (highest first)
        return sorted(scored_urls, key=lambda x: x[0], reverse=True)
    
    def log_successful_image_url(self, recipe_name: str, successful_url: str, score: int, cuisine_dir: str):
        """Log successful image URLs to notes.txt for pattern analysis"""
        notes_file = os.path.join(cuisine_dir, "notes.txt")
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {recipe_name} | Score: {score} | URL: {successful_url}\n"
        
        with open(notes_file, 'a') as f:
            f.write(log_entry)
    
    def download_best_available_image(self, image_urls: List[str], recipe_name: str, filepath: str, cuisine_dir: str) -> bool:
        """Try downloading images in order of quality score until one succeeds"""
        if not image_urls:
            print(f"  ❌ No images available for {recipe_name}")
            return False
        
        # Score and sort images
        scored_images = self.score_and_sort_images(image_urls, recipe_name)
        
        print(f"  🎯 Trying {len(scored_images)} images in order of quality...")
        
        for attempt, (score, url) in enumerate(scored_images, 1):
            print(f"    Attempt {attempt}: Score {score} - {url}")
            
            if self.download_image(url, filepath):
                print(f"  ✅ Successfully downloaded image on attempt {attempt}")
                # Log the successful URL for pattern analysis
                self.log_successful_image_url(recipe_name, url, score, cuisine_dir)
                return True
            else:
                print(f"    ❌ Attempt {attempt} failed, trying next...")
        
        print(f"  ❌ All {len(scored_images)} image downloads failed for {recipe_name}")
        return False
    
    def download_image(self, url: str, filepath: str, timeout=10) -> bool:
        """Download an image from URL to filepath"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(url, timeout=timeout, headers=headers, stream=True)
            response.raise_for_status()
            
            # Check if it's actually an image
            content_type = response.headers.get('content-type', '').lower()
            if not any(img_type in content_type for img_type in ['image/', 'jpeg', 'jpg', 'png']):
                print(f"  ⚠️  Not an image: {content_type}")
                return False
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Download the image
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verify file was created and has content
            if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
                print(f"  ✅ Downloaded: {os.path.basename(filepath)} ({os.path.getsize(filepath)} bytes)")
                return True
            else:
                print(f"  ❌ Download failed or file too small: {filepath}")
                if os.path.exists(filepath):
                    os.remove(filepath)
                return False
                
        except Exception as e:
            print(f"  ❌ Download error for {url}: {e}")
            return False
    
    def load_recipes_json(self, cuisine_path: str) -> Dict:
        """Load existing recipes.json or create empty dict"""
        recipes_file = os.path.join(cuisine_path, 'recipes.json')
        if os.path.exists(recipes_file):
            with open(recipes_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_recipes_json(self, cuisine_path: str, recipes: Dict):
        """Save recipes to recipes.json"""
        recipes_file = os.path.join(cuisine_path, 'recipes.json')
        os.makedirs(cuisine_path, exist_ok=True)
        
        with open(recipes_file, 'w') as f:
            json.dump(recipes, f, indent=2)
        
        print(f"  💾 Updated: {recipes_file}")
    
    def process_dish_file(self, dish_file_path: str, cuisine_name: str, max_dishes: Optional[int] = None, force_reprocess: bool = False):
        """Process a dish names file and discover recipes with images"""
        
        print(f"🚀 Processing cuisine: {cuisine_name}")
        print(f"📋 Reading dishes from: {dish_file_path}")
        
        # Read dish names
        with open(dish_file_path, 'r') as f:
            dish_names = [line.strip() for line in f if line.strip()]
        
        if max_dishes:
            dish_names = dish_names[:max_dishes]
        
        print(f"📊 Found {len(dish_names)} dishes to process")
        
        # Set up paths
        cuisine_dir = os.path.dirname(dish_file_path)
        images_dir = f"recipe-images/{cuisine_name}"
        
        # Load existing recipes
        recipes = self.load_recipes_json(cuisine_dir)
        
        successful_discoveries = 0
        failed_discoveries = []
        
        for dish_name in dish_names:
            print(f"\n{'='*60}")
            
            # Skip if already exists and has valid image (unless forcing reprocess)
            if dish_name in recipes and not force_reprocess:
                existing_image_path = recipes[dish_name].get('image_path', '')
                if os.path.exists(existing_image_path) and os.path.getsize(existing_image_path) > 1000:
                    print(f"⏭️  {dish_name}: Already exists with valid image")
                    continue
                else:
                    print(f"🔄 {dish_name}: Exists in JSON but missing/invalid image, re-processing...")
                    # Remove from recipes dict so it gets re-processed
                    del recipes[dish_name]
            elif dish_name in recipes and force_reprocess:
                print(f"🔄 {dish_name}: Force re-processing...")
                del recipes[dish_name]
            
            # Find recipe URL
            recipe_url = self.find_recipe_url(dish_name)
            if not recipe_url:
                failed_discoveries.append(dish_name)
                continue
            
            # Set up image path
            image_filename = dish_name.lower().replace(' ', '-').replace("'", '').replace('.', '') + '.jpg'
            image_path = f"{images_dir}/{image_filename}"
            
            # Scrape images from the recipe page
            image_urls = self.scrape_image_urls(recipe_url)
            
            # Try downloading images with fallback
            image_downloaded = self.download_best_available_image(image_urls, dish_name, image_path, cuisine_dir)
            
            # Add to recipes.json
            search_query = f"{dish_name} recipe food photo"
            recipes[dish_name] = {
                "url": recipe_url,
                "image_path": image_path,
                "search_query": search_query
            }
            
            if image_downloaded:
                print(f"  ✅ Complete: {dish_name} (URL + Image)")
                successful_discoveries += 1
            else:
                print(f"  ⚠️  Partial: {dish_name} (URL only, no image)")
                successful_discoveries += 1
            
            # Save progress after each dish
            self.save_recipes_json(cuisine_dir, recipes)
            
            # Be nice to servers
            time.sleep(2)
        
        # Final report
        print(f"\n{'='*60}")
        print(f"📊 Discovery Results for {cuisine_name}:")
        print(f"✅ Successful discoveries: {successful_discoveries}")
        print(f"❌ Failed discoveries: {len(failed_discoveries)}")
        
        if failed_discoveries:
            print(f"Failed dishes: {', '.join(failed_discoveries)}")
        
        return successful_discoveries, failed_discoveries

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Discover recipes and scrape images from dish names')
    parser.add_argument('--cuisine', required=True, 
                       help='Cuisine name (e.g., italian, thai, mexican)')
    parser.add_argument('--dish-file', 
                       help='Path to dish names file (default: cuisines/{cuisine}/dish-names.txt)')
    parser.add_argument('--max-dishes', type=int,
                       help='Maximum number of dishes to process (for testing)')
    parser.add_argument('--test', action='store_true',
                       help='Test mode: only process first 3 dishes')
    parser.add_argument('--force', action='store_true',
                       help='Force re-processing of existing recipes')
    
    args = parser.parse_args()
    
    if args.test:
        args.max_dishes = 3
    
    # Default dish file path
    if not args.dish_file:
        args.dish_file = f"cuisines/{args.cuisine}/dish-names.txt"
    
    if not os.path.exists(args.dish_file):
        print(f"❌ Dish file not found: {args.dish_file}")
        exit(1)
    
    # Create pipeline and process
    pipeline = RecipeDiscoveryPipeline()
    pipeline.process_dish_file(args.dish_file, args.cuisine, args.max_dishes, args.force)

if __name__ == "__main__":
    main()