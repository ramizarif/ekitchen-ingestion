#!/usr/bin/env python3
"""
Integration test for the enhanced MCP server with search URL discovery and caching.
"""

import asyncio
import json
import sys
import os

# Add the project directory to Python path
sys.path.insert(0, os.path.abspath('.'))

from recipe_discovery_mcp.server import state

async def test_integration():
    """Test the integrated search URL discovery and caching workflow"""
    
    print("🧪 Testing integrated MCP server components...")
    
    # Test 1: Initialize services
    print("\n1️⃣ Testing service initialization...")
    try:
        # Force initialization of services
        _ = state.search_url_cache
        _ = state.search_url_discoverer
        _ = state.site_manager
        print("✅ All services initialized successfully")
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        return
    
    # Test 2: Load search URL cache
    print("\n2️⃣ Testing search URL cache loading...")
    try:
        await state.search_url_cache.load_cache()
        cache_stats = await state.search_url_cache.get_cache_stats()
        print(f"✅ Cache loaded: {cache_stats['total_entries']} entries, {cache_stats['valid_entries']} valid")
    except Exception as e:
        print(f"❌ Cache loading failed: {e}")
    
    # Test 3: Test site manager
    print("\n3️⃣ Testing site manager...")
    try:
        enabled_sites = state.site_manager.get_enabled_sites()
        print(f"✅ Found {len(enabled_sites)} enabled sites:")
        for site in enabled_sites[:3]:  # Show first 3
            print(f"   - {site.domain}: {len(site.search_paths)} search paths")
    except Exception as e:
        print(f"❌ Site manager test failed: {e}")
    
    # Test 4: Test search URL discovery workflow
    print("\n4️⃣ Testing search URL discovery workflow...")
    try:
        from recipe_discovery_mcp.server import _get_search_pages_for_query
        
        # Test with a subset of sites
        test_sites = ["allrecipes.com"]
        search_pages = await _get_search_pages_for_query("chicken", test_sites)
        
        print(f"✅ Search URL discovery successful:")
        for domain, url in search_pages.items():
            print(f"   - {domain}: {url}")
            
    except Exception as e:
        print(f"❌ Search URL discovery failed: {e}")
    
    # Test 5: Test cache save
    print("\n5️⃣ Testing cache save...")
    try:
        await state.search_url_cache.save_cache()
        print("✅ Cache saved successfully")
    except Exception as e:
        print(f"❌ Cache save failed: {e}")
    
    print("\n🎉 Integration test completed!")

if __name__ == "__main__":
    asyncio.run(test_integration())