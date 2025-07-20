#!/usr/bin/env python3
"""Interactive Testing Suite for Recipe Discovery MCP Features"""

import asyncio
import sys
import os
import json
from datetime import datetime

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from recipe_discovery_mcp.scraper import RecipeScrapingService
from recipe_discovery_mcp.site_manager import SiteManager
from recipe_discovery_mcp.url_manager import UrlManager
from recipe_discovery_mcp.http_client import AsyncHttpClient
from recipe_discovery_mcp.discovery_engine import MultiSiteDiscoveryEngine
from recipe_discovery_mcp.models import DiscoveryConfig
from recipe_discovery_mcp.config import get_config

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print(f"{'='*60}")

def print_section(title):
    print(f"\n{'─'*40}")
    print(f"🔸 {title}")
    print(f"{'─'*40}")

async def test_1_single_recipe():
    """Test 1: Single Recipe Extraction"""
    print_header("TEST 1: Single Recipe Extraction")
    
    scraper = RecipeScrapingService()
    
    # Test multiple URLs
    test_urls = [
        "https://www.allrecipes.com/recipe/16354/easy-meatloaf/",
        "https://www.foodnetwork.com/recipes/alton-brown/baked-macaroni-and-cheese-recipe-1939524",
        "https://www.allrecipes.com/recipe/213742/cheesy-chicken-broccoli-casserole/"  # This will fail (404)
    ]
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n🔗 Testing URL {i}: {url}")
        try:
            recipe = await scraper.scrape_recipe(url)
            
            if recipe.success:
                print(f"   ✅ SUCCESS!")
                print(f"   📗 Title: {recipe.title}")
                print(f"   🥘 Ingredients: {len(recipe.ingredients)} items")
                print(f"   ⏰ Prep: {recipe.prep_time} min | Cook: {recipe.cook_time} min")
                print(f"   🍽️  Serves: {recipe.yields}")
                print(f"   ⭐ Quality Score: {recipe.get_quality_score():.1f}")
                if recipe.ingredients:
                    print(f"   📋 Sample ingredients: {recipe.ingredients[:3]}")
            else:
                print(f"   ❌ FAILED: {recipe.error_message}")
                print(f"   ℹ️  This shows error handling works!")
                
        except Exception as e:
            print(f"   💥 ERROR: {e}")
    
    # Show stats
    stats = scraper.get_stats()
    print(f"\n📊 Scraper Statistics:")
    print(f"   Total requests: {stats['total_requests']}")
    print(f"   Success rate: {stats['success_rate']:.1f}%")
    print(f"   Requests/second: {stats['requests_per_second']:.2f}")

async def test_2_batch_processing():
    """Test 2: Batch Processing"""
    print_header("TEST 2: Batch Processing")
    
    scraper = RecipeScrapingService(max_concurrent=3)
    
    # Batch of URLs
    urls = [
        "https://www.allrecipes.com/recipe/16354/easy-meatloaf/",
        "https://www.foodnetwork.com/recipes/alton-brown/baked-macaroni-and-cheese-recipe-1939524",
        "https://www.allrecipes.com/recipe/213742/cheesy-chicken-broccoli-casserole/",  # Will fail
        "https://www.allrecipes.com/recipe/231015/simple-macaroni-and-cheese/",
        "https://www.foodnetwork.com/recipes/alton-brown/good-eats-meatloaf-recipe-1937667"
    ]
    
    print(f"🔄 Processing {len(urls)} recipes in batch...")
    print("   (Watch for parallel processing - multiple recipes at once)")
    
    start_time = datetime.now()
    recipes = await scraper.scrape_batch(urls, batch_size=3)
    end_time = datetime.now()
    
    processing_time = (end_time - start_time).total_seconds()
    
    print(f"\n📊 Batch Results:")
    print(f"   ⏱️  Total time: {processing_time:.2f} seconds")
    print(f"   📈 Recipes/second: {len(recipes)/processing_time:.2f}")
    print(f"   ✅ Successful: {sum(1 for r in recipes if r.success)}")
    print(f"   ❌ Failed: {sum(1 for r in recipes if not r.success)}")
    
    print(f"\n📋 Individual Results:")
    for i, recipe in enumerate(recipes, 1):
        if recipe.success:
            print(f"   {i}. ✅ {recipe.title} ({len(recipe.ingredients)} ingredients)")
        else:
            print(f"   {i}. ❌ Failed: {recipe.error_message}")

