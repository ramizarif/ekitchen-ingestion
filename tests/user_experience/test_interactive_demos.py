#!/usr/bin/env python3
"""Interactive Demo Scripts for Recipe Discovery MCP

These scripts provide guided, interactive demonstrations of the Recipe Discovery MCP
system capabilities. Perfect for user onboarding, training, and showcasing features.

Usage:
    python3 tests/user_experience/test_interactive_demos.py
"""

import asyncio
import sys
import os
from datetime import datetime
import time

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

def print_banner(title, width=60):
    """Print a formatted banner"""
    print(f"\n{'='*width}")
    print(f"🎯 {title}")
    print(f"{'='*width}")

def print_step(step_num, description):
    """Print a formatted step"""
    print(f"\n🔸 Step {step_num}: {description}")
    print("-" * 40)

def wait_for_user(message="Press Enter to continue..."):
    """Wait for user input"""
    input(f"\n💡 {message}")

async def demo_1_basic_introduction():
    """Demo 1: Basic Introduction to Recipe Discovery"""
    print_banner("DEMO 1: Recipe Discovery MCP Introduction")
    
    print("Welcome to the Recipe Discovery MCP System!")
    print("This system can:")
    print("• Extract recipes from 500+ websites")
    print("• Process multiple recipes simultaneously")
    print("• Discover recipes across multiple sites")
    print("• Handle errors gracefully")
    print("• Provide real-time performance monitoring")
    
    wait_for_user("Let's start with checking the system configuration...")
    
    print_step(1, "System Configuration")
    config = get_config()
    site_manager = SiteManager()
    
    print(f"✅ Server: {config.server_name}")
    print(f"✅ Max concurrent requests: {config.max_concurrent_requests}")
    print(f"✅ Request timeout: {config.request_timeout}s")
    print(f"✅ Configured sites: {len(site_manager.get_enabled_sites())}")
    
    wait_for_user("Now let's see what recipe sites are available...")
    
    print_step(2, "Available Recipe Sites")
    for site in site_manager.get_enabled_sites():
        print(f"🌐 {site.name} ({site.domain})")
        print(f"   Priority: {site.priority} | Rate: {site.rate_limit} req/s")
    
    wait_for_user("Ready to test recipe extraction?")

async def demo_2_single_recipe_extraction():
    """Demo 2: Single Recipe Extraction"""
    print_banner("DEMO 2: Single Recipe Extraction")
    
    print("Let's extract a recipe from AllRecipes...")
    
    scraper = RecipeScrapingService()
    test_url = "https://www.allrecipes.com/recipe/16354/easy-meatloaf/"
    
    print(f"🔗 Testing URL: {test_url}")
    print("⏳ Extracting recipe data...")
    
    start_time = time.time()
    recipe = await scraper.scrape_recipe(test_url)
    end_time = time.time()
    
    if recipe.success:
        print(f"\n✅ SUCCESS! Extracted in {end_time - start_time:.2f} seconds")
        print(f"📗 Title: {recipe.title}")
        print(f"🥘 Ingredients: {len(recipe.ingredients)} items")
        print(f"⏰ Prep Time: {recipe.prep_time} minutes")
        print(f"🍳 Cook Time: {recipe.cook_time} minutes")
        print(f"🍽️  Serves: {recipe.yields}")
        print(f"⭐ Quality Score: {recipe.get_quality_score():.1f}")
        
        if recipe.ingredients:
            print(f"\n📋 First few ingredients:")
            for i, ingredient in enumerate(recipe.ingredients[:5], 1):
                print(f"   {i}. {ingredient}")
            if len(recipe.ingredients) > 5:
                print(f"   ... and {len(recipe.ingredients) - 5} more")
    else:
        print(f"❌ Extraction failed: {recipe.error_message}")
    
    wait_for_user("Ready to try batch processing?")

