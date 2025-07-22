#!/usr/bin/env python3
"""Interactive Demo Scripts for Spoonacular API Client

These scripts provide guided, interactive demonstrations of the Spoonacular API client
capabilities. Perfect for user onboarding, testing API connectivity, and showcasing features.

Usage:
    python3 tests/user_experience/test_spoonacular_demos.py
"""

import asyncio
import sys
import os
from datetime import datetime
import time

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from spoonacular_client import (
    SpoonacularClient,
    SpoonacularError,
    SpoonacularAuthError,
    SpoonacularRateLimitError,
    SpoonacularNotFoundError
)
from spoonacular_client.config import get_config
from spoonacular_client.exceptions import SpoonacularConfigError
from spoonacular_client.models import (
    IngredientSearchResult,
    IngredientInformation,
    IngredientSubstitutes
)


def print_banner(title, width=60):
    """Print a formatted banner"""
    print(f"\n{'='*width}")
    print(f"🥘 {title}")
    print(f"{'='*width}")


def print_step(step_num, description):
    """Print a formatted step"""
    print(f"\n🔸 Step {step_num}: {description}")
    print("-" * 40)


def wait_for_user(message="Press Enter to continue..."):
    """Wait for user input"""
    input(f"\n💡 {message}")


def print_error(error_type, message):
    """Print formatted error message"""
    print(f"\n❌ {error_type}: {message}")


def print_success(message):
    """Print formatted success message"""
    print(f"\n✅ {message}")


async def demo_1_setup_and_config():
    """Demo 1: Configuration Setup and API Key Validation"""
    print_banner("DEMO 1: Spoonacular API Setup & Configuration")
    
    print("Welcome to the Spoonacular API Client!")
    print("This client provides:")
    print("• 🔍 Ingredient search across thousands of ingredients")
    print("• 📊 Detailed nutrition information per 100g")
    print("• 🔄 Intelligent ingredient substitutions")
    print("• ⚡ Async operation with rate limiting")
    print("• 🛡️  Comprehensive error handling")
    
    wait_for_user("Let's start by checking your API configuration...")
    
    print_step(1, "Configuration Validation")
    
    try:
        config = get_config()
        print_success("Configuration loaded successfully!")
        print(f"🌐 Base URL: {config.base_url}")
        print(f"⏱️  Request timeout: {config.request_timeout}s")
        print(f"🔄 Max retries: {config.max_retries}")
        print(f"📊 Rate limit: {config.requests_per_minute} requests/minute")
        
        # Check if API key is set (without exposing it)
        if config.api_key and config.api_key != "YOUR_SPOONACULAR_API_KEY_HERE":
            print_success("API key is configured")
        else:
            print_error("Configuration", "API key not set properly")
            print("Please edit config/spoonacular.json and add your Spoonacular API key")
            print("Get your API key from: https://spoonacular.com/food-api")
            return False
            
    except SpoonacularConfigError as e:
        print_error("Configuration Error", str(e))
        print("\nTo fix this:")
        print("1. Create config/spoonacular.json")
        print("2. Add your Spoonacular API key")
        print("3. Get your API key from: https://spoonacular.com/food-api")
        return False
    except Exception as e:
        print_error("Unexpected Error", str(e))
        return False
    
    wait_for_user("Configuration looks good! Ready to test API connectivity?")
    return True


