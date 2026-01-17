#!/usr/bin/env python3
"""
Recipe Image Scraper using Playwright
Scrapes recipe images from URLs in recipes.json and downloads them locally.
"""

import json
import os
import requests
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin, urlparse
import hashlib

def scrape_image_urls(url, timeout=30000):
    """
    Extract image URLs from a recipe page using Playwright.
    Returns list of image URLs found on the page.
    """
    print(f"🔍 Scraping images from: {url}")
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Set timeout and navigate
            page.set_default_timeout(timeout)
            page.goto(url, wait_until="domcontentloaded")
            
            # Wait a bit for images to load
            page.wait_for_timeout(2000)
            
            # Extract image URLs - focus on likely recipe images
            image_urls = page.eval_on_selector_all(
                "img",
                """elements => elements
                    .map(el => el.src)
                    .filter(src => src && !src.includes('data:'))
                    .filter(src => {
                        const lower = src.toLowerCase();
                        // Filter out obvious non-recipe images
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
            print(f"✅ Found {len(image_urls)} potential recipe images")
            return image_urls
            
        except Exception as e:
            print(f"❌ Error scraping {url}: {e}")
            if 'browser' in locals():
                browser.close()
            return []

def download_image(url, filepath, timeout=10):
    """
    Download an image from URL to filepath.
    Returns True if successful, False otherwise.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        response = requests.get(url, timeout=timeout, headers=headers, stream=True)
        response.raise_for_status()
        
        # Check if it's actually an image
        content_type = response.headers.get('content-type', '').lower()
        if not any(img_type in content_type for img_type in ['image/', 'jpeg', 'jpg', 'png']):
            print(f"⚠️  Not an image: {content_type}")
            return False
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Download the image
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Verify file was created and has content
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:  # At least 1KB
            print(f"✅ Downloaded: {os.path.basename(filepath)} ({os.path.getsize(filepath)} bytes)")
            return True
        else:
            print(f"❌ Download failed or file too small: {filepath}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return False
            
    except Exception as e:
        print(f"❌ Download error for {url}: {e}")
        return False

def find_best_recipe_image(image_urls, recipe_name):
    """
    Find the best image URL for a recipe based on size and relevance.
    Returns the best image URL or None.
    """
    if not image_urls:
        return None
    
    # Score images based on various criteria
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
    
    # Return the highest scoring image
    best_score, best_url = max(scored_urls, key=lambda x: x[0])
    print(f"🎯 Best image (score {best_score}): {best_url}")
    return best_url

def scrape_recipe_images(recipes_json_path, max_recipes=None):
    """
    Main function to scrape images for all recipes in the JSON file.
    """
    # Load recipes
    with open(recipes_json_path, 'r') as f:
        recipes = json.load(f)
    
    print(f"📋 Found {len(recipes)} recipes to process")
    
    successful_downloads = 0
    failed_downloads = []
    
    recipe_items = list(recipes.items())
    if max_recipes:
        recipe_items = recipe_items[:max_recipes]
    
    for recipe_name, recipe_data in recipe_items:
        print(f"\n🍝 Processing: {recipe_name}")
        
        url = recipe_data['url']
        expected_image_path = recipe_data['image_path']
        
        # Check if image already exists and is valid
        if os.path.exists(expected_image_path) and os.path.getsize(expected_image_path) > 1000:
            print(f"✅ Image already exists: {expected_image_path}")
            successful_downloads += 1
            continue
        
        # Scrape image URLs from the recipe page
        image_urls = scrape_image_urls(url)
        
        if not image_urls:
            print(f"❌ No images found for {recipe_name}")
            failed_downloads.append(recipe_name)
            continue
        
        # Find the best image for this recipe
        best_image_url = find_best_recipe_image(image_urls, recipe_name)
        
        if not best_image_url:
            print(f"❌ No suitable image found for {recipe_name}")
            failed_downloads.append(recipe_name)
            continue
        
        # Download the image
        if download_image(best_image_url, expected_image_path):
            successful_downloads += 1
        else:
            failed_downloads.append(recipe_name)
        
        # Be nice to servers
        time.sleep(1)
    
    # Report results
    print(f"\n📊 Scraping Results:")
    print(f"✅ Successful downloads: {successful_downloads}")
    print(f"❌ Failed downloads: {len(failed_downloads)}")
    
    if failed_downloads:
        print(f"Failed recipes: {', '.join(failed_downloads)}")
    
    return successful_downloads, failed_downloads

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape recipe images using Playwright')
    parser.add_argument('--recipes-json', default='cuisines/italian/recipes.json', 
                       help='Path to recipes JSON file')
    parser.add_argument('--max-recipes', type=int, 
                       help='Maximum number of recipes to process (for testing)')
    parser.add_argument('--test', action='store_true',
                       help='Test mode: only process first 3 recipes')
    
    args = parser.parse_args()
    
    if args.test:
        args.max_recipes = 3
    
    if not os.path.exists(args.recipes_json):
        print(f"❌ Recipes file not found: {args.recipes_json}")
        exit(1)
    
    print(f"🚀 Starting recipe image scraping...")
    scrape_recipe_images(args.recipes_json, args.max_recipes)