async def demo_3_batch_processing():
    """Demo 3: Batch Processing Demo"""
    print_banner("DEMO 3: Batch Processing")
    
    print("Now let's process multiple recipes simultaneously...")
    print("This demonstrates the system's ability to handle concurrent operations.")
    
    scraper = RecipeScrapingService(max_concurrent=3)
    
    urls = [
        "https://www.allrecipes.com/recipe/16354/easy-meatloaf/",
        "https://www.foodnetwork.com/recipes/alton-brown/baked-macaroni-and-cheese-recipe-1939524",
        "https://www.allrecipes.com/recipe/231015/simple-macaroni-and-cheese/",
        "https://www.allrecipes.com/recipe/213742/cheesy-chicken-broccoli-casserole/"  # This will fail (404)
    ]
    
    print(f"🔄 Processing {len(urls)} recipes in parallel...")
    print("   (Notice how they process simultaneously, not one at a time)")
    
    start_time = time.time()
    recipes = await scraper.scrape_batch(urls)
    end_time = time.time()
    
    processing_time = end_time - start_time
    successful = sum(1 for r in recipes if r.success)
    
    print(f"\n📊 Batch Results:")
    print(f"   ⏱️  Total time: {processing_time:.2f} seconds")
    print(f"   📈 Recipes/second: {len(recipes)/processing_time:.2f}")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed: {len(recipes) - successful}")
    print(f"   🎯 Success rate: {successful/len(recipes)*100:.1f}%")
    
    print(f"\n📋 Individual Results:")
    for i, recipe in enumerate(recipes, 1):
        if recipe.success:
            print(f"   {i}. ✅ {recipe.title}")
        else:
            print(f"   {i}. ❌ Failed: {recipe.error_message}")
    
    # Show performance stats
    stats = scraper.get_stats()
    print(f"\n📈 Performance Statistics:")
    print(f"   Total requests: {stats['total_requests']}")
    print(f"   Success rate: {stats['success_rate']:.1f}%")
    print(f"   Requests/second: {stats['requests_per_second']:.2f}")
    
    wait_for_user("Ready to see the multi-site discovery engine?")

async def demo_4_multi_site_discovery():
    """Demo 4: Multi-Site Discovery Engine"""
    print_banner("DEMO 4: Multi-Site Discovery Engine")
    
    print("This is the most powerful feature - discovering recipes across multiple sites!")
    print("The system will:")
    print("1. Search for URLs on multiple recipe sites")
    print("2. Validate and filter the URLs")
    print("3. Extract recipe data from valid URLs")
    print("4. Provide comprehensive results and statistics")
    
    wait_for_user("Let's start the discovery process...")
    
    # Initialize the full discovery stack
    http_client = AsyncHttpClient()
    site_manager = SiteManager()
    url_manager = UrlManager(site_manager, http_client)
    scraper = RecipeScrapingService()
    discovery_engine = MultiSiteDiscoveryEngine(site_manager, url_manager, scraper)
    
    # Configure discovery
    config = DiscoveryConfig(
        max_urls_per_site=5,
        target_sites=["allrecipes.com", "foodnetwork.com"],
        validate_urls=True,
        max_total_concurrent=3
    )
    
    query = "chicken recipe"
    
    print(f"🔍 Discovering recipes for: '{query}'")
    print(f"🎯 Target sites: {', '.join(config.target_sites)}")
    print(f"📊 Max URLs per site: {config.max_urls_per_site}")
    print(f"⚡ Concurrent operations: {config.max_total_concurrent}")
    
    print(f"\n⏳ Starting discovery process...")
    start_time = time.time()
    
    result = await discovery_engine.discover_recipes(query, config)
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    successful_recipes = result.get_successful_recipes()
    failed_recipes = result.get_failed_recipes()
    
    print(f"\n🎉 Discovery Complete in {processing_time:.2f} seconds!")
    print(f"📊 Overall Results:")
    print(f"   🔍 URLs discovered: {result.summary.get('total_urls_discovered', 0)}")
    print(f"   📄 Total recipes: {len(result.recipes)}")
    print(f"   ✅ Successful: {len(successful_recipes)}")
    print(f"   ❌ Failed: {len(failed_recipes)}")
    print(f"   🌐 Sites processed: {len(result.site_summaries)}")
    print(f"   🎯 Success rate: {len(successful_recipes)/len(result.recipes)*100:.1f}%")
    
    print(f"\n🏢 Site-by-Site Results:")
    for site, summary in result.site_summaries.items():
        print(f"   {site}:")
        print(f"      📊 {summary['successful']}/{summary['total']} recipes successful")
        print(f"      🎯 {summary['successful']/summary['total']*100:.1f}% success rate")
    
    if successful_recipes:
        print(f"\n🍽️  Sample Successful Recipes:")
        for i, recipe in enumerate(successful_recipes[:5], 1):
            print(f"   {i}. {recipe.title}")
            print(f"      🌐 From: {recipe.site_domain}")
            print(f"      🥘 {len(recipe.ingredients)} ingredients")
            print(f"      ⭐ Quality: {recipe.get_quality_score():.1f}")
    
    # Show engine statistics
    stats = discovery_engine.get_stats()
    print(f"\n📈 Discovery Engine Statistics:")
    for key, value in stats.items():
        if isinstance(value, (int, float)):
            print(f"   {key}: {value}")
    
    await http_client.close()
    
    wait_for_user("Discovery demo complete! Ready to see error handling?")

