#!/usr/bin/env python3
"""
Comprehensive Recipe Ingredient Rebuild Script

This script implements a "clean slate" approach to fix corrupted ingredient data:
1. Clear all recipe_ingredients and global_ingredients
2. Re-scrape each recipe from its URL
3. Use AI to standardize ingredient names
4. Create proper global ingredients with deduplication
5. Create correct recipe_ingredient associations
6. Regenerate recipe steps using the API endpoint

Usage:
    python comprehensive_ingredient_rebuild.py --dry-run  # Preview changes
    python comprehensive_ingredient_rebuild.py --live     # Actually rebuild
    python comprehensive_ingredient_rebuild.py --recipe-id d2k09mo5vf6c73cbrh60  # Single recipe test
"""

import sys
import os
import argparse
import json
import time
import requests
import re
from typing import List, Dict, Any, Optional
from openai import OpenAI

# Add the processing directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'processing'))

from ingredient_processor_direct import DirectIngredientProcessor
from direct_recipe_processor import DirectRecipeProcessor


class ComprehensiveIngredientRebuilder:
    """Complete ingredient data rebuild with clean slate approach"""
    
    def __init__(self):
        print("🔧 Initializing comprehensive rebuild system...")
        
        # Initialize processors
        self.ingredient_processor = DirectIngredientProcessor()
        self.recipe_processor = DirectRecipeProcessor()
        
        # Initialize OpenAI for AI standardization
        try:
            # Load OpenAI API key from environment config
            env_config = self.ingredient_processor._load_env_config()
            openai_api_key = env_config.get('OPENAI_API_KEY', '')
            
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY not found in environment configuration")
                
            self.openai_client = OpenAI(api_key=openai_api_key)
            print("✅ OpenAI client initialized")
        except Exception as e:
            print(f"❌ Failed to initialize OpenAI: {e}")
            raise
        
        # Statistics tracking
        self.stats = {
            'recipes_processed': 0,
            'recipes_skipped': 0,
            'global_ingredients_created': 0,
            'recipe_ingredients_created': 0,
            'steps_regenerated': 0,
            'errors': []
        }
        
        # Cache for global ingredients to avoid duplicates
        self.global_ingredients_cache = {}
        
    def authenticate(self) -> bool:
        """Authenticate with eKitchen API"""
        print("🔐 Authenticating with eKitchen...")
        
        # Load configuration
        env_config = self.ingredient_processor._load_env_config()
        admin_email = env_config.get('EKITCHEN_ADMIN_EMAIL', '')
        admin_password = env_config.get('EKITCHEN_ADMIN_PASSWORD', '')
        
        success = self.ingredient_processor.authenticate_ekitchen(admin_email, admin_password)
        if success:
            print("✅ eKitchen authentication successful")
            return True
        else:
            print("❌ eKitchen authentication failed")
            return False
    
    
    def get_recipes_needing_rebuild(self) -> List[Dict[str, Any]]:
        """Get recipes that have URLs and need ingredient rebuilding (no recipe_ingredients)"""
        try:
            url = f"{self.ingredient_processor.ekitchen_base_url}/global-recipes"
            headers = {
                'Authorization': f'Bearer {self.ingredient_processor.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Get all recipes
            params = {'limit': 1000}  # Adjust as needed
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                recipes = response.json()
                
                print(f"📋 Checking {len(recipes)} recipes for rebuild eligibility...")
                
                recipes_needing_rebuild = []
                recipes_with_urls = 0
                recipes_with_ingredients = 0
                
                for i, recipe in enumerate(recipes, 1):
                    if i % 50 == 0:  # Progress indicator
                        print(f"   📊 Checked {i}/{len(recipes)} recipes...")
                    
                    recipe_id = recipe.get('id')
                    recipe_url = recipe.get('inspired_by_url', recipe.get('url', ''))
                    
                    # Skip recipes without URLs
                    if not recipe_url:
                        continue
                    
                    recipes_with_urls += 1
                    
                    # Check if recipe has ingredients
                    if self.recipe_has_ingredients(recipe_id):
                        recipes_with_ingredients += 1
                        continue
                    
                    # This recipe needs rebuilding
                    recipes_needing_rebuild.append(recipe)
                
                print(f"✅ Analysis complete:")
                print(f"   📋 Total recipes: {len(recipes)}")
                print(f"   🔗 With URLs: {recipes_with_urls}")
                print(f"   🥘 Already have ingredients: {recipes_with_ingredients}")
                print(f"   🔧 Need rebuilding: {len(recipes_needing_rebuild)}")
                
                return recipes_needing_rebuild
            else:
                print(f"❌ Failed to get recipes: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error fetching recipes: {e}")
            return []
    
    def recipe_has_ingredients(self, recipe_id: str) -> bool:
        """Check if a recipe already has recipe_ingredients"""
        try:
            # Check if recipe has ingredients by getting the recipe and checking ingredients count
            url = f"{self.ingredient_processor.ekitchen_base_url}/global-recipes/{recipe_id}"
            headers = {
                'Authorization': f'Bearer {self.ingredient_processor.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                recipe_data = response.json()
                ingredients = recipe_data.get('ingredients', [])
                return len(ingredients) > 0
            else:
                # If we can't check, assume it needs rebuilding to be safe
                return False
                
        except Exception as e:
            # If we can't check, assume it needs rebuilding to be safe
            return False
    
    def get_all_recipes_with_urls(self) -> List[Dict[str, Any]]:
        """Get all recipes that have URLs (for force rebuild mode)"""
        try:
            url = f"{self.ingredient_processor.ekitchen_base_url}/global-recipes"
            headers = {
                'Authorization': f'Bearer {self.ingredient_processor.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Get all recipes
            params = {'limit': 1000}  # Adjust as needed
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                recipes = response.json()
                
                # Filter recipes that have URLs
                recipes_with_urls = []
                for recipe in recipes:
                    recipe_url = recipe.get('inspired_by_url', recipe.get('url', ''))
                    if recipe_url:
                        recipes_with_urls.append(recipe)
                
                print(f"✅ Found {len(recipes_with_urls)} recipes with URLs out of {len(recipes)} total")
                return recipes_with_urls
            else:
                print(f"❌ Failed to get recipes: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error fetching recipes: {e}")
            return []
    
    def parse_ingredient_quantity_and_unit(self, ingredient_text: str) -> Dict[str, str]:
        """Parse quantity and unit from ingredient text using regex patterns"""
        
        # Common unit patterns
        unit_patterns = {
            # Volume
            r'\b(cups?|cup)\b': 'cup',
            r'\b(tablespoons?|tablespoon|tbsp|tbs)\b': 'tablespoon', 
            r'\b(teaspoons?|teaspoon|tsp)\b': 'teaspoon',
            r'\b(quarts?|quart|qt)\b': 'quart',
            r'\b(pints?|pint|pt)\b': 'pint',
            r'\b(gallons?|gallon|gal)\b': 'gallon',
            r'\b(fluid ounces?|fluid ounce|fl oz|floz)\b': 'fluid ounce',
            r'\b(liters?|liter|litres?|litre|l)\b': 'liter',
            r'\b(milliliters?|milliliter|ml)\b': 'milliliter',
            
            # Weight
            r'\b(pounds?|pound|lbs?|lb)\b': 'pound',
            r'\b(ounces?|ounce|oz)\b': 'ounce', 
            r'\b(grams?|gram|g)\b': 'gram',
            r'\b(kilograms?|kilogram|kg)\b': 'kilogram',
            
            # Count/pieces
            r'\b(pieces?|piece)\b': 'piece',
            r'\b(slices?|slice)\b': 'slice',
            r'\b(cloves?|clove)\b': 'clove',
            r'\b(stalks?|stalk)\b': 'stalk',
            r'\b(heads?|head)\b': 'head',
            r'\b(bunches?|bunch)\b': 'bunch',
            r'\b(strips?|strip)\b': 'strip',
            
            # Special
            r'\b(cans?|can)\b': 'can',
            r'\b(packages?|package|pkg)\b': 'package',
            r'\b(jars?|jar)\b': 'jar',
            r'\b(bottles?|bottle)\b': 'bottle',
            r'\b(pinch|pinches)\b': 'pinch',
            r'\b(dash|dashes)\b': 'dash',
        }
        
        # Quantity patterns (including fractions and decimals)
        quantity_patterns = [
            r'^(\d+(?:\.\d+)?)\s*',  # Decimal numbers
            r'^(\d+/\d+)\s*',        # Fractions like 1/2
            r'^(\d+\s+\d+/\d+)\s*',  # Mixed numbers like 1 1/2
            r'^(one|two|three|four|five|six|seven|eight|nine|ten)\s*',  # Written numbers
        ]
        
        # Try to extract quantity
        quantity = "1.0"
        remaining_text = ingredient_text.lower().strip()
        
        for pattern in quantity_patterns:
            match = re.match(pattern, remaining_text, re.IGNORECASE)
            if match:
                quantity_str = match.group(1)
                
                # Convert fractions to decimals
                if '/' in quantity_str:
                    if ' ' in quantity_str:  # Mixed number like "1 1/2"
                        parts = quantity_str.split()
                        whole = float(parts[0])
                        frac_parts = parts[1].split('/')
                        fraction = float(frac_parts[0]) / float(frac_parts[1])
                        quantity = str(whole + fraction)
                    else:  # Simple fraction like "1/2"
                        frac_parts = quantity_str.split('/')
                        quantity = str(float(frac_parts[0]) / float(frac_parts[1]))
                else:
                    # Handle written numbers
                    written_numbers = {
                        'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
                        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10'
                    }
                    if quantity_str.lower() in written_numbers:
                        quantity = written_numbers[quantity_str.lower()]
                    else:
                        quantity = quantity_str
                
                # Remove the quantity from the text for unit parsing
                remaining_text = remaining_text[match.end():].strip()
                break
        
        # Try to extract unit (prioritize more specific units first)
        unit = "serving"  # Default
        
        # Sort patterns by specificity (longer patterns first)
        sorted_patterns = sorted(unit_patterns.items(), key=lambda x: len(x[1]), reverse=True)
        
        for pattern, unit_name in sorted_patterns:
            if re.search(pattern, remaining_text, re.IGNORECASE):
                unit = unit_name
                break
        
        return {
            'quantity': quantity,
            'unit': unit
        }
    
    def pluralize_to_singular(self, ingredient_name: str) -> str:
        """Convert plural ingredient names to singular form"""
        
        # Common plural patterns and their singular forms
        pluralization_rules = [
            # Irregular plurals
            (r'\b(children)\b', 'child'),
            (r'\b(feet)\b', 'foot'),
            (r'\b(geese)\b', 'goose'),
            (r'\b(men)\b', 'man'),
            (r'\b(mice)\b', 'mouse'),
            (r'\b(people)\b', 'person'),
            (r'\b(teeth)\b', 'tooth'),
            (r'\b(women)\b', 'woman'),
            
            # Food-specific irregular plurals
            (r'\b(leaves)\b', 'leaf'),
            (r'\b(loaves)\b', 'loaf'),
            (r'\b(halves)\b', 'half'),
            (r'\b(knives)\b', 'knife'),
            (r'\b(lives)\b', 'life'),
            (r'\b(wives)\b', 'wife'),
            
            # -ies endings
            (r'\b(\w+)ies\b', r'\1y'),  # berries -> berry, cherries -> cherry
            
            # -ves endings  
            (r'\b(\w+)ves\b', r'\1f'),   # calves -> calf
            
            # -ses endings
            (r'\b(\w+)ses\b', r'\1s'),   # glasses -> glass, masses -> mass
            
            # -es endings (after s, sh, ch, x, z)
            (r'\b(\w+[sshchxz])es\b', r'\1'),  # dishes -> dish, boxes -> box
            
            # -oes endings
            (r'\b(\w+)oes\b', r'\1o'),   # tomatoes -> tomato, potatoes -> potato
            
            # Regular -s endings (but preserve some common exceptions)
            (r'\b(\w+)s\b', r'\1'),      # apples -> apple, carrots -> carrot
        ]
        
        # Words that should stay plural (exceptions)
        exceptions = {
            'green beans', 'black beans', 'kidney beans', 'lima beans', 'pinto beans',
            'brussels sprouts', 'bean sprouts',
            'bread crumbs', 'pine nuts', 'mixed nuts',
            'rolled oats', 'steel cut oats',
            'corn flakes', 'wheat germ',
            'chili flakes', 'red pepper flakes',
            'sesame seeds', 'sunflower seeds', 'pumpkin seeds',
            'chocolate chips', 'butterscotch chips',
            'panko breadcrumbs', 'seasoned breadcrumbs'
        }
        
        ingredient_lower = ingredient_name.lower().strip()
        
        # Check if it's an exception that should stay plural
        if ingredient_lower in exceptions:
            return ingredient_name
        
        # Apply pluralization rules
        result = ingredient_name
        for pattern, replacement in pluralization_rules:
            new_result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
            if new_result != result:
                result = new_result
                break  # Only apply first matching rule
        
        return result
    
    def standardize_ingredient_name_with_ai(self, ingredient_text: str) -> str:
        """Use AI to create standardized global ingredient name"""
        try:
            prompt = f"""Create a standardized global ingredient name from this recipe ingredient:
"{ingredient_text}"

RULES for global ingredient names:
1. Remove quantities: "2 cups flour" → "flour"  
2. Remove preparations: "chopped onions" → "onions"
3. Remove descriptors: "fresh basil" → "basil"
4. Remove conditions: "thawed peas" → "peas"
5. Keep essential qualifiers: "red bell pepper" → "red bell pepper"
6. Use singular form when possible: "eggs" → "egg" (but "green beans" stays "green beans")
7. Remove brand names unless essential
8. Remove measurements: "1-inch pieces celery" → "celery"

Return ONLY the standardized name, nothing else.

Examples:
"2 cups all-purpose flour" → "all purpose flour"
"1 large onion, chopped" → "onion"  
"fresh basil leaves" → "basil"
"boneless chicken breast" → "chicken breast"
"1 can (14 oz) diced tomatoes" → "diced tomatoes"
"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.1
            )
            
            standardized_name = response.choices[0].message.content.strip().lower()
            
            # Apply singularization to the AI result
            singular_name = self.pluralize_to_singular(standardized_name)
            
            return singular_name
            
        except Exception as e:
            print(f"⚠️ AI standardization failed for '{ingredient_text}': {e}")
            # Fallback: basic cleanup
            return ingredient_text.split(',')[0].strip().lower()
    
    def get_or_create_global_ingredient(self, standardized_name: str, dry_run: bool = True) -> Optional[str]:
        """Get existing global ingredient or create new one, with caching"""
        
        # Check cache first
        if standardized_name in self.global_ingredients_cache:
            return self.global_ingredients_cache[standardized_name]
        
        if dry_run:
            # In dry run, simulate creating ingredient
            fake_id = f"simulated_{len(self.global_ingredients_cache)}"
            self.global_ingredients_cache[standardized_name] = fake_id
            print(f"   🧪 DRY RUN: Would create/find global ingredient '{standardized_name}' → {fake_id}")
            return fake_id
        
        try:
            base_url = self.ingredient_processor.ekitchen_base_url
            headers = {
                'Authorization': f'Bearer {self.ingredient_processor.access_token}',
                'Content-Type': 'application/json'
            }
            
            # First, search for existing ingredient  
            search_url = f"{base_url}/global-ingredients/search"
            search_params = {'q': standardized_name, 'limit': 10, 'offset': 0}
            response = requests.get(search_url, headers=headers, params=search_params, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                
                # Handle both possible response formats
                if 'ingredients' in response_data:
                    results = response_data['ingredients']  # MCP format
                else:
                    results = response_data  # Direct array format
                    
                print(f"   🔍 Search found {len(results)} results for '{standardized_name}'")
                # Look for exact match
                for ingredient in results:
                    ingredient_name = ingredient.get('name', '').lower().strip()
                    search_name = standardized_name.lower().strip()
                    print(f"   📝 Comparing: '{ingredient_name}' vs '{search_name}'")
                    if ingredient_name == search_name:
                        ingredient_id = ingredient.get('id')
                        self.global_ingredients_cache[standardized_name] = ingredient_id
                        print(f"   ♻️ Found existing global ingredient '{standardized_name}' → {ingredient_id}")
                        return ingredient_id
                        
                # If no exact match, show what we found
                if results:
                    print(f"   ⚠️ No exact match found. Available: {[r.get('name') for r in results[:3]]}")
            else:
                print(f"   ❌ Search failed with status {response.status_code}")
                # Debug: show response content
                try:
                    print(f"   📄 Response: {response.text[:200]}")
                except:
                    pass
            
            # If no exact match found, create new ingredient
            create_url = f"{base_url}/global-ingredients"
            ingredient_data = {
                'name': standardized_name,
                'category': 'other',  # Default category
                'needs_enrichment': True  # Mark for later enrichment
            }
            
            response = requests.post(create_url, json=ingredient_data, headers=headers, timeout=30)
            
            if response.status_code in [200, 201]:
                ingredient = response.json()
                ingredient_id = ingredient.get('id')
                self.global_ingredients_cache[standardized_name] = ingredient_id
                self.stats['global_ingredients_created'] += 1
                print(f"   ✨ Created new global ingredient '{standardized_name}' → {ingredient_id}")
                return ingredient_id
            elif response.status_code == 409:
                print(f"   ⚠️ Ingredient '{standardized_name}' already exists (409). Attempting to find it...")
                # Try to search again more aggressively
                broad_search_params = {'q': standardized_name, 'limit': 50, 'offset': 0}
                broad_response = requests.get(search_url, headers=headers, params=broad_search_params, timeout=30)
                if broad_response.status_code == 200:
                    broad_response_data = broad_response.json()
                    # Handle response format
                    if 'ingredients' in broad_response_data:
                        broad_results = broad_response_data['ingredients']
                    else:
                        broad_results = broad_response_data
                    for ingredient in broad_results:
                        if ingredient.get('name', '').lower().strip() == standardized_name.lower().strip():
                            ingredient_id = ingredient.get('id')
                            self.global_ingredients_cache[standardized_name] = ingredient_id
                            print(f"   ♻️ Found existing ingredient after 409: '{standardized_name}' → {ingredient_id}")
                            return ingredient_id
                print(f"   ❌ Could not find existing ingredient '{standardized_name}' despite 409 error")
                return None
            else:
                print(f"❌ Failed to create global ingredient '{standardized_name}': {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error details: {error_detail}")
                except:
                    print(f"   Error response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error with global ingredient '{standardized_name}': {e}")
            return None
    
    def create_recipe_ingredient_association(self, 
                                           recipe_id: str,
                                           global_ingredient_id: str, 
                                           quantity: str,
                                           unit: str,
                                           reference_as: str,
                                           dry_run: bool = True) -> bool:
        """Create recipe_ingredient association"""
        
        if dry_run:
            print(f"   🧪 DRY RUN: Would create recipe ingredient: {reference_as} → {global_ingredient_id}")
            return True
        
        try:
            # This would use your recipe ingredient creation endpoint
            # For now, we'll add to the recipe's ingredients list and update via UpdateGlobalRecipe
            return True
            
        except Exception as e:
            print(f"❌ Error creating recipe ingredient: {e}")
            return False
    
    def regenerate_recipe_steps(self, recipe_id: str, dry_run: bool = True) -> bool:
        """Regenerate recipe steps using the API endpoint"""
        
        if dry_run:
            print(f"   🧪 DRY RUN: Would regenerate steps for recipe {recipe_id}")
            return True
        
        try:
            url = f"{self.ingredient_processor.ekitchen_base_url}/admin/global-recipes/{recipe_id}/regenerate-steps"
            headers = {
                'Authorization': f'Bearer {self.ingredient_processor.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, timeout=60)
            
            if response.status_code in [200, 204]:
                self.stats['steps_regenerated'] += 1
                print(f"   ✅ Successfully regenerated steps for recipe {recipe_id}")
                return True
            else:
                error_msg = f"Failed to regenerate steps for recipe {recipe_id}: {response.status_code}"
                print(f"   ❌ {error_msg}")
                self.stats['errors'].append(error_msg)
                return False
                
        except Exception as e:
            error_msg = f"Error regenerating steps for recipe {recipe_id}: {e}"
            print(f"   ❌ {error_msg}")
            self.stats['errors'].append(error_msg)
            return False
    
    def process_single_recipe(self, recipe: Dict[str, Any], dry_run: bool = True) -> bool:
        """Process a single recipe: scrape, standardize ingredients, create associations"""
        
        recipe_id = recipe.get('id')
        recipe_name = recipe.get('name', 'Unknown')
        recipe_url = recipe.get('inspired_by_url', recipe.get('url', ''))
        
        print(f"\n{'='*60}")
        print(f"🍽️ Processing Recipe: {recipe_name}")
        print(f"🆔 ID: {recipe_id}")
        print(f"🔗 URL: {recipe_url}")
        
        if not recipe_url:
            print("⚠️ No URL found - skipping")
            self.stats['recipes_skipped'] += 1
            return False
        
        try:
            # Step 1: Re-scrape the recipe
            print(f"\n📋 Step 1: Re-scraping recipe...")
            scraped_data = self.recipe_processor.scrape_recipe_from_url(recipe_url)
            
            if not scraped_data or not scraped_data.get('ingredients'):
                print("❌ Failed to scrape ingredients")
                self.stats['recipes_skipped'] += 1
                return False
            
            scraped_ingredients = scraped_data['ingredients']
            print(f"✅ Scraped {len(scraped_ingredients)} ingredients")
            
            # Step 2: Process each ingredient
            print(f"\n📋 Step 2: Processing ingredients...")
            recipe_ingredients_list = []
            
            for i, scraped_ingredient in enumerate(scraped_ingredients, 1):
                # Handle both string ingredients and dict ingredients
                if isinstance(scraped_ingredient, str):
                    ingredient_text = scraped_ingredient
                    # Parse quantity and unit from the text
                    parsed = self.parse_ingredient_quantity_and_unit(ingredient_text)
                    quantity = parsed['quantity']
                    unit = parsed['unit']
                else:
                    ingredient_text = scraped_ingredient.get('name', '')
                    quantity = scraped_ingredient.get('quantity', '1.0')
                    unit = scraped_ingredient.get('unit', 'serving')
                
                print(f"\n   🔍 Processing ingredient {i}: '{ingredient_text}'")
                print(f"   📏 Parsed: {quantity} {unit}")
                
                # Standardize the ingredient name with AI (includes singularization)
                standardized_name = self.standardize_ingredient_name_with_ai(ingredient_text)
                print(f"   🤖 AI standardized + singularized: '{ingredient_text}' → '{standardized_name}'")
                
                # Get or create global ingredient
                global_ingredient_id = self.get_or_create_global_ingredient(standardized_name, dry_run)
                
                if global_ingredient_id:
                    # Create recipe ingredient association
                    recipe_ingredient = {
                        "ingredient_id": global_ingredient_id,
                        "quantity": quantity,
                        "unit": unit,
                        "reference_as": ingredient_text,  # Preserve original recipe context
                        "extra_comment": "",
                        "section_name": ""
                    }
                    recipe_ingredients_list.append(recipe_ingredient)
                    self.stats['recipe_ingredients_created'] += 1
                else:
                    print(f"   ❌ Failed to process ingredient: {ingredient_text}")
            
            # Step 3: Update recipe with new ingredients list
            if recipe_ingredients_list and not dry_run:
                print(f"\n📋 Step 3: Updating recipe with {len(recipe_ingredients_list)} ingredients...")
                
                url = f"{self.ingredient_processor.ekitchen_base_url}/global-recipes/{recipe_id}"
                headers = {
                    'Authorization': f'Bearer {self.ingredient_processor.access_token}',
                    'Content-Type': 'application/json'
                }
                
                update_data = {
                    "id": recipe_id,
                    "ingredients": recipe_ingredients_list
                }
                
                response = requests.put(url, json=update_data, headers=headers, timeout=30)
                
                if response.status_code not in [200, 204]:
                    print(f"   ❌ Failed to update recipe ingredients: {response.status_code}")
                    return False
                print(f"   ✅ Updated recipe with clean ingredients")
            
            # Step 4: Regenerate recipe steps
            print(f"\n📋 Step 4: Regenerating recipe steps...")
            if not self.regenerate_recipe_steps(recipe_id, dry_run):
                print("   ⚠️ Step regeneration failed, but continuing...")
            
            self.stats['recipes_processed'] += 1
            print(f"✅ Successfully processed recipe: {recipe_name}")
            return True
            
        except Exception as e:
            error_msg = f"Error processing recipe {recipe_name}: {e}"
            print(f"❌ {error_msg}")
            self.stats['errors'].append(error_msg)
            self.stats['recipes_skipped'] += 1
            return False
    
    def rebuild_all_ingredients(self, dry_run: bool = True, recipe_id: Optional[str] = None, force_all: bool = False) -> Dict[str, Any]:
        """Main method: rebuild ingredient data for recipes that need it
        
        Args:
            dry_run: Preview changes without making them
            recipe_id: Process specific recipe only (for testing)
            force_all: Process all recipes regardless of current ingredient state
        """
        
        print(f"🚀 Starting comprehensive ingredient rebuild...")
        print(f"📋 Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        if force_all:
            print(f"⚠️ Force mode: Will process ALL recipes regardless of current state")
        
        start_time = time.time()
        
        # Authenticate
        if not self.authenticate():
            return {"success": False, "error": "Authentication failed"}
        
        # If testing single recipe
        if recipe_id:
            print(f"🎯 Testing single recipe: {recipe_id}")
            
            # Get specific recipe
            try:
                url = f"{self.ingredient_processor.ekitchen_base_url}/global-recipes/{recipe_id}"
                headers = {
                    'Authorization': f'Bearer {self.ingredient_processor.access_token}',
                    'Content-Type': 'application/json'
                }
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    recipe = response.json()
                    success = self.process_single_recipe(recipe, dry_run)
                    
                    return {
                        "success": success,
                        "test_mode": "single_recipe",
                        "recipe_id": recipe_id,
                        "stats": self.stats,
                        "duration": time.time() - start_time
                    }
                else:
                    return {"success": False, "error": f"Recipe {recipe_id} not found"}
                    
            except Exception as e:
                return {"success": False, "error": f"Error fetching recipe {recipe_id}: {e}"}
        
        # Full rebuild process
        try:
            # Step 1: Get recipes to process
            print(f"\n{'='*60}")
            if force_all:
                print("📋 STEP 1: Getting ALL recipes with URLs (force mode)")
                recipes = self.get_all_recipes_with_urls()
            else:
                print("📋 STEP 1: Finding recipes that need ingredient rebuilding")
                recipes = self.get_recipes_needing_rebuild()
            
            if not recipes:
                return {"success": True, "message": "No recipes need rebuilding - all recipes already have ingredients"}
            
            print(f"✅ Found {len(recipes)} recipes to process")
            
            # Step 2: Process each recipe
            print(f"\n{'='*60}")
            print("🔄 STEP 2: Processing recipes")
            
            for i, recipe in enumerate(recipes, 1):
                print(f"\n--- Processing {i}/{len(recipes)} ---")
                self.process_single_recipe(recipe, dry_run)
                
                # Rate limiting
                if not dry_run:
                    time.sleep(1)
            
            # Final summary
            duration = time.time() - start_time
            print(f"\n{'='*60}")
            print("📊 REBUILD COMPLETE!")
            print(f"⏱️  Duration: {duration:.1f} seconds")
            print(f"✅ Recipes processed: {self.stats['recipes_processed']}")
            print(f"⏭️  Recipes skipped: {self.stats['recipes_skipped']}")
            print(f"🌟 Global ingredients created: {self.stats['global_ingredients_created']}")
            print(f"🔗 Recipe ingredients created: {self.stats['recipe_ingredients_created']}")
            print(f"⚡ Steps regenerated: {self.stats['steps_regenerated']}")
            print(f"❌ Errors: {len(self.stats['errors'])}")
            
            if self.stats['errors']:
                print("\n🚨 ERRORS:")
                for error in self.stats['errors']:
                    print(f"   - {error}")
            
            return {
                "success": True,
                "stats": self.stats,
                "duration": duration
            }
            
        except Exception as e:
            error_msg = f"Fatal error during rebuild: {e}"
            print(f"💥 {error_msg}")
            return {"success": False, "error": error_msg}


def main():
    parser = argparse.ArgumentParser(description='Comprehensive Recipe Ingredient Rebuild')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Preview changes without making them (default)')
    parser.add_argument('--live', action='store_true',
                       help='Actually perform the rebuild')
    parser.add_argument('--recipe-id', type=str,
                       help='Test on a single recipe by ID')
    parser.add_argument('--force-all', action='store_true',
                       help='Process ALL recipes regardless of current ingredient state')
    
    args = parser.parse_args()
    
    # Default to dry run unless --live is specified
    dry_run = not args.live
    
    rebuilder = ComprehensiveIngredientRebuilder()
    result = rebuilder.rebuild_all_ingredients(dry_run=dry_run, recipe_id=args.recipe_id, force_all=args.force_all)
    
    if result['success']:
        print(f"\n🎉 Rebuild {'simulated' if dry_run else 'completed'} successfully!")
    else:
        print(f"\n💥 Rebuild failed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()