async def demo_2_ingredient_search():
    """Demo 2: Ingredient Search Functionality"""
    print_banner("DEMO 2: Ingredient Search")
    
    print("Let's search for ingredients and see what we can find...")
    
    print_step(1, "Basic Ingredient Search")
    
    async with SpoonacularClient() as client:
        # Test search for common ingredient
        search_term = "apple"
        print(f"🔍 Searching for: '{search_term}'")
        print("⏳ Making API request...")
        
        try:
            start_time = time.time()
            response = await client.search_ingredients(search_term, number=5)
            end_time = time.time()
            
            # Parse response using our model
            search_result = IngredientSearchResult.from_dict(response)
            
            print_success(f"Search completed in {end_time - start_time:.2f} seconds")
            print(f"📊 Found {search_result.total_results} total results")
            print(f"📋 Showing {len(search_result.results)} results:")
            
            for i, ingredient in enumerate(search_result.results, 1):
                print(f"  {i}. {ingredient.name} (ID: {ingredient.id})")
                if ingredient.image:
                    print(f"     🖼️ Image: {ingredient.image}")
                    
        except SpoonacularAuthError as e:
            print_error("Authentication Error", str(e))
            print("Please check your API key in config/spoonacular.json")
            return False
        except SpoonacularRateLimitError as e:
            print_error("Rate Limit", str(e))
            print("You've hit the API rate limit. Please wait before trying again.")
            return False
        except SpoonacularError as e:
            print_error("API Error", str(e))
            return False
        except Exception as e:
            print_error("Unexpected Error", str(e))
            return False
    
    wait_for_user("Great! Ready to test more specific searches?")
    
    print_step(2, "Advanced Search with Filters")
    
    async with SpoonacularClient() as client:
        # Test search with intolerances
        search_term = "milk"
        print(f"🔍 Searching for: '{search_term}' (excluding dairy)")
        
        try:
            response = await client.search_ingredients(
                search_term, 
                number=3,
                intolerances="dairy"
            )
            
            search_result = IngredientSearchResult.from_dict(response)
            print_success(f"Found {len(search_result.results)} dairy-free alternatives")
            
            for ingredient in search_result.results:
                print(f"  • {ingredient.name}")
                
        except SpoonacularError as e:
            print_error("API Error", str(e))
            return False
    
    wait_for_user("Excellent! Ready to get detailed ingredient information?")
    return True


async def demo_3_ingredient_information():
    """Demo 3: Detailed Ingredient Information"""
    print_banner("DEMO 3: Detailed Ingredient Information")
    
    print("Now let's get detailed nutrition information for a specific ingredient...")
    
    print_step(1, "Getting Ingredient Details")
    
    async with SpoonacularClient() as client:
        try:
            # First, search for an ingredient to get its ID
            search_response = await client.search_ingredients("chicken breast", number=1)
            search_result = IngredientSearchResult.from_dict(search_response)
            
            if not search_result.results:
                print_error("Search", "No results found for chicken breast")
                return False
                
            ingredient = search_result.results[0]
            print(f"🔍 Found: {ingredient.name} (ID: {ingredient.id})")
            
            print("⏳ Getting detailed nutrition information...")
            
            # Get detailed information
            start_time = time.time()
            info_response = await client.get_ingredient_information(
                ingredient.id,
                amount=100,
                unit="grams"
            )
            end_time = time.time()
            
            # Parse the detailed information
            ingredient_info = IngredientInformation.from_dict(info_response)
            
            print_success(f"Information retrieved in {end_time - start_time:.2f} seconds")
            print(f"\n📊 Detailed Information for {ingredient_info.name}:")
            print(f"  • Amount: {ingredient_info.amount} {ingredient_info.unit}")
            print(f"  • Aisle: {ingredient_info.aisle or 'Not specified'}")
            print(f"  • Consistency: {ingredient_info.consistency or 'Not specified'}")
            
            if ingredient_info.nutrition:
                print(f"\n🥗 Nutrition Information (per 100g):")
                # Show key nutrients
                key_nutrients = ["Calories", "Protein", "Fat", "Carbohydrates"]
                for nutrient in ingredient_info.nutrition:
                    if nutrient.name in key_nutrients:
                        print(f"  • {nutrient.name}: {nutrient.amount} {nutrient.unit}")
                        if nutrient.percent_of_daily_needs:
                            print(f"    ({nutrient.percent_of_daily_needs:.1f}% daily value)")
            
            if ingredient_info.possible_units:
                print(f"\n📏 Available units: {', '.join(ingredient_info.possible_units)}")
                
        except SpoonacularNotFoundError:
            print_error("Not Found", "Ingredient not found")
            return False
        except SpoonacularError as e:
            print_error("API Error", str(e))
            return False
        except Exception as e:
            print_error("Unexpected Error", str(e))
            return False
    
    wait_for_user("Amazing nutrition data! Ready to explore ingredient substitutions?")
    return True


