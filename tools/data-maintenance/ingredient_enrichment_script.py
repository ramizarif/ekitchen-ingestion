#!/usr/bin/env python3
"""
Ingredient Enrichment Script

This script retrieves global ingredients that need enrichment AND are ready for enrichment,
enriches them with Spoonacular data and categorizes them using OpenAI.

Enrichment Logic:
- If Spoonacular data found: needs_enrichment=false, ready_for_enrichment=false (complete)
- If no Spoonacular data: needs_enrichment=true, ready_for_enrichment=false (prevent retries)

This prevents repeated attempts on ingredients that don't have Spoonacular data available.

Usage:
    python ingredient_enrichment_script.py --dry-run    # Preview changes
    python ingredient_enrichment_script.py --live       # Actually enrich ingredients
    python ingredient_enrichment_script.py --limit 10   # Process only 10 ingredients
"""

import sys
import os
import argparse
import json
import time
import requests
import urllib.parse
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from openai import OpenAI

# Add the processing directory to path for reusing existing classes
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'processing'))
from ingredient_processor_direct import DirectIngredientProcessor

@dataclass
class SpoonacularIngredientData:
    """Data structure for Spoonacular ingredient information"""
    id: int
    name: str
    calories: Optional[float] = None
    protein: Optional[float] = None
    fat: Optional[float] = None
    carbohydrates: Optional[float] = None
    sugar: Optional[float] = None
    consistency: Optional[str] = None
    possible_units: List[str] = None
    estimated_cost_per_unit: Optional[float] = None
    cost_unit: Optional[str] = None
    purchase_unit: Optional[str] = None
    purchase_quantity: Optional[float] = None
    min_purchase_threshold: Optional[float] = None
    unit_conversions: Optional[Dict[str, float]] = None
    
    def __post_init__(self):
        if self.possible_units is None:
            self.possible_units = []
        if self.unit_conversions is None:
            self.unit_conversions = {}

