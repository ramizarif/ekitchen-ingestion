#!/usr/bin/env python3
"""Individual Copy-Paste Test Commands for Recipe Discovery MCP

This module provides individual test commands that users can copy and paste
into their terminal for quick testing of specific features.

Usage:
    python3 tests/user_experience/test_individual_commands.py

This will print all available copy-paste commands.
"""

import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def get_venv_prefix():
    """Get the virtual environment activation prefix"""
    return "source venv/bin/activate && "

def test_1_single_recipe_command():
    """Generate command for single recipe extraction"""
    return f'''{get_venv_prefix()}python3 -c "
import asyncio
from recipe_discovery_mcp.scraper import RecipeScrapingService

async def test():
    scraper = RecipeScrapingService()
    
    # Try different URLs
    urls = [
        'https://www.allrecipes.com/recipe/16354/easy-meatloaf/',
        'https://www.foodnetwork.com/recipes/alton-brown/baked-macaroni-and-cheese-recipe-1939524'
    ]
    
    for url in urls:
        print(f'Testing: {{url}}')
        recipe = await scraper.scrape_recipe(url)
        if recipe.success:
            print(f'✅ {{recipe.title}}: {{len(recipe.ingredients)}} ingredients')
            print(f'   Prep: {{recipe.prep_time}}min | Cook: {{recipe.cook_time}}min')
        else:
            print(f'❌ Failed: {{recipe.error_message}}')
        print()

asyncio.run(test())
"'''

def test_2_batch_processing_command():
    """Generate command for batch processing"""
    return f'''{get_venv_prefix()}python3 -c "
import asyncio
from recipe_discovery_mcp.scraper import RecipeScrapingService

async def test():
    scraper = RecipeScrapingService(max_concurrent=3)
    
    urls = [
        'https://www.allrecipes.com/recipe/16354/easy-meatloaf/',
        'https://www.foodnetwork.com/recipes/alton-brown/baked-macaroni-and-cheese-recipe-1939524',
        'https://www.allrecipes.com/recipe/231015/simple-macaroni-and-cheese/'
    ]
    
    print(f'Processing {{len(urls)}} recipes in batch...')
    recipes = await scraper.scrape_batch(urls)
    
    successful = sum(1 for r in recipes if r.success)
    print(f'Results: {{successful}}/{{len(recipes)}} successful')
    
    for i, recipe in enumerate(recipes, 1):
        if recipe.success:
            print(f'{{i}}. ✅ {{recipe.title}}')
        else:
            print(f'{{i}}. ❌ Failed: {{recipe.error_message}}')

asyncio.run(test())
"'''

def test_3_site_info_command():
    """Generate command for site configuration check"""
    return f'''{get_venv_prefix()}python3 -c "
from recipe_discovery_mcp.site_manager import SiteManager

site_manager = SiteManager()
print('🌐 Configured Recipe Sites:')

for site in site_manager.get_enabled_sites():
    print(f'• {{site.name}} ({{site.domain}})')
    print(f'  Priority: {{site.priority}} | Rate: {{site.rate_limit}} req/s')
    print(f'  Max concurrent: {{site.max_concurrent}}')
    print()
"'''

def test_4_url_discovery_command():
    """Generate command for URL discovery"""
    return f'''{get_venv_prefix()}python3 -c "
import asyncio
from recipe_discovery_mcp.url_manager import UrlManager
from recipe_discovery_mcp.site_manager import SiteManager
from recipe_discovery_mcp.http_client import AsyncHttpClient

async def test():
    http_client = AsyncHttpClient()
    site_manager = SiteManager()
    url_manager = UrlManager(site_manager, http_client)
    
    query = 'chicken pasta'
    print(f'🔍 Discovering URLs for: {{query}}')
    
    urls_by_site = await url_manager.discover_recipe_urls(
        query=query,
        max_urls_per_site=5,
        sites=['allrecipes.com', 'foodnetwork.com']
    )
    
    total_urls = 0
    for site, urls in urls_by_site.items():
        print(f'{{site}}: {{len(urls)}} URLs found')
        for i, url in enumerate(urls[:3], 1):
            print(f'  {{i}}. {{url}}')
        if len(urls) > 3:
            print(f'  ... and {{len(urls)-3}} more')
        total_urls += len(urls)
        print()
    
    print(f'Total URLs discovered: {{total_urls}}')
    await http_client.close()

asyncio.run(test())
"'''