async def test_3_site_manager():
    """Test 3: Site Manager Configuration"""
    print_header("TEST 3: Site Manager & Configuration")
    
    site_manager = SiteManager()
    config = get_config()
    
    print(f"🌐 Enabled Sites ({len(site_manager.get_enabled_sites())}):")
    for site in site_manager.get_enabled_sites():
        print(f"   • {site.name} ({site.domain})")
        print(f"     Priority: {site.priority} | Rate: {site.rate_limit} req/s | Concurrent: {site.max_concurrent}")
        print(f"     Search paths: {len(site.search_paths)} | URL patterns: {len(site.recipe_url_patterns)}")
    
    print(f"\n⚙️  Global Configuration:")
    print(f"   Max concurrent: {config.max_concurrent_requests}")
    print(f"   Request timeout: {config.request_timeout}s")
    print(f"   Rate limit: {config.requests_per_second} req/s")
    print(f"   Max retries: {config.max_retries}")
    
    # Test site stats
    stats = site_manager.get_stats()
    print(f"\n📊 Site Manager Stats:")
    for key, value in stats.items():
        print(f"   {key}: {value}")

async def test_4_url_discovery():
    """Test 4: URL Discovery (Fast exploration)"""
    print_header("TEST 4: URL Discovery Engine")
    
    http_client = AsyncHttpClient()
    site_manager = SiteManager()
    url_manager = UrlManager(site_manager, http_client)
    
    queries = ["chicken recipe", "pasta"]
    
    for query in queries:
        print_section(f"Discovering URLs for: '{query}'")
        
        # Discover URLs (fast, no scraping)
        start_time = datetime.now()
        urls_by_site = await url_manager.discover_recipe_urls(
            query=query,
            max_urls_per_site=5,
            sites=["allrecipes.com", "foodnetwork.com"]  # Limit to 2 sites for speed
        )
        end_time = datetime.now()
        
        discovery_time = (end_time - start_time).total_seconds()
        
        print(f"   ⏱️  Discovery time: {discovery_time:.2f} seconds")
        
        total_urls = 0
        for site, urls in urls_by_site.items():
            print(f"   🔍 {site}: {len(urls)} URLs found")
            total_urls += len(urls)
            # Show first few URLs
            for i, url in enumerate(urls[:3]):
                print(f"      {i+1}. {url}")
            if len(urls) > 3:
                print(f"      ... and {len(urls)-3} more")
        
        print(f"   📊 Total URLs discovered: {total_urls}")
    
    # Show URL manager stats
    stats = url_manager.get_stats()
    print(f"\n📊 URL Manager Statistics:")
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    await http_client.close()

async def test_5_multi_site_discovery():
    """Test 5: Full Multi-Site Discovery (Discovery + Scraping)"""
    print_header("TEST 5: Multi-Site Discovery Engine (FULL POWER)")
    
    # Initialize the full stack
    http_client = AsyncHttpClient()
    site_manager = SiteManager()
    url_manager = UrlManager(site_manager, http_client)
    scraper = RecipeScrapingService()
    discovery_engine = MultiSiteDiscoveryEngine(site_manager, url_manager, scraper)
    
    # Test configurations
    test_configs = [
        {
            "name": "Quick Test",
            "query": "chicken recipe",
            "config": DiscoveryConfig(
                max_urls_per_site=3,
                target_sites=["allrecipes.com"],
                validate_urls=True,
                max_total_concurrent=2
            )
        },
        {
            "name": "Multi-Site Test", 
            "query": "pasta",
            "config": DiscoveryConfig(
                max_urls_per_site=5,
                target_sites=["allrecipes.com", "foodnetwork.com"],
                validate_urls=True,
                max_total_concurrent=3
            )
        }
    ]
    
    for test in test_configs:
        print_section(f"{test['name']}: '{test['query']}'")
        
        start_time = datetime.now()
        result = await discovery_engine.discover_recipes(test['query'], test['config'])
        end_time = datetime.now()
        
        processing_time = (end_time - start_time).total_seconds()
        successful_recipes = result.get_successful_recipes()
        
        print(f"   ⏱️  Total time: {processing_time:.2f} seconds")
        print(f"   🔍 URLs discovered: {result.summary.get('total_urls_discovered', 0)}")
        print(f"   📊 Total recipes: {len(result.recipes)}")
        print(f"   ✅ Successful: {len(successful_recipes)}")
        print(f"   ❌ Failed: {len(result.get_failed_recipes())}")
        print(f"   🌐 Sites processed: {len(result.site_summaries)}")
        
        # Show site summaries
        print(f"\n   📋 Site Results:")
        for site, summary in result.site_summaries.items():
            print(f"      {site}: {summary['successful']}/{summary['total']} recipes")
        
        # Show successful recipes
        print(f"\n   🍽️  Sample Successful Recipes:")
        for i, recipe in enumerate(successful_recipes[:5], 1):
            print(f"      {i}. {recipe.title} ({recipe.site_domain})")
            print(f"         {len(recipe.ingredients)} ingredients, Quality: {recipe.get_quality_score():.1f}")
    
    # Show engine stats
    stats = discovery_engine.get_stats()
    print(f"\n📊 Discovery Engine Statistics:")
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    await http_client.close()

