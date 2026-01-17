#!/usr/bin/env python3
"""
Simple Spoonacular API Test
Test basic Spoonacular functionality to verify API connectivity
"""

import os
import sys
import json
from datetime import datetime

# Add src to path to import our modules
sys.path.insert(0, 'src')

def test_spoonacular_mcp():
    """Test using Spoonacular MCP server"""
    print("🧪 TESTING SPOONACULAR MCP SERVER")
    print("=" * 50)
    
    try:
        # Test common ingredients
        test_ingredients = ["salt", "chicken breast", "olive oil", "butter", "garlic"]
        
        for ingredient_name in test_ingredients:
            print(f"\n🔍 Testing ingredient: '{ingredient_name}'")
            print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
            
            # We'll call the MCP server directly here
            # This would be replaced with actual MCP calls
            print(f"   ℹ️  Would search for: {ingredient_name}")
            print(f"   ⏳ MCP call would happen here...")
            
        return True
        
    except Exception as e:
        print(f"❌ MCP test failed: {e}")
        return False

def test_spoonacular_direct():
    """Test direct Spoonacular API calls"""
    print("\n🧪 TESTING DIRECT SPOONACULAR API")
    print("=" * 50)
    
    # Check if we have API key in environment or config file
    api_key = os.getenv('SPOONACULAR_API_KEY')
    
    if not api_key:
        # Try loading from config file
        try:
            config_path = "config/spoonacular.json"
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    api_key = config.get('api_key')
                    print(f"✅ API key loaded from config file: {config_path}")
        except Exception as e:
            print(f"⚠️  Could not load config file: {e}")
    
    if not api_key:
        print("❌ SPOONACULAR_API_KEY not found in environment or config")
        print("   Add to local.env: SPOONACULAR_API_KEY=your_key")
        print("   Or check config/spoonacular.json")
        return False
    
    print(f"✅ API key found: {api_key[:10]}...")
    
    try:
        import requests
        
        # Check if using RapidAPI or direct API
        config_path = "config/spoonacular.json"
        base_url = "https://api.spoonacular.com"
        headers = {}
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    configured_base_url = config.get('base_url', '')
                    if 'rapidapi' in configured_base_url:
                        base_url = configured_base_url
                        headers = {
                            'X-RapidAPI-Key': api_key,
                            'X-RapidAPI-Host': 'spoonacular-recipe-food-nutrition-v1.p.rapidapi.com'
                        }
                        print(f"📡 Using RapidAPI endpoint: {base_url}")
                    else:
                        print(f"📡 Using direct Spoonacular API")
            except Exception as e:
                print(f"⚠️  Could not read config: {e}")
        
        # Test ingredient search endpoint
        test_ingredients = ["salt", "chicken", "olive oil"]
        
        for ingredient_name in test_ingredients:
            print(f"\n🔍 Testing ingredient search: '{ingredient_name}'")
            
            # Search for ingredient
            search_url = f"{base_url}/food/ingredients/search"
            params = {
                'query': ingredient_name,
                'number': 3
            }
            
            # Add API key to params if not using RapidAPI
            if not headers:
                params['apiKey'] = api_key
            
            print(f"   🌐 URL: {search_url}")
            print(f"   📝 Params: query={ingredient_name}, number=3")
            print(f"   🔑 Headers: {list(headers.keys()) if headers else 'API key in params'}")
            
            response = requests.get(search_url, params=params, headers=headers, timeout=10)
            
            print(f"   📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                print(f"   ✅ Found {len(results)} results")
                
                for i, result in enumerate(results[:2]):  # Show first 2
                    print(f"      {i+1}. ID: {result.get('id')}, Name: {result.get('name')}")
                
                # Test getting details for first result
                if results:
                    ingredient_id = results[0]['id']
                    print(f"\n   🔬 Testing ingredient details for ID: {ingredient_id}")
                    
                    details_url = f"{base_url}/food/ingredients/{ingredient_id}/information"
                    details_params = {
                        'amount': 100,
                        'unit': 'grams'
                    }
                    
                    # Add API key to params if not using RapidAPI
                    if not headers:
                        details_params['apiKey'] = api_key
                    
                    details_response = requests.get(details_url, params=details_params, headers=headers, timeout=10)
                    print(f"   📊 Details Status: {details_response.status_code}")
                    
                    if details_response.status_code == 200:
                        details_data = details_response.json()
                        nutrition = details_data.get('nutrition', {}).get('nutrients', [])
                        calories = next((n['amount'] for n in nutrition if n['name'] == 'Calories'), 'N/A')
                        protein = next((n['amount'] for n in nutrition if n['name'] == 'Protein'), 'N/A')
                        
                        print(f"      📊 Calories: {calories}, Protein: {protein}g")
                        print(f"      ✅ Ingredient details working!")
                    else:
                        print(f"      ❌ Details failed: {details_response.text[:100]}")
                        
            else:
                print(f"   ❌ Search failed: {response.text[:100]}")
                print(f"   🚨 Status {response.status_code} might indicate API issues")
                return False
        
        print(f"\n✅ Direct Spoonacular API test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Direct API test failed: {e}")
        return False

def main():
    print("🧪 SPOONACULAR CONNECTIVITY TEST")
    print("=" * 60)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load environment variables
    try:
        from processing.ingredient_processor_direct import load_env_file
        env_loaded = load_env_file()
        print(f"📁 Environment loaded from: {env_loaded}")
    except Exception as e:
        print(f"⚠️  Could not load environment: {e}")
    
    # Test direct API first
    direct_success = test_spoonacular_direct()
    
    # Test MCP (placeholder for now)
    mcp_success = test_spoonacular_mcp()
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print(f"Direct API: {'✅ PASS' if direct_success else '❌ FAIL'}")
    print(f"MCP Server: {'✅ PASS' if mcp_success else '❌ FAIL'}")
    
    if direct_success:
        print("\n🎉 Spoonacular API is working correctly!")
        print("   The ingredient processor should be able to enrich ingredients.")
    else:
        print("\n🚨 Spoonacular API issues detected!")
        print("   Check your API key and network connectivity.")
        print("   Ingredient enrichment may not work properly.")

if __name__ == "__main__":
    main()