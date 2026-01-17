#!/usr/bin/env python3
"""
Test the fixed ingredient search/create logic to verify HTTP 409 conflicts are resolved
"""

import sys
sys.path.insert(0, 'src/processing')

from direct_recipe_processor import DirectRecipeProcessor

def test_ingredient_409_fix():
    """Test that common ingredients don't cause 409 conflicts"""
    print("🧪 TESTING INGREDIENT 409 FIX")
    print("=" * 50)
    
    # Initialize the processor
    try:
        processor = DirectRecipeProcessor()
        print("✅ DirectRecipeProcessor initialized")
    except Exception as e:
        print(f"❌ Failed to initialize processor: {e}")
        return False
    
    # Test common ingredients that were causing 409s
    test_ingredients = [
        "olive oil",
        "salt", 
        "black pepper",
        "garlic",
        "butter"
    ]
    
    print(f"\n🔍 Testing {len(test_ingredients)} common ingredients for 409 conflicts...")
    
    success_count = 0
    for ingredient in test_ingredients:
        print(f"\n   🧪 Testing: '{ingredient}'")
        
        try:
            # This should either find existing or create new WITHOUT 409 conflicts
            ingredient_id = processor.get_or_create_global_ingredient_enhanced(ingredient)
            
            if ingredient_id:
                print(f"   ✅ Success: '{ingredient}' → {ingredient_id}")
                success_count += 1
            else:
                print(f"   ❌ Failed: '{ingredient}' (returned None)")
                
        except Exception as e:
            if "409" in str(e):
                print(f"   🚨 HTTP 409 CONFLICT: '{ingredient}' - {e}")
            else:
                print(f"   ❌ Other error: '{ingredient}' - {e}")
    
    print(f"\n📊 Results: {success_count}/{len(test_ingredients)} ingredients processed successfully")
    
    if success_count == len(test_ingredients):
        print("🎉 All ingredients processed without 409 conflicts!")
        print("✅ The fix is working correctly")
        return True
    else:
        print("🚨 Some ingredients still causing issues")
        return False

if __name__ == "__main__":
    test_ingredient_409_fix()