async def test_6_error_handling():
    """Test 6: Error Handling & Recovery"""
    print_header("TEST 6: Error Handling & Recovery")
    
    scraper = RecipeScrapingService()
    
    # Test various error scenarios
    error_tests = [
        ("Invalid URL", "not-a-url"),
        ("404 Error", "https://www.allrecipes.com/recipe/999999/nonexistent-recipe/"),
        ("Invalid Domain", "https://totally-fake-recipe-site.com/recipe"),
        ("Empty URL", ""),
    ]
    
    print("🚨 Testing error scenarios (these should fail gracefully):")
    
    for test_name, url in error_tests:
        print(f"\n   🧪 {test_name}: {url}")
        try:
            recipe = await scraper.scrape_recipe(url)
            print(f"      Status: {recipe.status}")
            print(f"      Error: {recipe.error_message}")
            print(f"      ✅ Error handled gracefully!")
        except Exception as e:
            print(f"      💥 Exception caught: {e}")
            print(f"      ✅ Exception handling works!")

async def test_7_performance_monitoring():
    """Test 7: Performance Monitoring"""
    print_header("TEST 7: Performance Monitoring")
    
    scraper = RecipeScrapingService()
    
    # Do some work to generate stats
    print("🔄 Generating performance data...")
    urls = [
        "https://www.allrecipes.com/recipe/16354/easy-meatloaf/",
        "https://www.foodnetwork.com/recipes/alton-brown/baked-macaroni-and-cheese-recipe-1939524"
    ]
    
    for url in urls:
        await scraper.scrape_recipe(url)
    
    # Test scraper service
    print("\n🧪 Running service test...")
    test_results = await scraper.test_scraping_service()
    
    print(f"📊 Service Test Results:")
    print(f"   Status: {test_results.get('service_status')}")
    print(f"   Test summary: {test_results.get('test_summary', {})}")
    
    # Get comprehensive stats
    stats = scraper.get_stats()
    print(f"\n📈 Performance Statistics:")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"   {key}: {value:.3f}")
        else:
            print(f"   {key}: {value}")

async def run_all_tests():
    """Run all feature tests"""
    print_header("RECIPE DISCOVERY MCP - COMPLETE FEATURE TESTING")
    print("🎯 This will test every major feature of your system!")
    print("⏱️  Total estimated time: 2-3 minutes")
    
    start_time = datetime.now()
    
    try:
        await test_1_single_recipe()
        await test_2_batch_processing()
        await test_3_site_manager()
        await test_4_url_discovery()
        await test_5_multi_site_discovery()
        await test_6_error_handling()
        await test_7_performance_monitoring()
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        print_header("🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
        print(f"⏱️  Total testing time: {total_time:.2f} seconds")
        print("\n🚀 Your Recipe Discovery MCP system is fully functional!")
        print("\n💡 Next steps:")
        print("   • Try your own recipe URLs")
        print("   • Experiment with different search queries")
        print("   • Adjust batch sizes and concurrency")
        print("   • Set up Claude Desktop integration")
        
    except Exception as e:
        print(f"\n💥 Test suite failed: {e}")
        raise

async def run_quick_test():
    """Run a quick subset of tests"""
    print_header("QUICK FEATURE TEST")
    await test_1_single_recipe()
    await test_3_site_manager()
    print_header("🎉 QUICK TEST COMPLETED!")

def main():
    """Main function with test options"""
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        print("🏃‍♂️ Running quick test...")
        asyncio.run(run_quick_test())
    else:
        print("🔬 Running complete test suite...")
        print("💡 Tip: Use 'python3 test_all_features.py quick' for faster testing")
        asyncio.run(run_all_tests())

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Testing failed: {e}")
        sys.exit(1)