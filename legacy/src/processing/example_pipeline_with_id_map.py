#!/usr/bin/env python3
"""
Example Pipeline Using Enhanced Ingredient ID Mapping

This demonstrates how to use the enhanced DirectIngredientProcessor
with clear ingredient ID mapping to avoid "ingredient doesn't exist" errors.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.processing.ingredient_processor_direct import DirectIngredientProcessor, load_env_file

def example_recipe_pipeline():
    """
    Example pipeline showing how to process ingredients and create recipe with proper ID mapping
    """
    print("🚀 Starting Recipe Pipeline with Enhanced Ingredient ID Mapping")
    print("="*70)
    
    # Initialize processor
    processor = DirectIngredientProcessor()
    
    # Load credentials
    env_file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'local.env')
    env_vars = load_env_file(env_file_path)
    
    admin_email = env_vars.get('EKITCHEN_ADMIN_EMAIL')
    admin_password = env_vars.get('EKITCHEN_ADMIN_PASSWORD')
    
    if not admin_email or not admin_password:
        print("❌ Missing eKitchen credentials in local.env file")
        return None
    
    # Authenticate
    if not processor.authenticate_ekitchen(admin_email, admin_password):
        print("❌ Authentication failed - cannot proceed")
        return None
    
    # Example recipe data
    recipe_data = {
        "name": "Quick Thai Coconut Soup",
        "ingredients": [
            "2 cups chicken broth",
            "1 can coconut milk",
            "2 tablespoons red curry paste",
            "1 pound shrimp, peeled",
            "1 cup mushrooms, sliced",
            "2 tablespoons fish sauce",
            "1 tablespoon lime juice",
            "2 teaspoons brown sugar"
        ],
        "servings": 4
    }
    
    print(f"📋 Processing recipe: {recipe_data['name']}")
    print(f"🥘 Ingredients: {len(recipe_data['ingredients'])}")
    
    # STEP 1: Process ingredients and get clear ID mapping
    print(f"\n🔥 STEP 1: Processing ingredients...")
    processed_ingredients, ingredient_id_map = processor.process_recipe_ingredients(recipe_data['ingredients'])
    
    # STEP 2: Verify the ID mapping is complete
    print(f"\n🔍 STEP 2: Verifying ingredient ID mapping...")
    missing_ids = []
    for ingredient_name in ingredient_id_map.keys():
        if not ingredient_id_map[ingredient_name]:
            missing_ids.append(ingredient_name)
    
    if missing_ids:
        print(f"❌ Missing IDs for: {missing_ids}")
        print("   Recipe creation will fail - aborting pipeline")
        return None
    else:
        print(f"✅ All {len(ingredient_id_map)} ingredients have valid IDs")
    
    # STEP 3: Format ingredients for recipe creation
    print(f"\n📦 STEP 3: Formatting ingredients for recipe creation...")
    formatted_ingredients = processor.format_ingredients_for_recipe(recipe_data['ingredients'], ingredient_id_map)
    
    print(f"✅ Formatted {len(formatted_ingredients)} ingredients with valid IDs")
    
    # STEP 4: Calculate nutrition
    print(f"\n🧮 STEP 4: Calculating recipe nutrition...")
    nutrition = processor.calculate_recipe_nutrition_from_map(
        recipe_data['ingredients'], 
        processed_ingredients, 
        ingredient_id_map, 
        recipe_data['servings']
    )
    
    # STEP 5: Prepare complete recipe data for eKitchen
    print(f"\n📋 STEP 5: Preparing complete recipe data...")
    
    ekitchen_recipe_data = {
        "name": recipe_data['name'],
        "description": f"Delicious {recipe_data['name']} with {len(formatted_ingredients)} ingredients",
        "num_servings": recipe_data['servings'],
        "prep_time_minutes": 15,
        "cook_time_minutes": 20,
        "total_time_minutes": 35,
        "difficulty": "Easy",
        "cuisine": "Thai",
        "ingredients": formatted_ingredients,  # Uses correct ingredient IDs
        "steps": [
            {"template": "Heat broth and coconut milk in a large pot"},
            {"template": "Add curry paste and stir until dissolved"},
            {"template": "Add shrimp and mushrooms, cook until shrimp is pink"},
            {"template": "Season with fish sauce, lime juice, and brown sugar"},
            {"template": "Serve hot and enjoy!"}
        ],
        "tag_names": ["Thai", "Soup", "Seafood", "Quick", "Easy"],
        # Nutrition from calculated values
        "calories": nutrition['calories'],
        "protein": nutrition['protein'],
        "fat": nutrition['fat'],
        "carbohydrates": nutrition['carbohydrates'],
        "sugar": nutrition['sugar']
    }
    
    print(f"✅ Recipe data prepared with {len(formatted_ingredients)} valid ingredient mappings")
    
    # STEP 6: Show the final ingredient mapping for verification
    print(f"\n🗺️  FINAL INGREDIENT ID MAPPING:")
    print("="*50)
    for ingredient_name, ingredient_id in ingredient_id_map.items():
        print(f"   {ingredient_name:<25} → {ingredient_id}")
    print("="*50)
    
    print(f"\n✅ PIPELINE COMPLETE!")
    print(f"📊 Summary:")
    print(f"   Recipe: {recipe_data['name']}")
    print(f"   Ingredients processed: {len(ingredient_id_map)}")
    print(f"   Ingredients with valid IDs: {len(formatted_ingredients)}")
    print(f"   Success rate: {(len(formatted_ingredients) / len(recipe_data['ingredients']) * 100):.1f}%")
    print(f"   Ready for eKitchen recipe creation: ✅")
    
    return ekitchen_recipe_data, ingredient_id_map

def demonstrate_id_mapping_benefits():
    """
    Demonstrate the benefits of the clear ID mapping system
    """
    print("\n🎯 ID MAPPING BENEFITS:")
    print("="*50)
    print("✅ BEFORE: Unclear ingredient data flow")
    print("   - Ingredient IDs buried in complex data structures")
    print("   - Hard to verify all ingredients have valid IDs")
    print("   - Recipe creation fails with 'ingredient doesn't exist' errors")
    print()
    print("✅ AFTER: Clear ingredient ID mapping")
    print("   - Simple dict: ingredient_name → ingredient_id")
    print("   - Easy verification of complete ID mapping")
    print("   - Pipeline fails early if IDs are missing")
    print("   - Recipe creation guaranteed to work with valid IDs")
    print("="*50)

if __name__ == "__main__":
    # Run the example pipeline
    result = example_recipe_pipeline()
    
    if result:
        recipe_data, id_map = result
        print(f"\n🎉 Recipe ready for eKitchen creation!")
        print(f"📦 Total ingredients mapped: {len(id_map)}")
        
        # Show the mapping benefits
        demonstrate_id_mapping_benefits()
    else:
        print(f"\n❌ Pipeline failed - check ingredient processing")