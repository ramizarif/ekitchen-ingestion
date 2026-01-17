#!/usr/bin/env python3
"""
Quick test script for the recipe parser API.
"""
import httpx
import json


def test_parse_endpoint():
    """Test the /parse endpoint with a real recipe URL."""

    # Test URLs
    test_cases = [
        {
            "name": "AllRecipes - Classic Chocolate Chip Cookies",
            "url": "https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/",
            "source_type": "website"
        },
    ]

    for test in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing: {test['name']}")
        print(f"URL: {test['url']}")
        print(f"{'='*60}\n")

        try:
            response = httpx.post(
                "http://localhost:8000/api/v1/parse",
                json={
                    "url": test["url"],
                    "source_type": test["source_type"]
                },
                timeout=30.0
            )

            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ SUCCESS!")
                print(f"Parser Used: {data.get('parser_used')}")
                print(f"Confidence Score: {data.get('confidence_score')}")
                print(f"Processing Time: {data.get('processing_time_ms')}ms")

                recipe = data.get('data', {})
                print(f"\nRecipe Name: {recipe.get('name')}")
                print(f"Servings: {recipe.get('servings')}")
                print(f"Prep Time: {recipe.get('prep_time_minutes')} min")
                print(f"Cook Time: {recipe.get('cook_time_minutes')} min")
                print(f"Total Time: {recipe.get('total_time_minutes')} min")
                print(f"Ingredients Count: {len(recipe.get('ingredients', []))}")
                print(f"Steps Count: {len(recipe.get('steps', []))}")

                if data.get('warnings'):
                    print(f"\n⚠️  Warnings: {', '.join(data['warnings'])}")

                # Print first 3 ingredients
                if recipe.get('ingredients'):
                    print(f"\nFirst 3 Ingredients:")
                    for ing in recipe['ingredients'][:3]:
                        print(f"  - {ing}")

            else:
                error_data = response.json()
                print(f"\n❌ ERROR!")
                print(json.dumps(error_data, indent=2))

        except Exception as e:
            print(f"\n❌ EXCEPTION: {e}")


def test_health_endpoint():
    """Test the health check endpoint."""
    print(f"\n{'='*60}")
    print("Testing Health Endpoint")
    print(f"{'='*60}\n")

    try:
        response = httpx.get("http://localhost:8000/health")
        print(f"Status Code: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")


def test_parsers_list():
    """Test the /parsers endpoint."""
    print(f"\n{'='*60}")
    print("Testing Parsers List Endpoint")
    print(f"{'='*60}\n")

    try:
        response = httpx.get("http://localhost:8000/api/v1/parsers")
        print(f"Status Code: {response.status_code}")
        data = response.json()

        for parser in data['parsers']:
            status_emoji = "✅" if parser['status'] == 'available' else "⏳"
            print(f"{status_emoji} {parser['source_type']}: {parser['status']}")

    except Exception as e:
        print(f"❌ EXCEPTION: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("eKitchen Recipe Parser API - Test Suite")
    print("=" * 60)

    test_health_endpoint()
    test_parsers_list()
    test_parse_endpoint()

    print(f"\n{'='*60}")
    print("Tests Complete!")
    print(f"{'='*60}\n")