async def demo_4_ingredient_substitutes():
    """Demo 4: Ingredient Substitutions"""
    print_banner("DEMO 4: Ingredient Substitutions")
    
    print("Let's find substitutes for common cooking ingredients...")
    
    print_step(1, "Finding Substitutes")
    
    async with SpoonacularClient() as client:
        ingredients_to_test = ["butter", "egg", "milk"]
        
        for ingredient_name in ingredients_to_test:
            print(f"\n🔄 Finding substitutes for: {ingredient_name}")
            
            try:
                start_time = time.time()
                response = await client.get_ingredient_substitutes(ingredient_name)
                end_time = time.time()
                
                substitutes = IngredientSubstitutes.from_dict(response)
                
                print(f"⏱️ Found in {end_time - start_time:.2f} seconds")
                
                if substitutes.substitutes:
                    print(f"✅ Found {len(substitutes.substitutes)} substitutes:")
                    for i, substitute in enumerate(substitutes.substitutes, 1):
                        print(f"  {i}. {substitute.name}")
                else:
                    print("❌ No substitutes found")
                
                if substitutes.message:
                    print(f"💡 Note: {substitutes.message}")
                    
            except SpoonacularError as e:
                print_error("API Error", f"Failed to get substitutes for {ingredient_name}: {str(e)}")
                continue
            except Exception as e:
                print_error("Unexpected Error", f"Error processing {ingredient_name}: {str(e)}")
                continue
    
    wait_for_user("Excellent! Ready for the error handling demonstration?")
    return True


async def demo_5_error_handling():
    """Demo 5: Error Handling and Edge Cases"""
    print_banner("DEMO 5: Error Handling & Edge Cases")
    
    print("Let's test how the client handles various error scenarios...")
    
    print_step(1, "Testing Invalid Ingredient ID")
    
    async with SpoonacularClient() as client:
        try:
            print("⏳ Requesting information for invalid ingredient ID (999999)...")
            await client.get_ingredient_information(999999)
            print("❓ Unexpected: No error was raised")
        except SpoonacularNotFoundError as e:
            print_success("Correctly handled 404 Not Found error")
            print(f"   Details: {str(e)}")
        except SpoonacularError as e:
            print_success("Handled API error gracefully")
            print(f"   Details: {str(e)}")
    
    print_step(2, "Testing Empty Search")
    
    async with SpoonacularClient() as client:
        try:
            print("⏳ Searching for empty string...")
            response = await client.search_ingredients("", number=1)
            search_result = IngredientSearchResult.from_dict(response)
            print(f"✅ Handled gracefully: Found {len(search_result.results)} results")
        except SpoonacularError as e:
            print_success("Handled empty search error")
            print(f"   Details: {str(e)}")
    
    print_step(3, "Testing Non-existent Ingredient Substitutes")
    
    async with SpoonacularClient() as client:
        try:
            print("⏳ Getting substitutes for 'xyz123nonsense'...")
            response = await client.get_ingredient_substitutes("xyz123nonsense")
            substitutes = IngredientSubstitutes.from_dict(response)
            print(f"✅ Handled gracefully: Found {len(substitutes.substitutes)} substitutes")
            if substitutes.message:
                print(f"   Message: {substitutes.message}")
        except SpoonacularError as e:
            print_success("Handled invalid ingredient name")
            print(f"   Details: {str(e)}")
    
    wait_for_user("Error handling looks solid! Ready for the final performance test?")
    return True