def test_5_full_discovery_command():
    """Generate command for full multi-site discovery"""
    return f'''{get_venv_prefix()}python3 -c "
import asyncio
from recipe_discovery_mcp.discovery_engine import MultiSiteDiscoveryEngine
from recipe_discovery_mcp.site_manager import SiteManager
from recipe_discovery_mcp.url_manager import UrlManager
from recipe_discovery_mcp.http_client import AsyncHttpClient
from recipe_discovery_mcp.scraper import RecipeScrapingService
from recipe_discovery_mcp.models import DiscoveryConfig

async def test():
    # Initialize the full stack
    http_client = AsyncHttpClient()
    site_manager = SiteManager()
    url_manager = UrlManager(site_manager, http_client)
    scraper = RecipeScrapingService()
    discovery_engine = MultiSiteDiscoveryEngine(site_manager, url_manager, scraper)
    
    # Configure discovery
    config = DiscoveryConfig(
        max_urls_per_site=5,
        target_sites=['allrecipes.com', 'foodnetwork.com'],
        validate_urls=True,
        max_total_concurrent=3
    )
    
    query = 'chicken recipe'
    print(f'🚀 Full discovery for: {{query}}')
    print('This will find URLs AND scrape recipes...')
    
    result = await discovery_engine.discover_recipes(query, config)
    
    successful = result.get_successful_recipes()
    
    print(f'📊 Results:')
    print(f'  Total recipes: {{len(result.recipes)}}')
    print(f'  Successful: {{len(successful)}}')
    print(f'  Sites processed: {{len(result.site_summaries)}}')
    
    print(f'\\n🍽️ Sample Recipes:')
    for i, recipe in enumerate(successful[:5], 1):
        print(f'  {{i}}. {{recipe.title}} ({{recipe.site_domain}})')
        print(f'     {{len(recipe.ingredients)}} ingredients')
    
    await http_client.close()

asyncio.run(test())
"'''

def test_6_performance_command():
    """Generate command for performance monitoring"""
    return f'''{get_venv_prefix()}python3 -c "
import asyncio
from recipe_discovery_mcp.scraper import RecipeScrapingService

async def test():
    scraper = RecipeScrapingService()
    
    # Do some scraping
    await scraper.scrape_recipe('https://www.allrecipes.com/recipe/16354/easy-meatloaf/')
    
    # Get stats
    stats = scraper.get_stats()
    print('📊 Performance Statistics:')
    for key, value in stats.items():
        if isinstance(value, float):
            print(f'  {{key}}: {{value:.3f}}')
        else:
            print(f'  {{key}}: {{value}}')
    
    # Test service
    print('\\n🧪 Running service test...')
    test_results = await scraper.test_scraping_service()
    print(f'Service status: {{test_results.get(\"service_status\")}}')

asyncio.run(test())
"'''

def test_7_custom_url_command():
    """Generate command for testing custom URLs"""
    return f'''{get_venv_prefix()}python3 -c "
import asyncio
from recipe_discovery_mcp.scraper import RecipeScrapingService

async def test():
    scraper = RecipeScrapingService()
    url = input('Enter recipe URL: ')
    recipe = await scraper.scrape_recipe(url)
    if recipe.success:
        print(f'✅ {{recipe.title}}')
        print(f'Ingredients: {{len(recipe.ingredients)}}')
        print(f'First 3 ingredients: {{recipe.ingredients[:3]}}')
    else:
        print(f'❌ Failed: {{recipe.error_message}}')

asyncio.run(test())
"'''

