#!/usr/bin/env python3
"""
Quick test to verify the MCP server tools are working correctly.
This simulates what Claude would do when calling the tools.
"""

import asyncio
import json
import sys
import os

# Add the project directory to Python path
sys.path.insert(0, os.path.abspath('.'))

from recipe_discovery_mcp.server import (
    health_check, 
    get_available_sites, 
    get_search_url_cache_stats,
    discover_recipes
)

async def test_mcp_tools():
    """Test all MCP tools to ensure they work correctly"""
    
    print("🧪 Testing MCP Tools (simulating Claude's tool calls)...")
    
    # Test 1: Health Check
    print("\n1️⃣ Testing health_check tool...")
    try:
        health_result = await health_check()
        if health_result.get("success"):
            print("✅ Health check passed")
            print(f"   Status: {health_result['health']['status']}")
            print(f"   Uptime: {health_result['health']['uptime_seconds']:.1f}s")
        else:
            print("❌ Health check failed")
            print(f"   Error: {health_result}")
    except Exception as e:
        print(f"❌ Health check error: {e}")
    
    # Test 2: Available Sites
    print("\n2️⃣ Testing get_available_sites tool...")
    try:
        sites_result = await get_available_sites()
        if sites_result.get("success"):
            print("✅ Available sites check passed")
            print(f"   Enabled sites: {sites_result['enabled_count']}")
            for site in sites_result['enabled_sites'][:3]:
                print(f"   - {site['domain']}: {site['search_paths_count']} search paths")
        else:
            print("❌ Available sites check failed")
    except Exception as e:
        print(f"❌ Available sites error: {e}")
    
    # Test 3: Cache Stats
    print("\n3️⃣ Testing get_search_url_cache_stats tool...")
    try:
        cache_result = await get_search_url_cache_stats()
        if cache_result.get("success"):
            print("✅ Cache stats check passed")
            print(f"   Cache coverage: {cache_result['cache_coverage_percentage']:.1f}%")
            print(f"   Cached domains: {cache_result['sites_with_cached_urls']}")
        else:
            print("❌ Cache stats check failed")
    except Exception as e:
        print(f"❌ Cache stats error: {e}")
    
    # Test 4: Recipe Discovery (small test)
    print("\n4️⃣ Testing discover_recipes tool (quick test)...")
    try:
        discovery_result = await discover_recipes(
            query="chicken alfredo pasta",
            max_urls_per_site=5,  # Small test
            sites="allrecipes.com",  # Single site
            use_smart_extraction=True
        )
        
        if discovery_result.get("success"):
            print("✅ Recipe discovery test passed")
            summary = discovery_result['summary']
            print(f"   Total recipes: {summary['total_recipes']}")
            print(f"   Successful recipes: {summary['successful_recipes']}")
            print(f"   Success rate: {summary['success_rate']:.1f}%")
            print(f"   Cache hit rate: {summary['cache_utilization']['cache_hit_rate']:.1f}%")
            
            # Show first recipe if available
            if discovery_result['recipes']:
                first_recipe = discovery_result['recipes'][0]
                print(f"   Sample recipe: {first_recipe.get('title', 'No title')}")
        else:
            print("❌ Recipe discovery test failed")
            print(f"   Error: {discovery_result}")
    except Exception as e:
        print(f"❌ Recipe discovery error: {e}")
    
    print("\n🎉 MCP Tool testing completed!")
    print("\n💡 If all tests passed, the MCP server is working correctly.")
    print("   Claude should be able to use these tools once properly configured.")

if __name__ == "__main__":
    asyncio.run(test_mcp_tools())