async def demo_6_performance_test():
    """Demo 6: Performance and Rate Limiting"""
    print_banner("DEMO 6: Performance & Rate Limiting")
    
    print("Let's test performance with multiple concurrent requests...")
    
    print_step(1, "Concurrent Requests Test")
    
    async with SpoonacularClient() as client:
        ingredients = ["apple", "banana", "orange", "chicken", "beef"]
        
        print(f"🚀 Making {len(ingredients)} concurrent searches...")
        start_time = time.time()
        
        try:
            # Make concurrent requests
            tasks = [
                client.search_ingredients(ingredient, number=3)
                for ingredient in ingredients
            ]
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            successful = sum(1 for r in responses if not isinstance(r, Exception))
            failed = len(responses) - successful
            
            print_success(f"Completed in {end_time - start_time:.2f} seconds")
            print(f"📊 Results: {successful} successful, {failed} failed")
            
            if successful > 0:
                avg_time = (end_time - start_time) / len(ingredients)
                print(f"⚡ Average time per request: {avg_time:.2f} seconds")
            
            # Check for rate limiting
            rate_limited = sum(1 for r in responses if isinstance(r, SpoonacularRateLimitError))
            if rate_limited > 0:
                print(f"⚠️  {rate_limited} requests were rate limited")
            
        except Exception as e:
            print_error("Performance Test", str(e))
            return False
    
    print_step(2, "Rate Limiting Demonstration")
    
    print("The client automatically handles rate limiting:")
    print("• 🔄 Tracks requests per minute")
    print("• ⏸️  Automatically waits when approaching limits")
    print("• 🔁 Retries rate-limited requests")
    print("• 📊 Follows Spoonacular's 150 requests/minute limit")
    
    wait_for_user("Performance test complete!")
    return True


async def main():
    """Main demo orchestrator"""
    print_banner("🥘 SPOONACULAR API CLIENT INTERACTIVE DEMO 🥘", 70)
    
    print("This comprehensive demo will walk you through all features of the")
    print("Spoonacular API client, including setup, usage, and error handling.")
    print("\nWhat you'll learn:")
    print("• How to configure the API client")
    print("• Searching for ingredients")
    print("• Getting detailed nutrition information")  
    print("• Finding ingredient substitutes")
    print("• Error handling and edge cases")
    print("• Performance and rate limiting")
    
    wait_for_user("Ready to begin? Let's start with setup...")
    
    demos = [
        ("Configuration & Setup", demo_1_setup_and_config),
        ("Ingredient Search", demo_2_ingredient_search),
        ("Detailed Information", demo_3_ingredient_information),
        ("Ingredient Substitutes", demo_4_ingredient_substitutes),
        ("Error Handling", demo_5_error_handling),
        ("Performance Test", demo_6_performance_test)
    ]
    
    for i, (name, demo_func) in enumerate(demos, 1):
        try:
            success = await demo_func()
            if not success:
                print(f"\n❌ Demo {i} ({name}) failed. Stopping here.")
                break
        except KeyboardInterrupt:
            print("\n\n👋 Demo interrupted by user. Goodbye!")
            break
        except Exception as e:
            print_error("Demo Error", f"Demo {i} failed unexpectedly: {str(e)}")
            break
    else:
        # All demos completed successfully
        print_banner("🎉 ALL DEMOS COMPLETED SUCCESSFULLY! 🎉", 70)
        print("Congratulations! You've successfully:")
        print("✅ Configured the Spoonacular API client")
        print("✅ Searched for ingredients")
        print("✅ Retrieved detailed nutrition information")
        print("✅ Found ingredient substitutes")
        print("✅ Tested error handling")
        print("✅ Verified performance and rate limiting")
        print("\nThe Spoonacular API client is ready for use in your applications!")
        print("For integration into MCP servers, see the upcoming Issue #12.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrupted. Goodbye!")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)