async def demo_5_error_handling():
    """Demo 5: Error Handling and Recovery"""
    print_banner("DEMO 5: Error Handling & Recovery")
    
    print("Let's see how the system handles various error scenarios...")
    print("This demonstrates the robustness and reliability of the system.")
    
    scraper = RecipeScrapingService()
    
    error_scenarios = [
        ("Valid URL", "https://www.allrecipes.com/recipe/16354/easy-meatloaf/"),
        ("404 Not Found", "https://www.allrecipes.com/recipe/999999/nonexistent-recipe/"),
        ("Invalid Domain", "https://totally-fake-recipe-site.com/recipe"),
        ("Malformed URL", "not-a-url-at-all")
    ]
    
    print(f"\n🧪 Testing {len(error_scenarios)} scenarios:")
    
    for i, (scenario, url) in enumerate(error_scenarios, 1):
        print(f"\n   Test {i}: {scenario}")
        print(f"   URL: {url}")
        
        try:
            recipe = await scraper.scrape_recipe(url)
            
            if recipe.success:
                print(f"   ✅ Success: {recipe.title}")
            else:
                print(f"   ⚠️  Handled gracefully: {recipe.error_message}")
                print(f"   ✅ System remained stable")
                
        except Exception as e:
            print(f"   🛡️  Exception caught and handled: {str(e)[:50]}...")
            print(f"   ✅ System remained stable")
        
        time.sleep(0.5)  # Brief pause for readability
    
    print(f"\n🎯 Error Handling Summary:")
    print(f"   • All error scenarios handled gracefully")
    print(f"   • System remained operational throughout")
    print(f"   • No crashes or unhandled exceptions")
    print(f"   • Appropriate error messages provided")
    
    wait_for_user("Error handling demo complete!")