class IngredientEnrichmentScript:
    """Script to enrich ingredients with Spoonacular data and OpenAI categorization"""
    
    def __init__(self):
        print("🔧 Initializing ingredient enrichment system...")
        
        # Initialize the processor for authentication and configuration
        self.processor = DirectIngredientProcessor(log_to_file=False)
        
        # Initialize OpenAI client
        try:
            openai_api_key = self.processor.env_config.get('OPENAI_API_KEY', '')
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY not found in environment configuration")
            
            self.openai_client = OpenAI(api_key=openai_api_key)
            print("✅ OpenAI client initialized")
        except Exception as e:
            print(f"❌ Failed to initialize OpenAI: {e}")
            raise
        
        # Initialize Spoonacular API key
        self.spoonacular_api_key = self.processor.spoonacular_config.get('api_key', '')
        if not self.spoonacular_api_key:
            print("⚠️ Spoonacular API key not found - will skip Spoonacular enrichment")
        else:
            print("✅ Spoonacular API key loaded")
        
        # Statistics tracking
        self.stats = {
            'ingredients_processed': 0,
            'ingredients_skipped': 0,
            'spoonacular_enriched': 0,
            'openai_categorized': 0,
            'cost_estimated': 0,
            'needs_enrichment_updated': 0,
            'errors': []
        }
        
        # Data preview tracking
        self.preview_data = []
    
    def authenticate(self) -> bool:
        """Authenticate with eKitchen API"""
        print("🔐 Authenticating with eKitchen...")
        
        admin_email = self.processor.env_config.get('EKITCHEN_ADMIN_EMAIL', '')
        admin_password = self.processor.env_config.get('EKITCHEN_ADMIN_PASSWORD', '')
        
        success = self.processor.authenticate_ekitchen(admin_email, admin_password)
        if success:
            print("✅ eKitchen authentication successful")
            return True
        else:
            print("❌ eKitchen authentication failed")
            return False
    
    def get_ingredients_needing_enrichment(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get ingredients that need enrichment and are ready for enrichment from eKitchen API"""
        try:
            # Use the filter parameter as shown in the user's example
            url = f"{self.processor.ekitchen_base_url}/global-ingredients/"
            params = {
                'filter': 'needs_enrichment = true AND ready_for_enrichment = true',
                'limit': limit,
                'offset': offset
            }
            
            headers = {
                'Authorization': f'Bearer {self.processor.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                # Handle both possible response formats
                if isinstance(data, dict) and 'ingredients' in data:
                    ingredients = data['ingredients']
                else:
                    ingredients = data if isinstance(data, list) else []
                
                print(f"✅ Found {len(ingredients)} ingredients needing enrichment")
                return ingredients
            else:
                print(f"❌ Failed to get ingredients: {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error details: {error_detail}")
                except:
                    print(f"   Error response: {response.text}")
                return []
                
        except Exception as e:
            print(f"❌ Error fetching ingredients: {e}")
            return []
    
    def search_spoonacular_ingredient(self, ingredient_name: str) -> Optional[SpoonacularIngredientData]:
        """Search for an ingredient in Spoonacular API"""
        if not self.spoonacular_api_key:
            return None
        
        try:
            # Clean ingredient name for search
            clean_name = ingredient_name.strip().lower()
            
            # Search for ingredients using RapidAPI
            search_url = f"{self.processor.spoonacular_config['base_url']}/food/ingredients/search"
            params = {
                'query': clean_name,
                'number': 5,
                'metaInformation': True
            }
            
            # RapidAPI headers
            headers = {
                'X-RapidAPI-Key': self.spoonacular_api_key,
                'X-RapidAPI-Host': 'spoonacular-recipe-food-nutrition-v1.p.rapidapi.com'
            }
            
            response = requests.get(search_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if not results:
                    print(f"   🔍 No Spoonacular results for '{ingredient_name}'")
                    return None
                
                # Find best match (exact match or first result)
                best_match = None
                for result in results:
                    result_name = result.get('name', '').lower()
                    if result_name == clean_name:
                        best_match = result
                        break
                
                if not best_match:
                    best_match = results[0]  # Use first result as fallback
                
                spoon_id = best_match.get('id')
                if not spoon_id:
                    return None
                
                # Get detailed nutrition information
                nutrition_data = self.get_spoonacular_nutrition(spoon_id, ingredient_name)
                return nutrition_data
                
            else:
                print(f"   ❌ Spoonacular search failed for '{ingredient_name}': {response.status_code}")
                return None
                
        except Exception as e:
            print(f"   ❌ Error searching Spoonacular for '{ingredient_name}': {e}")
            return None
    
    def get_spoonacular_nutrition(self, spoonacular_id: int, ingredient_name: str) -> Optional[SpoonacularIngredientData]:
        """Get detailed nutrition information from Spoonacular"""
        try:
            info_url = f"{self.processor.spoonacular_config['base_url']}/food/ingredients/{spoonacular_id}/information"
            params = {
                'amount': 100,  # Per 100g
                'unit': 'grams'
            }
            
            # RapidAPI headers
            headers = {
                'X-RapidAPI-Key': self.spoonacular_api_key,
                'X-RapidAPI-Host': 'spoonacular-recipe-food-nutrition-v1.p.rapidapi.com'
            }
            
            response = requests.get(info_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                nutrition = data.get('nutrition', {})
                nutrients = nutrition.get('nutrients', [])
                
                # Extract key nutrients
                nutrient_map = {}
                for nutrient in nutrients:
                    name = nutrient.get('name', '').lower()
                    amount = nutrient.get('amount', 0)
                    
                    if 'calories' in name or 'energy' in name:
                        nutrient_map['calories'] = amount
                    elif 'protein' in name:
                        nutrient_map['protein'] = amount
                    elif 'fat' in name and 'saturated' not in name:
                        nutrient_map['fat'] = amount
                    elif 'carbohydrate' in name:
                        nutrient_map['carbohydrates'] = amount
                    elif 'sugar' in name:
                        nutrient_map['sugar'] = amount
                
                # Get possible units
                possible_units = data.get('possibleUnits', [])
                consistency = data.get('consistency', 'solid')
                
                spoon_data = SpoonacularIngredientData(
                    id=spoonacular_id,
                    name=data.get('name', ingredient_name),
                    calories=nutrient_map.get('calories'),
                    protein=nutrient_map.get('protein'),
                    fat=nutrient_map.get('fat'),
                    carbohydrates=nutrient_map.get('carbohydrates'),
                    sugar=nutrient_map.get('sugar'),
                    consistency=consistency,
                    possible_units=possible_units
                )
                
                # Estimate cost information using AI
                cost_info = self.estimate_ingredient_cost_with_ai(ingredient_name, possible_units)
                if cost_info:
                    spoon_data.estimated_cost_per_unit = cost_info['cost_per_unit']
                    spoon_data.cost_unit = cost_info['cost_unit']
                    spoon_data.purchase_unit = cost_info['purchase_unit']
                    spoon_data.purchase_quantity = cost_info['purchase_quantity']
                    spoon_data.min_purchase_threshold = cost_info['min_purchase_threshold']
                    
                    # Get unit conversions for the cost unit
                    spoon_data.unit_conversions = self.get_unit_conversions(
                        ingredient_name, possible_units, cost_info['cost_unit']
                    )
                
                print(f"   ✅ Spoonacular data retrieved for '{ingredient_name}'")
                return spoon_data
            else:
                print(f"   ❌ Failed to get Spoonacular nutrition for '{ingredient_name}': {response.status_code}")
                return None
                
        except Exception as e:
            print(f"   ❌ Error getting Spoonacular nutrition for '{ingredient_name}': {e}")
            return None
    
    def categorize_ingredient_with_ai(self, ingredient_name: str) -> str:
        """Use OpenAI to categorize an ingredient"""
        try:
            prompt = f"""Categorize this food ingredient into ONE of these exact categories:
- proteins (meat, fish, poultry, eggs, legumes, nuts, seeds)
- dairy (milk, cheese, yogurt, butter, cream)
- vegetables (all vegetables including herbs)
- fruits (all fruits including berries)
- grains (rice, wheat, oats, quinoa, flour, bread, pasta)
- spices (spices, seasonings, extracts, flavorings)
- condiments (sauces, dressings, oils, vinegar, mustard)
- beverages (water, juice, wine, coffee, tea)
- other (anything that doesn't fit above categories)

Ingredient: "{ingredient_name}"

Return ONLY the category name, nothing else."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20,
                temperature=0.1
            )
            
            category = response.choices[0].message.content.strip().lower()
            
            # Validate category
            valid_categories = ['proteins', 'dairy', 'vegetables', 'fruits', 'grains', 'spices', 'condiments', 'beverages', 'other']
            if category not in valid_categories:
                print(f"   ⚠️ AI returned invalid category '{category}', using 'other'")
                category = 'other'
            
            print(f"   🤖 AI categorized '{ingredient_name}' as '{category}'")
            return category
            
        except Exception as e:
            print(f"   ❌ AI categorization failed for '{ingredient_name}': {e}")
            return 'other'
    
    def estimate_ingredient_cost_with_ai(self, ingredient_name: str, possible_units: List[str]) -> Optional[Dict[str, Any]]:
        """Use OpenAI to estimate ingredient cost and purchase information"""
        try:
            units_list = ", ".join(possible_units[:5]) if possible_units else "cup, tablespoon, teaspoon, ounce"
            
            prompt = f"""Estimate cost and purchase information for this ingredient: "{ingredient_name}"
Available units: {units_list}

Provide realistic US grocery store estimates in this EXACT JSON format:
{{
  "cost_per_unit": [number],
  "cost_unit": "[smallest practical unit for costing]",
  "purchase_unit": "[what you actually buy - bottle, jar, bag, etc]",
  "purchase_quantity": [how many cost_units in one purchase_unit],
  "min_purchase_threshold": [if recipe needs this many cost_units or more, buy full purchase_unit]
}}

Examples:
- Honey: cost_per_unit: 0.12, cost_unit: "tablespoon", purchase_unit: "bottle", purchase_quantity: 32, min_purchase_threshold: 8
- Ground beef: cost_per_unit: 6.99, cost_unit: "pound", purchase_unit: "pound", purchase_quantity: 1, min_purchase_threshold: 0.5
- Salt: cost_per_unit: 0.02, cost_unit: "teaspoon", purchase_unit: "container", purchase_quantity: 192, min_purchase_threshold: 48

Return ONLY the JSON, no other text."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            
            # Try to parse JSON response
            try:
                cost_info = json.loads(response_text)
                
                # Validate required fields
                required_fields = ['cost_per_unit', 'cost_unit', 'purchase_unit', 'purchase_quantity', 'min_purchase_threshold']
                if all(field in cost_info for field in required_fields):
                    print(f"   💰 AI estimated cost: ${cost_info['cost_per_unit']:.2f}/{cost_info['cost_unit']}")
                    return cost_info
                else:
                    print(f"   ⚠️ AI cost estimation missing required fields for '{ingredient_name}'")
                    return None
                    
            except json.JSONDecodeError:
                print(f"   ⚠️ AI cost estimation returned invalid JSON for '{ingredient_name}': {response_text}")
                return None
            
        except Exception as e:
            print(f"   ❌ AI cost estimation failed for '{ingredient_name}': {e}")
            return None
    
    def get_unit_conversions(self, ingredient_name: str, possible_units: List[str], cost_unit: str) -> Dict[str, float]:
        """Get conversion factors from all possible units to the cost unit"""
        if not self.spoonacular_api_key or not possible_units:
            return {}
        
        conversions = {}
        
        # Common units to prioritize for conversion
        priority_units = ['cup', 'tablespoon', 'teaspoon', 'ounce', 'pound', 'gram', 'liter']
        units_to_convert = []
        
        # Add priority units that exist in possible_units
        for unit in priority_units:
            if unit in possible_units and unit != cost_unit:
                units_to_convert.append(unit)
        
        # Add other possible units (limit to avoid too many API calls)
        for unit in possible_units:
            if unit not in units_to_convert and unit != cost_unit and len(units_to_convert) < 8:
                units_to_convert.append(unit)
        
        print(f"   🔄 Getting conversion factors for {len(units_to_convert)} units...")
        
        for unit in units_to_convert:
            try:
                # Convert 1 unit to cost_unit
                convert_url = f"{self.processor.spoonacular_config['base_url']}/recipes/convert"
                params = {
                    'ingredientName': ingredient_name,
                    'sourceAmount': 1,
                    'sourceUnit': unit,
                    'targetUnit': cost_unit
                }
                
                # RapidAPI headers
                headers = {
                    'X-RapidAPI-Key': self.spoonacular_api_key,
                    'X-RapidAPI-Host': 'spoonacular-recipe-food-nutrition-v1.p.rapidapi.com'
                }
                
                response = requests.get(convert_url, params=params, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('type') == 'CONVERSION':
                        conversion_factor = data.get('targetAmount', 1.0)
                        # Only include positive conversion factors
                        if conversion_factor > 0:
                            conversions[unit] = conversion_factor
                            print(f"   ✅ 1 {unit} = {conversion_factor:.3f} {cost_unit}")
                        else:
                            print(f"   ⚠️ Invalid conversion factor (≤0): {unit} → {cost_unit}")
                    else:
                        print(f"   ⚠️ No conversion available: {unit} → {cost_unit}")
                else:
                    print(f"   ❌ Conversion failed: {unit} → {cost_unit} ({response.status_code})")
                
                # Small delay to be respectful to API
                time.sleep(0.2)
                
            except Exception as e:
                print(f"   ❌ Error converting {unit} → {cost_unit}: {e}")
        
        # Always include the identity conversion (cost_unit to itself)
        conversions[cost_unit] = 1.0
        
        print(f"   📊 Got {len(conversions)} conversion factors")
        return conversions
    
    def update_ingredient(self, ingredient_id: str, update_data: Dict[str, Any], dry_run: bool = True) -> bool:
        """Update an ingredient with enrichment data"""
        if dry_run:
            print(f"   🧪 DRY RUN: Would update ingredient {ingredient_id} with: {json.dumps(update_data, indent=2)}")
            return True
        
        try:
            url = f"{self.processor.ekitchen_base_url}/global-ingredients/{ingredient_id}"
            headers = {
                'Authorization': f'Bearer {self.processor.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Add update_mask with all the fields we're updating
            # Map JSON field names to Go struct field names for update_mask
            json_to_go_field_map = {
                'external_id': 'ExternalID',
                'consistency': 'Consistency',
                'possible_units': 'PossibleUnits',
                'calories': 'Calories',
                'protein': 'Protein',
                'fat': 'Fat',
                'carbohydrates': 'Carbohydrates',
                'sugar': 'Sugar',
                'estimated_cost_value': 'EstimatedCostValue',
                'estimated_cost_unit': 'EstimatedCostUnit',
                'purchase_info': 'PurchaseInfo',
                'unit_conversions': 'UnitConversions',
                'category': 'Category',
                'needs_enrichment': 'NeedsEnrichment',
                'ready_for_enrichment': 'ReadyForEnrichment'
            }
            
            fields_to_update = [key for key in update_data.keys() if key != 'id']
            go_field_names = [json_to_go_field_map.get(field, field) for field in fields_to_update]
            update_mask = ','.join(go_field_names)
            params = {'update_mask': update_mask}
            
            print(f"   📋 Update mask: {update_mask}")
            print(f"   🔄 Sending PATCH request...")
            
            response = requests.patch(url, json=update_data, headers=headers, params=params, timeout=30)
            
            if response.status_code in [200, 204]:
                print(f"   ✅ Successfully updated ingredient {ingredient_id}")
                return True
            else:
                print(f"   ❌ Failed to update ingredient {ingredient_id}: {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error details: {error_detail}")
                except:
                    print(f"   Error response: {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error updating ingredient {ingredient_id}: {e}")
            return False
    
    def save_preview_data(self, filename: str):
        """Save preview data to a JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump({
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "summary": self.stats,
                    "ingredients": self.preview_data
                }, f, indent=2)
        except Exception as e:
            print(f"❌ Failed to save preview data: {e}")
    
    def process_single_ingredient(self, ingredient: Dict[str, Any], dry_run: bool = True) -> bool:
        """Process a single ingredient: enrich with Spoonacular and categorize with AI"""
        ingredient_id = ingredient.get('id')
        ingredient_name = ingredient.get('name', 'Unknown')
        
        print(f"\n{'='*60}")
        print(f"🥕 Processing Ingredient: {ingredient_name}")
        print(f"🆔 ID: {ingredient_id}")
        
        if not ingredient_id or not ingredient_name:
            print("⚠️ Missing ingredient ID or name - skipping")
            self.stats['ingredients_skipped'] += 1
            return False
        
        try:
            # Prepare update data
            update_data = {
                "id": ingredient_id
            }
            
            # Step 1: Try to get Spoonacular data
            print(f"\n📋 Step 1: Searching Spoonacular for '{ingredient_name}'...")
            spoon_data = self.search_spoonacular_ingredient(ingredient_name)
            
            spoonacular_found = spoon_data is not None
            
            if spoon_data:
                # Add Spoonacular nutrition data
                update_data.update({
                    "external_id": str(spoon_data.id),
                    "consistency": spoon_data.consistency or "solid",
                    "possible_units": spoon_data.possible_units or ["cup", "tbsp", "tsp", "oz", "g"]
                })
                
                # Add nutrition data only if values exist
                if spoon_data.calories is not None:
                    update_data["calories"] = spoon_data.calories
                if spoon_data.protein is not None:
                    update_data["protein"] = spoon_data.protein
                if spoon_data.fat is not None:
                    update_data["fat"] = spoon_data.fat
                if spoon_data.carbohydrates is not None:
                    update_data["carbohydrates"] = spoon_data.carbohydrates
                if spoon_data.sugar is not None:
                    update_data["sugar"] = spoon_data.sugar
                
                # Add cost information if available
                if spoon_data.estimated_cost_per_unit is not None:
                    update_data["estimated_cost_value"] = spoon_data.estimated_cost_per_unit
                    update_data["estimated_cost_unit"] = spoon_data.cost_unit
                    
                    # Store purchase info as JSON string (matches backend schema)
                    purchase_info = {
                        "purchase_unit": spoon_data.purchase_unit,
                        "purchase_quantity": spoon_data.purchase_quantity,
                        "min_purchase_threshold": spoon_data.min_purchase_threshold,
                        "supplier": "AI Estimate"
                    }
                    update_data["purchase_info"] = json.dumps(purchase_info)
                    
                    # Store unit conversions as JSON string (matches backend schema)
                    if spoon_data.unit_conversions:
                        update_data["unit_conversions"] = json.dumps(spoon_data.unit_conversions)
                    
                    self.stats['cost_estimated'] += 1
                
                self.stats['spoonacular_enriched'] += 1
                print(f"   ✅ Spoonacular data added")
            else:
                print(f"   ❌ No Spoonacular data found")
            
            # Step 2: Categorize with OpenAI
            print(f"\n📋 Step 2: Categorizing with AI...")
            category = self.categorize_ingredient_with_ai(ingredient_name)
            update_data["category"] = category
            self.stats['openai_categorized'] += 1
            
            # Step 3: Set needs_enrichment and ready_for_enrichment based on whether we found Spoonacular data
            if spoonacular_found:
                # Found Spoonacular data - mark as fully enriched
                update_data["needs_enrichment"] = False
                update_data["ready_for_enrichment"] = False  # No longer ready since it's complete
                print(f"   ✅ Marking as enriched (Spoonacular data found)")
                self.stats['needs_enrichment_updated'] += 1
            else:
                # No Spoonacular data - keep as needs enrichment but mark as not ready to prevent retries
                update_data["needs_enrichment"] = True
                update_data["ready_for_enrichment"] = False  # Don't retry ingredients without Spoonacular data
                print(f"   ⚠️ Keeping as needs_enrichment but marking as not ready for enrichment (no Spoonacular data)")
            
            # Step 4: Save preview data
            preview_entry = {
                "original_name": ingredient_name,
                "ingredient_id": ingredient_id,
                "spoonacular_found": spoonacular_found,
                "update_data": update_data.copy(),
                "spoonacular_data": None,
                "cost_info": None
            }
            
            if spoon_data:
                preview_entry["spoonacular_data"] = {
                    "spoonacular_id": spoon_data.id,
                    "calories_per_100g": spoon_data.calories,
                    "protein_per_100g": spoon_data.protein,
                    "fat_per_100g": spoon_data.fat,
                    "carbohydrates_per_100g": spoon_data.carbohydrates,
                    "sugar_per_100g": spoon_data.sugar,
                    "consistency": spoon_data.consistency,
                    "possible_units": spoon_data.possible_units
                }
                
                if spoon_data.estimated_cost_per_unit:
                    preview_entry["cost_info"] = {
                        "cost_per_unit": spoon_data.estimated_cost_per_unit,
                        "cost_unit": spoon_data.cost_unit,
                        "purchase_unit": spoon_data.purchase_unit,
                        "purchase_quantity": spoon_data.purchase_quantity,
                        "min_purchase_threshold": spoon_data.min_purchase_threshold,
                        "unit_conversions": spoon_data.unit_conversions
                    }
            
            self.preview_data.append(preview_entry)
            
            # Step 5: Update the ingredient
            print(f"\n📋 Step 4: Updating ingredient...")
            success = self.update_ingredient(ingredient_id, update_data, dry_run)
            
            if success:
                self.stats['ingredients_processed'] += 1
                print(f"✅ Successfully processed ingredient: {ingredient_name}")
                return True
            else:
                print(f"❌ Failed to process ingredient: {ingredient_name}")
                self.stats['ingredients_skipped'] += 1
                return False
            
        except Exception as e:
            error_msg = f"Error processing ingredient {ingredient_name}: {e}"
            print(f"❌ {error_msg}")
            self.stats['errors'].append(error_msg)
            self.stats['ingredients_skipped'] += 1
            return False
    
    def enrich_ingredients(self, limit: int = 50, dry_run: bool = True) -> Dict[str, Any]:
        """Main method: enrich ingredients that need enrichment"""
        print(f"🚀 Starting ingredient enrichment...")
        print(f"📋 Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        print(f"📊 Limit: {limit} ingredients")
        
        start_time = time.time()
        
        # Authenticate
        if not self.authenticate():
            return {"success": False, "error": "Authentication failed"}
        
        try:
            # Step 1: Get ingredients that need enrichment
            print(f"\n{'='*60}")
            print("📋 STEP 1: Getting ingredients that need enrichment")
            ingredients = self.get_ingredients_needing_enrichment(limit=limit)
            
            if not ingredients:
                return {"success": True, "message": "No ingredients need enrichment"}
            
            print(f"✅ Found {len(ingredients)} ingredients to process")
            
            # Step 2: Process each ingredient
            print(f"\n{'='*60}")
            print("🔄 STEP 2: Processing ingredients")
            
            for i, ingredient in enumerate(ingredients, 1):
                print(f"\n--- Processing {i}/{len(ingredients)} ---")
                self.process_single_ingredient(ingredient, dry_run)
                
                # Rate limiting to be respectful to APIs
                if not dry_run:
                    time.sleep(1)
            
            # Final summary
            duration = time.time() - start_time
            print(f"\n{'='*60}")
            print("📊 ENRICHMENT COMPLETE!")
            print(f"⏱️  Duration: {duration:.1f} seconds")
            print(f"✅ Ingredients processed: {self.stats['ingredients_processed']}")
            print(f"⏭️  Ingredients skipped: {self.stats['ingredients_skipped']}")
            print(f"🌟 Spoonacular enriched: {self.stats['spoonacular_enriched']}")
            print(f"🤖 AI categorized: {self.stats['openai_categorized']}")
            print(f"💰 Cost estimated: {self.stats['cost_estimated']}")
            print(f"✨ Marked as enriched: {self.stats['needs_enrichment_updated']}")
            print(f"❌ Errors: {len(self.stats['errors'])}")
            
            if self.stats['errors']:
                print("\n🚨 ERRORS:")
                for error in self.stats['errors']:
                    print(f"   - {error}")
            
            # Save preview data to file
            if self.preview_data:
                preview_file = f"data-maintenance/enrichment_preview_{int(time.time())}.json"
                self.save_preview_data(preview_file)
                print(f"\n💾 Preview data saved to: {preview_file}")
            
            return {
                "success": True,
                "stats": self.stats,
                "duration": duration
            }
            
        except Exception as e:
            error_msg = f"Fatal error during enrichment: {e}"
            print(f"💥 {error_msg}")
            return {"success": False, "error": error_msg}


def main():
    parser = argparse.ArgumentParser(description='Ingredient Enrichment Script')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Preview changes without making them (default)')
    parser.add_argument('--live', action='store_true',
                       help='Actually perform the enrichment')
    parser.add_argument('--limit', type=int, default=50,
                       help='Maximum number of ingredients to process (default: 50)')
    
    args = parser.parse_args()
    
    # Default to dry run unless --live is specified
    dry_run = not args.live
    
    enricher = IngredientEnrichmentScript()
    result = enricher.enrich_ingredients(limit=args.limit, dry_run=dry_run)
    
    if result['success']:
        print(f"\n🎉 Enrichment {'simulated' if dry_run else 'completed'} successfully!")
    else:
        print(f"\n💥 Enrichment failed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()