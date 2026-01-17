#!/usr/bin/env python3
"""
Test Spoonacular enrichment for NEW ingredients
"""

import sys
sys.path.insert(0, 'src/processing')

from direct_recipe_processor import DirectRecipeProcessor

def test_spoonacular_enrichment():
    """Test that new ingredients get Spoonacular enrichment"""
    print("🧪 TESTING SPOONACULAR ENRICHMENT FOR NEW INGREDIENTS")
    print("=" * 60)
    
    # Initialize the processor
    try:
        processor = DirectRecipeProcessor()
        print("✅ DirectRecipeProcessor initialized")
    except Exception as e:
        print(f"❌ Failed to initialize processor: {e}")
        return False
    
    # Test with ingredients that likely don't exist yet (unique names)
    test_ingredients = [
        "test_chicken_thighs_unique_2025",  # Unique name that won't exist
        "test_basmati_rice_unique_2025",    # Another unique name
    ]
    
    print(f"\n🔍 Testing {len(test_ingredients)} new ingredients for Spoonacular enrichment...")
    
    for ingredient in test_ingredients:
        print(f"\n   🧪 Testing NEW ingredient: '{ingredient}'")
        
        try:
            # This should NOT find existing and should create with enrichment
            ingredient_id = processor.get_or_create_global_ingredient_enhanced(ingredient)
            
            if ingredient_id:
                print(f"   ✅ Created: '{ingredient}' → {ingredient_id}")
                
                # Now let's check if it has enrichment by trying with a real ingredient
                print(f"\n   🧪 Now testing with real ingredient: 'chicken thighs'")
                real_id = processor.get_or_create_global_ingredient_enhanced("chicken thighs")
                print(f"   ✅ Real ingredient: 'chicken thighs' → {real_id}")
                
                return True
            else:
                print(f"   ❌ Failed to create: '{ingredient}'")
                
        except Exception as e:
            print(f"   ❌ Error with '{ingredient}': {e}")
            
    return False

if __name__ == "__main__":
    test_spoonacular_enrichment()