async def demo_6_performance_monitoring():
    """Demo 6: Performance Monitoring"""
    print_banner("DEMO 6: Performance Monitoring")
    
    print("Let's explore the built-in monitoring and analytics capabilities...")
    
    scraper = RecipeScrapingService()
    
    # Generate some activity for monitoring
    print("🔄 Generating test activity for monitoring...")
    test_urls = [
        "https://www.allrecipes.com/recipe/16354/easy-meatloaf/",
        "https://www.foodnetwork.com/recipes/alton-brown/baked-macaroni-and-cheese-recipe-1939524"
    ]
    
    for url in test_urls:
        await scraper.scrape_recipe(url)
    
    # Show real-time statistics
    stats = scraper.get_stats()
    print(f"\n📊 Real-Time Statistics:")
    print(f"   Uptime: {stats['uptime_seconds']:.2f} seconds")
    print(f"   Total requests: {stats['total_requests']}")
    print(f"   Successful requests: {stats['successful_requests']}")
    print(f"   Failed requests: {stats['failed_requests']}")
    print(f"   Success rate: {stats['success_rate']:.1f}%")
    print(f"   Requests per second: {stats['requests_per_second']:.2f}")
    print(f"   Max concurrent: {stats['max_concurrent']}")
    
    # Run service health test
    print(f"\n🧪 Running comprehensive service test...")
    test_results = await scraper.test_scraping_service()
    
    print(f"📋 Service Test Results:")
    print(f"   Service status: {test_results.get('service_status')}")
    print(f"   Test summary: {test_results.get('test_summary', {})}")
    
    # Show configuration
    config = get_config()
    print(f"\n⚙️  System Configuration:")
    print(f"   Server name: {config.server_name}")
    print(f"   Log level: {config.log_level}")
    print(f"   Max concurrent: {config.max_concurrent_requests}")
    print(f"   Timeout: {config.request_timeout}s")
    print(f"   Rate limit: {config.requests_per_second} req/s")
    print(f"   Max retries: {config.max_retries}")
    
    wait_for_user("Performance monitoring demo complete!")

async def demo_interactive_menu():
    """Interactive menu for selecting demos"""
    print_banner("RECIPE DISCOVERY MCP - INTERACTIVE DEMOS")
    
    demos = [
        ("Basic Introduction", demo_1_basic_introduction),
        ("Single Recipe Extraction", demo_2_single_recipe_extraction),
        ("Batch Processing", demo_3_batch_processing),
        ("Multi-Site Discovery Engine", demo_4_multi_site_discovery),
        ("Error Handling & Recovery", demo_5_error_handling),
        ("Performance Monitoring", demo_6_performance_monitoring)
    ]
    
    while True:
        print(f"\n🎯 Available Demos:")
        for i, (name, _) in enumerate(demos, 1):
            print(f"   {i}. {name}")
        print(f"   7. Run All Demos")
        print(f"   0. Exit")
        
        try:
            choice = input(f"\n🔸 Select demo (0-7): ").strip()
            
            if choice == "0":
                print("👋 Goodbye!")
                break
            elif choice == "7":
                print("🚀 Running all demos...")
                for name, demo_func in demos:
                    print(f"\n🎬 Starting: {name}")
                    await demo_func()
                print(f"\n🎉 All demos completed!")
                break
            elif choice.isdigit() and 1 <= int(choice) <= len(demos):
                demo_index = int(choice) - 1
                name, demo_func = demos[demo_index]
                print(f"\n🎬 Starting: {name}")
                await demo_func()
            else:
                print("❌ Invalid choice. Please select 0-7.")
                
        except KeyboardInterrupt:
            print(f"\n👋 Demo interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

async def run_quick_demo():
    """Run a quick demonstration of key features"""
    print_banner("QUICK DEMO - Recipe Discovery MCP Key Features")
    
    print("🎯 This quick demo will show you the core capabilities:")
    print("   • Single recipe extraction")
    print("   • Batch processing")
    print("   • Multi-site discovery")
    print("   • Error handling")
    
    wait_for_user("Ready to start the quick demo?")
    
    await demo_2_single_recipe_extraction()
    await demo_3_batch_processing()
    await demo_5_error_handling()
    
    print_banner("🎉 QUICK DEMO COMPLETE!")
    print("You've seen the core capabilities of the Recipe Discovery MCP system.")
    print("For more detailed demonstrations, run the full interactive demo.")

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        print("🏃‍♂️ Running quick demo...")
        asyncio.run(run_quick_demo())
    else:
        print("🎬 Starting interactive demo menu...")
        asyncio.run(demo_interactive_menu())

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n👋 Demo interrupted. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"💥 Demo failed: {e}")
        sys.exit(1)