def test_8_custom_search_command():
    """Generate command for testing custom search queries"""
    return f'''{get_venv_prefix()}python3 -c "
import asyncio
from recipe_discovery_mcp.url_manager import UrlManager
from recipe_discovery_mcp.site_manager import SiteManager
from recipe_discovery_mcp.http_client import AsyncHttpClient

async def test():
    http_client = AsyncHttpClient()
    site_manager = SiteManager()
    url_manager = UrlManager(site_manager, http_client)
    
    query = input('Enter search query: ')
    urls = await url_manager.discover_recipe_urls(query, max_urls_per_site=5)
    
    for site, url_list in urls.items():
        if url_list:
            print(f'{{site}}: {{len(url_list)}} URLs')
    
    await http_client.close()

asyncio.run(test())
"'''

def print_all_commands():
    """Print all available test commands"""
    
    print("🧪 COPY-PASTE TEST COMMANDS FOR RECIPE DISCOVERY MCP")
    print("=" * 70)
    print("Copy and paste these commands into your terminal:")
    print("=" * 70)
    
    commands = [
        ("Single Recipe Extraction", test_1_single_recipe_command()),
        ("Batch Processing", test_2_batch_processing_command()),
        ("Site Configuration Check", test_3_site_info_command()),
        ("URL Discovery", test_4_url_discovery_command()),
        ("Full Multi-Site Discovery", test_5_full_discovery_command()),
        ("Performance Monitoring", test_6_performance_command()),
        ("Test Custom URL", test_7_custom_url_command()),
        ("Test Custom Search Query", test_8_custom_search_command())
    ]
    
    for i, (name, command) in enumerate(commands, 1):
        print(f"\n{'='*70}")
        print(f"🔸 TEST {i}: {name.upper()}")
        print(f"{'='*70}")
        print(command.strip())
        print()

def print_quick_commands():
    """Print just the most common quick test commands"""
    
    print("⚡ QUICK TEST COMMANDS")
    print("=" * 40)
    
    print("\n1. 🍳 Test Single Recipe (30 seconds):")
    print(f"{get_venv_prefix()}python3 -c \"")
    print("import asyncio")
    print("from recipe_discovery_mcp.scraper import RecipeScrapingService")
    print("async def test():")
    print("    scraper = RecipeScrapingService()")
    print("    recipe = await scraper.scrape_recipe('https://www.allrecipes.com/recipe/16354/easy-meatloaf/')")
    print("    print(f'✅ {recipe.title}: {len(recipe.ingredients)} ingredients')")
    print("asyncio.run(test())")
    print("\"")
    
    print("\n2. 🌐 Check Available Sites (5 seconds):")
    print(f"{get_venv_prefix()}python3 -c \"")
    print("from recipe_discovery_mcp.site_manager import SiteManager")
    print("sm = SiteManager()")
    print("for site in sm.get_enabled_sites():")
    print("    print(f'• {site.name} ({site.domain}) - {site.priority} priority')")
    print("\"")
    
    print("\n3. 🔍 Quick URL Discovery (30 seconds):")
    print(f"{get_venv_prefix()}python3 -c \"")
    print("import asyncio")
    print("from recipe_discovery_mcp.url_manager import UrlManager")
    print("from recipe_discovery_mcp.site_manager import SiteManager")
    print("from recipe_discovery_mcp.http_client import AsyncHttpClient")
    print("async def test():")
    print("    http_client = AsyncHttpClient()")
    print("    site_manager = SiteManager()")
    print("    url_manager = UrlManager(site_manager, http_client)")
    print("    urls = await url_manager.discover_recipe_urls('pasta', max_urls_per_site=3, sites=['allrecipes.com'])")
    print("    for site, url_list in urls.items():")
    print("        print(f'{site}: {len(url_list)} URLs found')")
    print("    await http_client.close()")
    print("asyncio.run(test())")
    print("\"")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        print_quick_commands()
    else:
        print_all_commands()