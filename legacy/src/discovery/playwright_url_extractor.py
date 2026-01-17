#!/usr/bin/env python3
"""
Playwright URL Extractor for Recipe Search Pages
Uses Playwright browser automation for intelligent URL extraction from search results
"""

import sys
import os
import json
import time
from typing import List, Optional, Dict
from urllib.parse import urlparse, urljoin


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
                
                # Extract recipe links with JavaScript filtering (more efficient and reliable)
                print(f"🔗 Extracting recipe URLs using JavaScript evaluation...")
                
                try:
                    recipe_links = page.eval_on_selector_all(
                        "a[href]",
f"""elements => elements
                            .filter(el => {{
                                const href = el.href;
                                if (!href || !href.startsWith('http')) return false;
                                
                                const text = el.textContent?.toLowerCase() || '';
                                const title = el.title?.toLowerCase() || '';
                                const href_lower = href.toLowerCase();
                                
                                // STRICT FILTERING: Must contain recipe indicators in URL
                                const hasRecipeInUrl = href_lower.includes('/recipe/') || 
                                                      href_lower.match(/\\/recipe\\/\\d+\\//);
                                
                                if (!hasRecipeInUrl) return false;
                                
                                // Additional validation for recipe content
                                const hasRecipeContent = text.includes('recipe') || 
                                                        text.includes('view') || 
                                                        text.length > 10 ||  // Recipe title links
                                                        title.includes('recipe');
                                
                                // Skip navigation, ads, social media links  
                                const skipPatterns = ['/search', '/category', '/tag', '/author', 
                                                    '/page', '/login', '/register', '/profile',
                                                    '/latest', '/trending', '/popular',
                                                    'facebook.', 'twitter.', 'instagram.',
                                                    'pinterest.', 'youtube.', 'tiktok.',
                                                    '.jpg', '.png', '.gif', '.pdf'];
                                
                                const shouldSkip = skipPatterns.some(pattern => 
                                    href_lower.includes(pattern));
                                
                                return !shouldSkip && hasRecipeContent;
                            }})
                            .map(el => el.href)
                            .slice(0, {max_urls})"""
                    )
                    
                    recipe_urls = recipe_links
                    print(f"✅ JavaScript extraction found {len(recipe_urls)} recipe URLs")
                    
                    for i, url in enumerate(recipe_urls[:5]):  # Show first 5
                        print(f"  {i+1}. {url}")
                    
                    if len(recipe_urls) > 5:
                        print(f"  ... and {len(recipe_urls) - 5} more")
                        
                except Exception as e:
                    print(f"❌ JavaScript extraction failed: {e}")
                    print(f"⚠️  Falling back to manual link extraction...")
                    
                    # Fallback to manual extraction
                    try:
                        links = page.query_selector_all('a[href]')
                        print(f"🔗 Found {len(links)} total links on page (fallback)")
                        
                        parsed_base = urlparse(search_url)
                        base_domain = parsed_base.netloc
                        
                        for link in links:
                            if len(recipe_urls) >= max_urls:
                                break
                                
                            try:
                                href = link.get_attribute('href')
                                if not href:
                                    continue
                                
                                # Convert relative URLs to absolute
                                if href.startswith('/'):
                                    href = urljoin(search_url, href)
                                elif not href.startswith('http'):
                                    continue
                                
                                # Check if it looks like a recipe URL
                                if self._looks_like_recipe_url(href, base_domain):
                                    recipe_urls.append(href)
                                    print(f"  ✅ Found recipe URL: {href}")
                            
                            except Exception as e:
                                continue  # Skip problematic links
                                
                    except Exception as e2:
                        print(f"❌ Fallback extraction also failed: {e2}")
                
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