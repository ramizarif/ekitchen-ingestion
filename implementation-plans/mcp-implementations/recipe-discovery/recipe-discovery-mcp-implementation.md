"""
Recipe Discovery MCP Server
Combines intelligent site search with recipe-scrapers extraction
"""

import asyncio
import json
import logging
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse, quote_plus
import httpx
from bs4 import BeautifulSoup
from recipe_scrapers import scrape_me
import random
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("RecipeDiscoveryServer")

# Site configurations for recipe discovery
RECIPE_SITES = {
    "allrecipes": {
        "base_url": "https://www.allrecipes.com",
        "search_url": "https://www.allrecipes.com/search?q={keyword}",
        "recipe_selector": "a[href*='/recipe/']",
        "pagination_selector": "a.mntl-pagination__next",
        "max_pages": 5
    },
    "foodnetwork": {
        "base_url": "https://www.foodnetwork.com",
        "search_url": "https://www.foodnetwork.com/search/{keyword}",
        "recipe_selector": "a[href*='/recipes/']",
        "pagination_selector": "a.o-Pagination__a-NextLink",
        "max_pages": 3
    },
    "bbcgoodfood": {
        "base_url": "https://www.bbcgoodfood.com",
        "search_url": "https://www.bbcgoodfood.com/search/recipes?q={keyword}",
        "recipe_selector": "a[href*='/recipes/']",
        "pagination_selector": "a.pagination-item--next",
        "max_pages": 4
    },
    "seriouseats": {
        "base_url": "https://www.seriouseats.com",
        "search_url": "https://www.seriouseats.com/search?q={keyword}",
        "recipe_selector": "a[href*='/recipes/']",
        "pagination_selector": "a.pagination__link--next",
        "max_pages": 3
    },
    "food52": {
        "base_url": "https://food52.com",
        "search_url": "https://food52.com/recipes/search?q={keyword}",
        "recipe_selector": "a[href*='/recipes/']",
        "pagination_selector": "a.pagination-next",
        "max_pages": 3
    }
}

class RecipeDiscovery:
    def __init__(self):
        self.session = None
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]
    
    async def get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session with rotating user agents"""
        if self.session is None:
            headers = {
                "User-Agent": random.choice(self.user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive"
            }
            self.session = httpx.AsyncClient(
                headers=headers,
                timeout=30.0,
                follow_redirects=True
            )
        return self.session
    
    async def search_site(self, site_name: str, keyword: str, max_results: int = 50) -> List[str]:
        """Search a specific site for recipe URLs"""
        if site_name not in RECIPE_SITES:
            logger.warning(f"Unknown site: {site_name}")
            return []
        
        site_config = RECIPE_SITES[site_name]
        session = await self.get_session()
        recipe_urls = set()
        
        try:
            # Format search URL
            search_url = site_config["search_url"].format(keyword=quote_plus(keyword))
            logger.info(f"Searching {site_name}: {search_url}")
            
            for page in range(1, site_config["max_pages"] + 1):
                if len(recipe_urls) >= max_results:
                    break
                
                # Add pagination if needed
                if page > 1:
                    if "?" in search_url:
                        page_url = f"{search_url}&page={page}"
                    else:
                        page_url = f"{search_url}?page={page}"
                else:
                    page_url = search_url
                
                try:
                    response = await session.get(page_url)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Find recipe links
                    recipe_links = soup.select(site_config["recipe_selector"])
                    
                    if not recipe_links:
                        logger.info(f"No more recipes found on {site_name} page {page}")
                        break
                    
                    for link in recipe_links:
                        href = link.get('href')
                        if href:
                            # Convert relative URLs to absolute
                            if href.startswith('/'):
                                full_url = urljoin(site_config["base_url"], href)
                            elif href.startswith('http'):
                                full_url = href
                            else:
                                continue
                            
                            recipe_urls.add(full_url)
                            
                            if len(recipe_urls) >= max_results:
                                break
                    
                    # Small delay between pages to be respectful
                    await asyncio.sleep(1)
                    
                except httpx.HTTPError as e:
                    logger.error(f"Error fetching page {page} from {site_name}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error on {site_name} page {page}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error searching {site_name}: {e}")
        
        logger.info(f"Found {len(recipe_urls)} recipe URLs from {site_name}")
        return list(recipe_urls)
    
    async def scrape_recipe(self, url: str) -> Optional[Dict]:
        """Scrape a single recipe using recipe-scrapers"""
        try:
            # Use recipe-scrapers to extract data
            scraper = scrape_me(url, wild_mode=True)
            
            # Extract all available data
            recipe_data = {
                "source_url": url,
                "source_site": urlparse(url).netloc,
                "title": getattr(scraper, 'title', lambda: None)() or "Unknown",
                "description": getattr(scraper, 'description', lambda: None)() or "",
                "ingredients": getattr(scraper, 'ingredients', lambda: [])() or [],
                "instructions": getattr(scraper, 'instructions', lambda: [])() or [],
                "total_time": getattr(scraper, 'total_time', lambda: None)(),
                "prep_time": getattr(scraper, 'prep_time', lambda: None)(),
                "cook_time": getattr(scraper, 'cook_time', lambda: None)(),
                "yields": getattr(scraper, 'yields', lambda: None)() or "",
                "image": getattr(scraper, 'image', lambda: None)(),
                "nutrients": getattr(scraper, 'nutrients', lambda: {})() or {},
                "cuisine": getattr(scraper, 'cuisine', lambda: None)(),
                "category": getattr(scraper, 'category', lambda: None)(),
                "author": getattr(scraper, 'author', lambda: None)(),
                "ratings": getattr(scraper, 'ratings', lambda: None)(),
            }
            
            # Clean up the data
            if recipe_data["total_time"]:
                recipe_data["total_time"] = int(recipe_data["total_time"])
            if recipe_data["prep_time"]:
                recipe_data["prep_time"] = int(recipe_data["prep_time"])
            if recipe_data["cook_time"]:
                recipe_data["cook_time"] = int(recipe_data["cook_time"])
            
            logger.info(f"Successfully scraped: {recipe_data['title']}")
            return recipe_data
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.aclose()

# Global instance
discovery = RecipeDiscovery()

@mcp.tool()
async def discover_recipes(keyword: str, target_count: int = 100, sites: Optional[List[str]] = None) -> str:
    """
    Discover recipes from multiple sites based on keyword search.
    
    Args:
        keyword: Search term (e.g., "chicken pasta", "vegetarian", "chocolate cake")
        target_count: Target number of recipes to find (default: 100)
        sites: List of specific sites to search (default: all available sites)
    
    Returns:
        JSON string containing raw recipe data from all discovered recipes
    """
    if sites is None:
        sites = list(RECIPE_SITES.keys())
    
    logger.info(f"Starting recipe discovery for '{keyword}' (target: {target_count})")
    
    all_urls = []
    recipes_per_site = max(target_count // len(sites), 10)
    
    # Discover URLs from each site
    for site in sites:
        try:
            urls = await discovery.search_site(site, keyword, recipes_per_site)
            all_urls.extend(urls)
            logger.info(f"Found {len(urls)} URLs from {site}")
        except Exception as e:
            logger.error(f"Error searching {site}: {e}")
            continue
    
    # Remove duplicates and limit to target count
    unique_urls = list(set(all_urls))[:target_count]
    logger.info(f"Total unique URLs found: {len(unique_urls)}")
    
    # Scrape all discovered recipes
    scraped_recipes = []
    batch_size = 5  # Process in small batches to avoid overwhelming servers
    
    for i in range(0, len(unique_urls), batch_size):
        batch_urls = unique_urls[i:i + batch_size]
        
        # Process batch concurrently
        tasks = [discovery.scrape_recipe(url) for url in batch_urls]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in batch_results:
            if isinstance(result, dict):
                scraped_recipes.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Scraping error: {result}")
        
        # Brief pause between batches
        await asyncio.sleep(2)
        
        logger.info(f"Processed {min(i + batch_size, len(unique_urls))}/{len(unique_urls)} URLs")
    
    logger.info(f"Successfully scraped {len(scraped_recipes)} recipes")
    
    # Return as JSON string for AI processing
    result = {
        "keyword": keyword,
        "target_count": target_count,
        "sites_searched": sites,
        "urls_discovered": len(unique_urls),
        "recipes_scraped": len(scraped_recipes),
        "recipes": scraped_recipes
    }
    
    return json.dumps(result, indent=2)

@mcp.tool()
async def scrape_recipe_urls(urls: List[str]) -> str:
    """
    Scrape specific recipe URLs using recipe-scrapers.
    
    Args:
        urls: List of recipe URLs to scrape
    
    Returns:
        JSON string containing scraped recipe data
    """
    logger.info(f"Scraping {len(urls)} specific URLs")
    
    scraped_recipes = []
    batch_size = 5
    
    for i in range(0, len(urls), batch_size):
        batch_urls = urls[i:i + batch_size]
        
        tasks = [discovery.scrape_recipe(url) for url in batch_urls]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in batch_results:
            if isinstance(result, dict):
                scraped_recipes.append(result)
        
        await asyncio.sleep(1)
        logger.info(f"Processed {min(i + batch_size, len(urls))}/{len(urls)} URLs")
    
    result = {
        "urls_provided": len(urls),
        "recipes_scraped": len(scraped_recipes),
        "recipes": scraped_recipes
    }
    
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_supported_sites() -> str:
    """
    Get list of supported recipe sites for discovery.
    
    Returns:
        JSON string with site information
    """
    sites_info = {}
    for site_name, config in RECIPE_SITES.items():
        sites_info[site_name] = {
            "base_url": config["base_url"],
            "max_pages": config["max_pages"]
        }
    
    return json.dumps(sites_info, indent=2)

@mcp.tool()
async def test_site_search(site_name: str, keyword: str) -> str:
    """
    Test search functionality for a specific site.
    
    Args:
        site_name: Name of the site to test
        keyword: Search keyword to test
    
    Returns:
        JSON string with test results
    """
    if site_name not in RECIPE_SITES:
        return json.dumps({"error": f"Site '{site_name}' not supported"})
    
    urls = await discovery.search_site(site_name, keyword, 5)
    
    result = {
        "site": site_name,
        "keyword": keyword,
        "urls_found": len(urls),
        "sample_urls": urls[:3]
    }
    
    return json.dumps(result, indent=2)

# Cleanup on shutdown
@mcp.on_shutdown
async def cleanup():
    await discovery.close()

if __name__ == "__main__":
    mcp.run(transport="stdio")