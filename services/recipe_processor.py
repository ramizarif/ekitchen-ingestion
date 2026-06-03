#!/usr/bin/env python3
"""
Recipe Processor - Autonomous Recipe Ingestion Pipeline
Handles complete recipe processing flow with direct API calls and OpenAI for AI decisions
"""

import json
import urllib.request
import urllib.parse
import urllib.error
import requests
import re
import os
import logging
import base64
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from openai import OpenAI

# Import ingredient processor from same package
from services.ingredient_processor import DirectIngredientProcessor, IngredientData, load_env_file

# Non-ingredient blocklist: equipment, tools, prepared foods, and non-food items
# that GPT-4 sometimes includes when parsing recipes
NON_INGREDIENT_BLOCKLIST = {
    # Equipment/tools
    'fork', 'knife', 'spoon', 'spatula', 'whisk', 'tongs',
    'baking sheet', 'sheet pan', 'frying pan', 'saucepan', 'skillet',
    'pot', 'dutch oven', 'wok', 'grill', 'oven',
    'foil', 'aluminum foil', 'parchment paper', 'plastic wrap', 'cling wrap',
    'bamboo skewer', 'skewer', 'toothpick',
    'potato ricer', 'food processor', 'blender', 'mixer',
    'cutting board', 'bowl', 'plate', 'serving platter',
    'baking pan', 'cake pan', 'muffin tin', 'loaf pan',
    'colander', 'strainer', 'sieve', 'grater', 'peeler',
    'rolling pin', 'pastry brush', 'ladle', 'slotted spoon',
    'measuring cup', 'measuring spoon', 'thermometer',
    'parchment', 'wax paper', 'saran wrap',
    # Prepared foods (not base ingredients)
    'french fry', 'french fries', 'potato chip', 'potato chips',
    'tortilla chip', 'tortilla chips',
    'bean and cheese burrito', 'pizza dough',
    # Non-food items
    'ice cube', 'ice cubes', 'paper towel', 'paper towels',
    'kitchen twine', 'cheesecloth', 'butcher twine',
    'cooking spray', 'nonstick spray',
}

@dataclass
class RecipeProcessingResult:
    """Result of recipe processing operation"""
    success: bool
    recipe_id: Optional[str] = None
    recipe_name: Optional[str] = None
    error_message: Optional[str] = None
    ingredients_processed: int = 0
    image_generated: bool = False
    processing_time_seconds: float = 0.0

class DirectRecipeProcessor:
    """Autonomous recipe processor using direct API calls"""
    
    def __init__(self, log_to_file: bool = True):
        # Load configuration
        self.config = self._load_configuration()
        
        # Initialize components with updated cleaning
        self.ingredient_processor = DirectIngredientProcessor(log_to_file=log_to_file)
        self.logger = self._setup_logging(log_to_file)
        self.log_to_file = log_to_file
        
        # API clients
        self.openai_client = None
        self.ekitchen_token = None
        self.ekitchen_refresh_token = None
        
        # Initialize API connections
        self._initialize_apis()
        
        # Global ingredients cache for deduplication during ingestion
        self.global_ingredients_cache = {}
    
    def _load_configuration(self) -> Dict[str, str]:
        """Load configuration from environment variables first, then fall back to files"""
        env_vars = {}
        
        # First, check environment variables directly (for Docker/production)
        env_keys = [
            'OPENAI_API_KEY', 'SPOONACULAR_API_KEY', 
            'EKITCHEN_BASE_URL', 'EKITCHEN_ADMIN_EMAIL', 'EKITCHEN_ADMIN_PASSWORD',
            'SPOONACULAR_BASE_URL', 'SPOONACULAR_RATE_LIMIT_PER_MINUTE',
            'SPOONACULAR_RATE_LIMIT_PER_DAY', 'SPOONACULAR_REQUEST_TIMEOUT',
            'SPOONACULAR_MAX_RETRIES', 'SPOONACULAR_RETRY_DELAY'
        ]
        for key in env_keys:
            value = os.environ.get(key)
            if value:
                env_vars[key] = value
        
        # If we have the critical keys from environment, we're good
        if env_vars.get('OPENAI_API_KEY') and env_vars.get('EKITCHEN_ADMIN_EMAIL'):
            return env_vars
        
        # Fall back to loading from local.env file
        env_file_paths = [
            os.path.join(os.path.dirname(__file__), '..', 'local.env'),
            '/app/local.env',
            os.path.join(os.path.dirname(__file__), '..', '..', 'local.env')
        ]
        for env_file_path in env_file_paths:
            loaded = load_env_file(env_file_path)
            if loaded:
                env_vars.update(loaded)
                break
        
        return env_vars
    
    def _setup_logging(self, log_to_file: bool) -> logging.Logger:
        """Setup comprehensive logging"""
        logger = logging.getLogger('direct_recipe_processor')
        logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        if log_to_file:
            # Create logs directory
            log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            # Timestamped log file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = os.path.join(log_dir, f'direct_recipe_processor_{timestamp}.log')
            
            # File handler
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            print(f"📝 Recipe processor logging enabled: {log_file}")
        
        return logger
    
    def _log_and_print(self, message: str, level: str = 'info'):
        """Log message to file and print to console"""
        print(message)
        if self.log_to_file:
            if level == 'debug':
                self.logger.debug(message)
            elif level == 'error':
                self.logger.error(message)
            elif level == 'warning':
                self.logger.warning(message)
            else:
                self.logger.info(message)
    
    def _initialize_apis(self):
        """Initialize all API connections"""
        self._log_and_print("🔧 Initializing API connections...")
        
        # Initialize OpenAI
        openai_key = self.config.get('OPENAI_API_KEY')
        if openai_key:
            try:
                import openai
                self.openai_client = openai.OpenAI(api_key=openai_key)
                self._log_and_print("✅ OpenAI client initialized")
            except ImportError:
                self._log_and_print("❌ OpenAI library not installed. Run: pip install openai", 'error')
            except Exception as e:
                self._log_and_print(f"❌ OpenAI initialization failed: {e}", 'error')
        else:
            self._log_and_print("❌ OPENAI_API_KEY not found in configuration", 'error')
        
        # Initialize eKitchen authentication
        admin_email = self.config.get('EKITCHEN_ADMIN_EMAIL')
        admin_password = self.config.get('EKITCHEN_ADMIN_PASSWORD')
        
        if admin_email and admin_password:
            if self.ingredient_processor.authenticate_ekitchen(admin_email, admin_password):
                self.ekitchen_token = self.ingredient_processor.access_token
                self.ekitchen_refresh_token = self.ingredient_processor.refresh_token
                self._log_and_print("✅ eKitchen authentication successful")
            else:
                self._log_and_print("❌ eKitchen authentication failed", 'error')
        else:
            self._log_and_print("❌ eKitchen credentials not found in configuration", 'error')
    
    def scrape_recipe_from_url(self, recipe_url: str) -> Optional[Dict[str, Any]]:
        """Scrape recipe data from URL using recipe-scrapers library"""
        self._log_and_print(f"🌐 Scraping recipe from: {recipe_url}")
        
        try:
            # Use recipe-scrapers library for reliable scraping
            from recipe_scrapers import scrape_me
            
            scraper = scrape_me(recipe_url)
            
            # Extract recipe data
            recipe_data = {
                "title": scraper.title(),
                "description": scraper.description() or "",
                "ingredients": scraper.ingredients(),
                "instructions": scraper.instructions_list(),
                "prep_time": self._extract_time_minutes(scraper.prep_time()),
                "cook_time": self._extract_time_minutes(scraper.cook_time()),
                "total_time": self._extract_time_minutes(scraper.total_time()),
                "yields": self._extract_servings(scraper.yields()),
                "image_url": scraper.image() or "",
                "author": scraper.author() or "",
                "url": recipe_url
            }
            
            self._log_and_print(f"✅ Successfully scraped: {recipe_data['title']}")
            self._log_and_print(f"   Ingredients: {len(recipe_data['ingredients'])}")
            self._log_and_print(f"   Instructions: {len(recipe_data['instructions'])} steps")
            
            return recipe_data
            
        except ImportError:
            self._log_and_print("❌ recipe-scrapers library not installed. Run: pip install recipe-scrapers", 'error')
            return None
        except Exception as e:
            self._log_and_print(f"❌ Failed to scrape recipe: {e}", 'error')
            return None
    
    def _extract_time_minutes(self, time_value) -> int:
        """Extract time in minutes from various formats"""
        if not time_value:
            return 0
        
        if isinstance(time_value, int):
            return time_value
        
        if isinstance(time_value, str):
            # Extract numbers from time strings
            numbers = re.findall(r'\d+', time_value.lower())
            if numbers:
                if 'hour' in time_value.lower():
                    return int(numbers[0]) * 60 + (int(numbers[1]) if len(numbers) > 1 else 0)
                else:
                    return int(numbers[0])
        
        return 0
    
    def _extract_servings(self, yields_value) -> int:
        """Extract number of servings from yields"""
        if not yields_value:
            return 4  # Default
        
        if isinstance(yields_value, int):
            return yields_value
        
        if isinstance(yields_value, str):
            numbers = re.findall(r'\d+', yields_value)
            if numbers:
                return int(numbers[0])
        
        return 4  # Default fallback
    
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
    
    def standardize_ingredient_with_ai(self, ingredient_text: str) -> Dict[str, str]:
        """Use AI to standardize ingredient name and extract reference_as field"""
        if not self.openai_client:
            self._log_and_print("❌ OpenAI not available for ingredient standardization - recipe processing will fail", 'error')
            raise Exception("OpenAI client not available - ingredient standardization failed")
            
        try:
            prompt = f"""Given this recipe ingredient text, extract:
1. STANDARDIZED_NAME: Clean global ingredient name (remove quantities, preparations, descriptors)  
2. REFERENCE_AS: How this specific ingredient should be referenced in recipe steps

Input: "{ingredient_text}"

RULES for STANDARDIZED_NAME:
- Remove quantities: "2 cups flour" → "flour"
- Remove preparations: "chopped onions" → "onion" 
- Remove descriptors: "fresh basil" → "basil"
- Remove conditions: "thawed peas" → "peas"
- Keep essential qualifiers: "red bell pepper" → "red bell pepper"
- Use singular form when possible: "eggs" → "egg"
- Remove brand names and measurements

RULES for REFERENCE_AS:
- Keep original descriptors that matter for cooking: "fresh basil leaves" → "fresh basil"
- Keep preparation methods: "diced onions" → "diced onions"  
- Keep size descriptors: "large egg" → "large egg"
- Remove quantities but keep cooking-relevant details

Return ONLY a JSON object like:
{{"standardized_name": "flour", "reference_as": "all-purpose flour"}}

Examples:
"2 cups all-purpose flour" → {{"standardized_name": "flour", "reference_as": "all-purpose flour"}}
"1 large onion, chopped" → {{"standardized_name": "onion", "reference_as": "chopped onion"}}
"fresh basil leaves" → {{"standardized_name": "basil", "reference_as": "fresh basil"}}
"1 can (14 oz) diced tomatoes" → {{"standardized_name": "diced tomatoes", "reference_as": "diced tomatoes"}}
"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content.strip()
            self._log_and_print(f"🤖 AI raw response: '{result_text}'", 'debug')
            
            # Clean markdown code blocks if present
            if result_text.startswith('```json') and result_text.endswith('```'):
                result_text = result_text[7:-3].strip()  # Remove ```json and ```
            elif result_text.startswith('```') and result_text.endswith('```'):
                result_text = result_text[3:-3].strip()  # Remove generic ```
            
            # Parse JSON response with better error handling
            try:
                result = json.loads(result_text)
                standardized_name = result.get("standardized_name", "").lower().strip()
                reference_as = result.get("reference_as", "").strip()
                
                # Clean any JSON artifacts that might have slipped through
                standardized_name = standardized_name.strip(' "\'{}[](),')
                reference_as = reference_as.strip(' "\'{}[](),')
                
                if not standardized_name or len(standardized_name) < 2:
                    raise ValueError(f"Invalid standardized_name: '{standardized_name}'")
                    
                # Apply singularization to the standardized name
                singular_name = self.pluralize_to_singular(standardized_name)
                
                self._log_and_print(f"✅ AI JSON parsed successfully", 'debug')
                return {
                    "standardized_name": singular_name,
                    "reference_as": reference_as or ingredient_text.strip()
                }
            except json.JSONDecodeError:
                # Fallback: try to extract from text response with proper cleaning
                self._log_and_print(f"⚠️  JSON parsing failed for: '{result_text}' - using fallback extraction", 'warning')
                lines = result_text.split('\n')
                standardized_name = ""
                reference_as = ""
                
                for line in lines:
                    if 'standardized_name' in line.lower():
                        # Better cleaning - remove all JSON artifacts
                        name_part = line.split(':')[-1]
                        standardized_name = name_part.strip(' "\'{}[](),').lower()
                    elif 'reference_as' in line.lower():
                        # Better cleaning for reference_as too
                        ref_part = line.split(':')[-1]
                        reference_as = ref_part.strip(' "\'{}[](),')
                
                if not standardized_name:
                    standardized_name = ingredient_text.split(',')[0].strip().lower()
                if not reference_as:
                    reference_as = ingredient_text.strip()
                    
                # Apply singularization to the standardized name
                singular_name = self.pluralize_to_singular(standardized_name)
                
                return {
                    "standardized_name": singular_name,
                    "reference_as": reference_as
                }
            
        except Exception as e:
            self._log_and_print(f"❌ AI standardization failed for '{ingredient_text}': {e}", 'error')
            self._log_and_print("❌ Recipe processing will be aborted - OpenAI parsing is required for data quality", 'error')
            raise Exception(f"OpenAI ingredient standardization failed: {e}") from e
    
    def get_or_create_global_ingredient_enhanced(self, standardized_name: str) -> Optional[str]:
        """Get existing global ingredient or create new one with full Spoonacular enrichment"""
        
        # Check cache first
        if standardized_name in self.global_ingredients_cache:
            return self.global_ingredients_cache[standardized_name]
        
        try:
            # Use the SAME search logic as the working ingredient_processor_direct.py
            existing_ingredients = self.ingredient_processor.search_ekitchen_ingredient(standardized_name)
            
            # If found with exact name match, use the existing ingredient
            if existing_ingredients:
                # Check for true exact match first (case-insensitive)
                exact_match = None
                for ing in existing_ingredients:
                    if ing.get('name', '').lower().strip() == standardized_name.lower().strip():
                        exact_match = ing
                        break

                if exact_match:
                    ingredient_id = exact_match.get('id')
                    self.global_ingredients_cache[standardized_name] = ingredient_id
                    self._log_and_print(f"   ♻️ Found existing global ingredient '{standardized_name}' → {ingredient_id}")
                    return ingredient_id

            # ── Similarity / duplicate detection ──────────────────────
            # Before creating a new ingredient, check if a similar one exists
            similar = self.ingredient_processor._find_similar_ingredient(standardized_name)
            if similar:
                resolution = self.ingredient_processor._resolve_canonical_name(
                    standardized_name, similar['name']
                )
                if resolution.get('same_ingredient'):
                    canonical = resolution.get('canonical_name', standardized_name)
                    existing_id = similar['id']
                    existing_name = similar['name']

                    if canonical.lower().strip() == existing_name.lower().strip():
                        # Existing name IS canonical → just reuse it
                        self.global_ingredients_cache[standardized_name] = existing_id
                        self._log_and_print(
                            f"   ♻️ Dedup: '{standardized_name}' is same as existing "
                            f"'{existing_name}' (canonical) → {existing_id}"
                        )
                        return existing_id
                    else:
                        # New name is canonical → rename existing ingredient, then reuse
                        self._log_and_print(
                            f"   ✏️  Dedup: renaming '{existing_name}' → '{canonical}' (canonical)"
                        )
                        renamed = self.ingredient_processor.rename_ingredient(existing_id, canonical)
                        if renamed:
                            self.global_ingredients_cache[standardized_name] = existing_id
                            # Also cache under canonical name
                            self.global_ingredients_cache[canonical] = existing_id
                            return existing_id
                        else:
                            # Rename failed – still reuse existing to avoid duplicate
                            self._log_and_print(
                                f"   ⚠️  Rename failed, reusing existing '{existing_name}' → {existing_id}",
                                'warning',
                            )
                            self.global_ingredients_cache[standardized_name] = existing_id
                            return existing_id
                else:
                    self._log_and_print(
                        f"   🔀 AI says '{standardized_name}' ≠ '{similar['name']}' — creating new ingredient"
                    )
            # ── End similarity detection ──────────────────────────────

            # If not found, create with COMPREHENSIVE 2-step enrichment process
            self._log_and_print(f"   🌶️ Starting 2-step enrichment for '{standardized_name}'...")
            
            # STEP 1: Spoonacular enrichment
            self._log_and_print(f"   🔍 STEP 1: Searching Spoonacular for '{standardized_name}'...")
            spoon_search_result = self.ingredient_processor.search_spoonacular_ingredient_enhanced(standardized_name)
            
            ingredient_data = None
            
            if spoon_search_result:
                spoon_ingredient_id = spoon_search_result.id
                spoon_name = spoon_search_result.name
                self._log_and_print(f"   ✅ Found in Spoonacular: '{spoon_name}' (ID: {spoon_ingredient_id})")
                
                # Enhanced method already includes nutrition data
                self._log_and_print(f"   ✅ Got Spoonacular nutrition data from enhanced search")
                
                # Extract nutrition values from enhanced result
                calories = spoon_search_result.calories or 0
                protein = spoon_search_result.protein or 0
                fat = spoon_search_result.fat or 0
                carbs = spoon_search_result.carbohydrates or 0
                sugar = spoon_search_result.sugar or 0
                
                # Get estimated cost if available from enhanced result
                cost_value = spoon_search_result.estimated_cost_per_unit or 0
                
                self._log_and_print(f"   📊 Nutrition: {calories}cal, {protein}g protein, {fat}g fat, {carbs}g carbs")
                
                # STEP 2: OpenAI categorization
                self._log_and_print(f"   🤖 STEP 2: Getting category from OpenAI for '{standardized_name}'...")
                ai_category = self.get_ingredient_category_from_ai(standardized_name)
                
                # Build purchase_info JSON if cost data is available
                purchase_info_json = None
                unit_conversions_json = None
                if spoon_search_result.estimated_cost_per_unit is not None:
                    purchase_cost = spoon_search_result.purchase_cost
                    if purchase_cost is None and spoon_search_result.estimated_cost_per_unit and spoon_search_result.purchase_quantity:
                        purchase_cost = spoon_search_result.estimated_cost_per_unit * spoon_search_result.purchase_quantity
                    
                    purchase_info = {
                        "purchase_unit": spoon_search_result.purchase_unit,
                        "purchase_quantity": spoon_search_result.purchase_quantity,
                        "purchase_cost": purchase_cost,
                        "min_purchase_threshold": spoon_search_result.min_purchase_threshold,
                        "supplier": "Spoonacular + AI Estimate"
                    }
                    purchase_info_json = json.dumps(purchase_info)
                    
                    if spoon_search_result.unit_conversions:
                        unit_conversions_json = json.dumps(spoon_search_result.unit_conversions)
                
                # Determine decay rate and shelf life
                decay_rate, shelf_life = self.ingredient_processor.determine_decay_rate_and_shelf_life(
                    standardized_name, ai_category
                )
                
                # Create fully enriched ingredient data (keeping original name, not Spoonacular name)
                ingredient_data = IngredientData(
                    name=standardized_name,  # Keep our original standardized name, NOT Spoonacular's name
                    calories=calories,
                    protein=protein,
                    fat=fat,
                    carbohydrates=carbs,
                    sugar=sugar,
                    category=ai_category,  # Use OpenAI category
                    external_id=str(spoon_ingredient_id),  # Store Spoonacular ID for reference
                    tag_names=[],  # Can add tags later if needed
                    consistency=spoon_search_result.consistency or "solid",
                    possible_units=spoon_search_result.possible_units or ["cup", "tbsp", "tsp", "oz", "g"],
                    # Cost and purchase information
                    estimated_cost_value=spoon_search_result.estimated_cost_per_unit,
                    estimated_cost_unit=spoon_search_result.cost_unit,
                    purchase_info=purchase_info_json,
                    unit_conversions=unit_conversions_json,
                    # Shelf life information
                    default_decay_rate=decay_rate,
                    typical_shelf_life_days=shelf_life,
                    # Mark as enriched since we have Spoonacular data
                    needs_enrichment=False
                )
                
                self._log_and_print(f"   ✅ ENRICHMENT COMPLETE: '{standardized_name}' → Category: {ai_category}")
                self._log_and_print(f"   📊 Full nutrition: {calories}cal, {protein}g protein, {fat}g fat, {carbs}g carbs, {sugar}g sugar")
                self._log_and_print(f"   💰 Cost: ${spoon_search_result.estimated_cost_per_unit:.6f}/gram" if spoon_search_result.estimated_cost_per_unit else "   💰 Cost: N/A")
                self._log_and_print(f"   🕐 Shelf life: {decay_rate} decay, {shelf_life} days")
            else:
                self._log_and_print(f"   ❌ Not found in Spoonacular")
                # Still get category from AI even without Spoonacular data
                self._log_and_print(f"   🤖 STEP 2: Getting category from OpenAI (no Spoonacular data available)...")
                ai_category = self.get_ingredient_category_from_ai(standardized_name)
                
                # Determine decay rate and shelf life based on category
                decay_rate, shelf_life = self.ingredient_processor.determine_decay_rate_and_shelf_life(
                    standardized_name, ai_category
                )
                
                ingredient_data = IngredientData(
                    name=standardized_name,
                    category=ai_category,
                    tag_names=["Needs Review"],  # Flag for manual review since no Spoonacular data
                    default_decay_rate=decay_rate,
                    typical_shelf_life_days=shelf_life,
                    needs_enrichment=True  # Mark for future enrichment
                )
                self._log_and_print(f"   🕐 Shelf life: {decay_rate} decay, {shelf_life} days")
            
            # Create the ingredient using the working create method
            created_id = self.ingredient_processor.create_ekitchen_ingredient(ingredient_data)
            
            if created_id:
                self.global_ingredients_cache[standardized_name] = created_id
                self._log_and_print(f"   ✨ Created enriched ingredient '{standardized_name}' → {created_id}")
                return created_id
            else:
                self._log_and_print(f"❌ Failed to create global ingredient '{standardized_name}'", 'error')
                return None
                
        except Exception as e:
            self._log_and_print(f"❌ Error with global ingredient '{standardized_name}': {e}", 'error')
            return None
    
    def get_ingredient_category_from_ai(self, ingredient_name: str) -> str:
        """Use OpenAI to categorize ingredient into one of the 9 main categories"""
        
        if not self.openai_client:
            self._log_and_print("❌ OpenAI client not available for categorization", 'error')
            return "other"  # Default fallback
        
        try:
            self._log_and_print(f"   🤖 Asking OpenAI to categorize: '{ingredient_name}'")
            
            # Create prompt for ingredient categorization
            prompt = f"""
Categorize this ingredient into one of these 9 main categories. Respond with ONLY the category name (no explanation):

Categories:
1. proteins - meat, fish, poultry, eggs, tofu, beans, nuts, etc.
2. dairy - milk, cheese, yogurt, butter, cream, etc. 
3. vegetables - all vegetables including onions, garlic, peppers, etc.
4. fruits - all fresh and dried fruits
5. grains - rice, wheat, flour, bread, pasta, oats, etc.
6. spices - herbs, spices, seasonings (dried/fresh herbs, salt, pepper, etc.)
7. condiments - sauces, oils, vinegars, dressings, etc.
8. beverages - drinks, broths, stocks, etc.
9. other - anything that doesn't fit the above categories

Ingredient: {ingredient_name}

Category:"""

            # Make OpenAI API call with short timeout
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a food categorization expert. Respond with only the category name."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,  # Very short response needed
                temperature=0.1,  # Low temperature for consistent results
                timeout=15  # Quick timeout
            )
            
            category = response.choices[0].message.content.strip().lower()
            
            # Validate the category is one of our valid options
            valid_categories = ['proteins', 'dairy', 'vegetables', 'fruits', 'grains', 'spices', 'condiments', 'beverages', 'other']
            
            if category in valid_categories:
                self._log_and_print(f"   ✅ OpenAI categorized '{ingredient_name}' as: {category}")
                return category
            else:
                self._log_and_print(f"   ⚠️ OpenAI returned invalid category '{category}', defaulting to 'other'")
                return "other"
                
        except Exception as e:
            self._log_and_print(f"   ❌ OpenAI categorization failed for '{ingredient_name}': {e}")
            return "other"  # Default fallback
    
    def process_ingredients_enhanced(self, raw_ingredients: List[str], allow_ingredient_skipping: bool = False) -> Tuple[Dict[str, Any], Dict[str, str], List[Dict], bool]:
        """Enhanced ingredient processing with AI standardization, proper quantities/units, and singularization
        
        Args:
            raw_ingredients: List of raw ingredient strings
            allow_ingredient_skipping: Allow interactive ingredient skipping
            
        Returns:
            Tuple containing:
            - Dict[str, Any]: Processed ingredients data
            - Dict[str, str]: Ingredient name to ID mapping
            - List[Dict]: Formatted ingredients for recipe creation
            - bool: True if ingredients were skipped by user
        """
        
        self._log_and_print(f"🚀 Starting enhanced ingredient processing for {len(raw_ingredients)} ingredients...")
        self._log_and_print(f"DEBUG: Interactive skipping enabled: {allow_ingredient_skipping}", 'debug')
        
        processed_ingredients = {}
        ingredient_id_map = {}
        formatted_ingredients = []
        ingredients_skipped_by_user = False
        
        for i, ingredient_text in enumerate(raw_ingredients, 1):
            self._log_and_print(f"\n   🔍 Processing ingredient {i}: '{ingredient_text}'")
            
            # Interactive ingredient skipping
            skip_this_ingredient = False
            if allow_ingredient_skipping:
                while True:
                    print(f"\n📋 Ingredient: '{ingredient_text}'")
                    print("Options:")
                    print("  1. Process this ingredient (default)")
                    print("  2. Skip this ingredient")
                    print("  3. Skip remaining ingredients and abort recipe")
                    
                    try:
                        choice = input("Choose option (1/2/3): ").strip()
                        if choice == "" or choice == "1":
                            # Process normally
                            break
                        elif choice == "2":
                            print(f"⏭️  Skipping ingredient: '{ingredient_text}'")
                            self._log_and_print(f"   '{ingredient_text}' → SKIPPED BY USER")
                            skip_this_ingredient = True
                            ingredients_skipped_by_user = True
                            break
                        elif choice == "3":
                            print(f"⏹️  User chose to skip remaining ingredients and abort recipe")
                            self._log_and_print("⏹️  Recipe processing aborted by user (skip remaining ingredients)")
                            ingredients_skipped_by_user = True
                            return {}, {}, [], ingredients_skipped_by_user
                        else:
                            print("❌ Invalid choice. Please enter 1, 2, or 3.")
                            continue
                    except (EOFError, KeyboardInterrupt):
                        print(f"\n⏹️  Recipe processing aborted by user")
                        ingredients_skipped_by_user = True
                        return {}, {}, [], ingredients_skipped_by_user
            
            # Skip processing if user chose to skip this ingredient
            if skip_this_ingredient:
                continue
            
            # Parse quantity and unit from the text
            parsed = self.parse_ingredient_quantity_and_unit(ingredient_text)
            quantity = parsed['quantity']
            unit = parsed['unit']
            self._log_and_print(f"   📏 Parsed: {quantity} {unit}")
            
            # Standardize the ingredient name with AI and get reference_as
            ai_result = self.standardize_ingredient_with_ai(ingredient_text)
            standardized_name = ai_result["standardized_name"]
            reference_as = ai_result["reference_as"]
            self._log_and_print(f"   🤖 AI processed: '{ingredient_text}' → standardized: '{standardized_name}', reference: '{reference_as}'")

            # Check against non-ingredient blocklist
            if standardized_name.lower() in NON_INGREDIENT_BLOCKLIST:
                self._log_and_print(f"   ⛔ Skipping non-ingredient: {standardized_name}")
                continue

            # Get or create global ingredient
            global_ingredient_id = self.get_or_create_global_ingredient_enhanced(standardized_name)
            
            if global_ingredient_id:
                # Create recipe ingredient data with AI-generated reference_as
                recipe_ingredient = {
                    "ingredient_id": global_ingredient_id,
                    "quantity": quantity,
                    "unit": unit,
                    "reference_as": reference_as,  # Use AI-generated reference for better recipe context
                    "extra_comment": "",
                    "section_name": ""
                }
                formatted_ingredients.append(recipe_ingredient)
                
                # Add to mappings for compatibility
                ingredient_id_map[standardized_name] = global_ingredient_id
                processed_ingredients[standardized_name] = IngredientData(
                    id=global_ingredient_id,
                    name=standardized_name,
                    category='other',  # Will be enriched later
                    tag_names=[],  # Fixed: was 'tags', should be 'tag_names'
                    # Note: nutrition is not a field in IngredientData
                )
                
                self._log_and_print(f"   ✅ Successfully processed: {standardized_name} → {global_ingredient_id}")
            else:
                self._log_and_print(f"   ❌ Failed to process ingredient: {ingredient_text}", 'error')
        
        self._log_and_print(f"\n✅ Enhanced processing complete: {len(formatted_ingredients)}/{len(raw_ingredients)} ingredients processed")
        
        return processed_ingredients, ingredient_id_map, formatted_ingredients, ingredients_skipped_by_user
    
    def generate_ai_decisions(self, recipe_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use OpenAI to make AI-driven decisions about the recipe with timeout and retry"""
        self._log_and_print("🤖 Generating AI decisions for recipe...")
        
        if not self.openai_client:
            self._log_and_print("❌ OpenAI client not initialized - recipe processing will fail", 'error')
            return None
        
        # Retry logic: 2 attempts with 3-minute timeout each
        max_attempts = 2
        timeout_seconds = 180  # 3 minutes
        
        for attempt in range(1, max_attempts + 1):
            try:
                self._log_and_print(f"🔄 AI decision attempt {attempt}/{max_attempts} (timeout: {timeout_seconds}s)")
                
                # Create comprehensive prompt for all AI decisions
                prompt = self._create_ai_decision_prompt(recipe_data)
                
                response = self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are an expert culinary assistant for eKitchen, a cozy home cooking platform. Provide JSON responses only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2000,
                    timeout=timeout_seconds  # 3-minute timeout
                )
                
                # Parse AI response
                ai_decisions = json.loads(response.choices[0].message.content)
                self._log_and_print(f"✅ AI decisions generated successfully on attempt {attempt}")
                return ai_decisions
                
            except json.JSONDecodeError as e:
                self._log_and_print(f"❌ Attempt {attempt}: Failed to parse AI response as JSON: {e}", 'error')
                if attempt == max_attempts:
                    self._log_and_print("❌ All attempts failed - recipe processing will fail", 'error')
                    return None
                
            except Exception as e:
                if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                    self._log_and_print(f"⏰ Attempt {attempt}: AI decision generation timed out after {timeout_seconds}s", 'error')
                else:
                    self._log_and_print(f"❌ Attempt {attempt}: OpenAI API call failed: {e}", 'error')
                
                if attempt == max_attempts:
                    self._log_and_print("❌ All attempts failed - recipe processing will fail", 'error')
                    return None
                else:
                    self._log_and_print(f"🔄 Retrying in 5 seconds...")
                    time.sleep(5)
        
        # Should not reach here but safety net
        self._log_and_print("❌ Unexpected failure in AI decision generation", 'error')
        return None
    
    def _create_ai_decision_prompt(self, recipe_data: Dict[str, Any]) -> str:
        """Create comprehensive prompt for AI decisions"""
        return f"""
Please analyze this recipe and provide decisions in JSON format:

RECIPE DATA:
Title: {recipe_data['title']}
Description: {recipe_data.get('description', '')}
Ingredients: {recipe_data['ingredients']}
Instructions: {recipe_data['instructions']}
Prep Time: {recipe_data['prep_time']} minutes (0 = not specified, estimate needed)
Cook Time: {recipe_data['cook_time']} minutes (0 = not specified, estimate needed)
Total Time: {recipe_data['total_time']} minutes (0 = not specified, estimate needed)
Servings: {recipe_data['yields']}

REQUIRED JSON RESPONSE FORMAT:
{{
  "difficulty": "Easy|Medium|Hard",
  "cuisine": "cuisine_type",
  "tags": ["tag1", "tag2", "tag3"],
  "cozy_description": "Recipe description rewritten in eKitchen's approachable brand voice...",
  "cozy_instructions": [
    "Step 1 instruction rewritten in warm, cozy language...",
    "Step 2 instruction rewritten in warm, cozy language..."
  ],
  "dalle_prompt": "Professional food photography prompt for DALL-E...",
  "category": "breakfast|lunch|dinner|snack|dessert",
  "estimated_prep_time_minutes": number (only if original prep_time is 0 or missing),
  "estimated_cook_time_minutes": number (only if original cook_time is 0 or missing),
  "estimated_total_time_minutes": number (only if original total_time is 0 or missing)
}}

GUIDELINES:
1. DIFFICULTY: Easy (≤5 ingredients, ≤30min, simple techniques), Medium (6-12 ingredients, 30-90min), Hard (>12 ingredients, >90min, complex techniques)

2. CUISINE: Identify the cuisine type (Italian, Mexican, American, Thai, etc.)

3. TAGS: Include 5-8 relevant tags like dietary restrictions (gluten-free, dairy-free, vegan), cooking method (baked, fried, grilled), meal type, cuisine, etc.

4. TIME ESTIMATION (only if times are 0 or missing):
   - Analyze the ingredients and cooking steps to estimate realistic times
   - PREP_TIME: Chopping, mixing, measuring (usually 5-30 minutes)
   - COOK_TIME: Active cooking time (stovetop, oven, etc.)
   - TOTAL_TIME: Prep + Cook + any resting/cooling time
   - Be realistic but practical for home cooks
   - Examples: Simple pasta (10 prep, 15 cook, 25 total), Roasted chicken (15 prep, 60 cook, 75 total)

5. COZY_DESCRIPTION: Rewrite the recipe description in eKitchen's approachable, confident brand voice:
   - Keep it concise but appetizing (2-3 sentences max)
   - Focus on what makes this dish special or comforting
   - Use warm but professional language that builds excitement
   - Mention key flavors, textures, or cooking techniques
   - Sound inviting and achievable for home cooks
   - Avoid overly flowery language - stay authentic and helpful

6. COZY_INSTRUCTIONS: Rewrite each instruction step in eKitchen's approachable, confident brand voice:
   - Keep instructions clear, precise, and actionable
   - Use warm but professional language ("gently fold", "carefully season")
   - Maintain all original technical details and measurements
   - Add helpful tips where appropriate ("until fragrant", "until golden brown")
   - Preserve the exact cooking method and nuance from the original
   - Sound encouraging but scientifically accurate

7. DALLE_PROMPT: Create a detailed prompt for food photography:
   - Focus on homey, cozy kitchen atmosphere (NOT restaurant-style)
   - Mention "warm family kitchen" or "cozy home setting"
   - Include "natural lighting" and "inviting presentation"
   - Describe the dish appearance, garnishes, and mood
   - End with "warm, inviting home cooking photography"

8. CATEGORY: Choose the most appropriate meal category

Respond with ONLY the JSON object, no additional text.
"""
    
    def _fallback_ai_decisions(self, recipe_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback AI decisions when OpenAI is unavailable"""
        self._log_and_print("🔄 Using fallback AI decisions...")
        
        # Simple rule-based decisions
        ingredient_count = len(recipe_data['ingredients'])
        total_time = recipe_data['total_time']
        
        if ingredient_count <= 5 and total_time <= 30:
            difficulty = "Easy"
        elif ingredient_count <= 12 and total_time <= 90:
            difficulty = "Medium"
        else:
            difficulty = "Hard"
        
        # Basic tag generation
        tags = ["homemade", "comfort-food"]
        if any("chicken" in ing.lower() for ing in recipe_data['ingredients']):
            tags.append("chicken")
        if any("vegetarian" in recipe_data['title'].lower() for _ in [1]):
            tags.append("vegetarian")
        
        # Simple instruction rewriting
        cozy_instructions = []
        for i, instruction in enumerate(recipe_data['instructions']):
            cozy_instruction = instruction.replace("Cook", "Let it cook with love")
            cozy_instruction = cozy_instruction.replace("Mix", "Lovingly mix together")
            cozy_instructions.append(cozy_instruction)

        # Estimate times if missing (rule-based fallback)
        fallback_times = {}
        if not recipe_data['prep_time'] or recipe_data['prep_time'] == 0:
            # Base prep on ingredient count
            fallback_times['estimated_prep_time_minutes'] = min(5 + (ingredient_count * 2), 30)
        if not recipe_data['cook_time'] or recipe_data['cook_time'] == 0:
            # Base cook on difficulty
            if difficulty == "Easy":
                fallback_times['estimated_cook_time_minutes'] = 15
            elif difficulty == "Medium":
                fallback_times['estimated_cook_time_minutes'] = 30
            else:
                fallback_times['estimated_cook_time_minutes'] = 60
        if not recipe_data['total_time'] or recipe_data['total_time'] == 0:
            # Sum prep + cook if both estimated
            prep = fallback_times.get('estimated_prep_time_minutes', recipe_data['prep_time'] or 0)
            cook = fallback_times.get('estimated_cook_time_minutes', recipe_data['cook_time'] or 0)
            fallback_times['estimated_total_time_minutes'] = prep + cook

        result = {
            "difficulty": difficulty,
            "cuisine": "American",  # Default
            "tags": tags,
            "cozy_description": recipe_data.get('description', f"A delicious homemade {recipe_data['title']} that brings comfort and flavor to your table."),
            "cozy_instructions": cozy_instructions,
            "dalle_prompt": f"A cozy home-cooked {recipe_data['title']} served in a warm family kitchen with natural lighting, inviting home cooking photography",
            "category": "dinner"  # Default
        }

        # Add estimated times if calculated
        result.update(fallback_times)
        return result
    
    def generate_dalle_prompt_from_recipe(self, recipe_data: Dict[str, Any]) -> Optional[str]:
        """Generate DALL-E prompt using new recipe website photography template"""
        try:
            recipe_title = recipe_data.get('title', 'Unknown Recipe')
            ingredients = recipe_data.get('ingredients', [])
            description = recipe_data.get('description', '')
            
            self._log_and_print(f"🎨 Generating recipe website style prompt for {recipe_title}...")
            
            # Create ingredients summary for the prompt
            main_ingredients = ', '.join(ingredients[:8]) if ingredients else 'main ingredients'
            
            # Use the new recipe website photography template
            prompt = self._create_recipe_website_prompt(recipe_title, main_ingredients, description)
            
            self._log_and_print(f"✅ Recipe website prompt generated: {prompt[:100]}...")
            return prompt
            
        except Exception as e:
            self._log_and_print(f"❌ Recipe website prompt generation failed: {e}", 'error')
            return None

    def _create_recipe_website_prompt(self, recipe_title: str, ingredients: str, description: str) -> str:
        """Create DALL-E prompt using recipe website food photography template"""
        
        # Main Dish Focus - describe the recipe in detail
        main_focus = f"{recipe_title}"
        
        # Add preparation details based on common cooking terms
        if 'baked' in recipe_title.lower() or 'roasted' in recipe_title.lower():
            texture_desc = "golden and crispy"
        elif 'fried' in recipe_title.lower():
            texture_desc = "crispy and golden-brown"
        elif 'grilled' in recipe_title.lower():
            texture_desc = "charred and juicy"
        elif 'sauced' in recipe_title.lower() or 'buffalo' in recipe_title.lower():
            texture_desc = "coated in glossy sauce"
        else:
            texture_desc = "perfectly prepared"
        
        # Composition & Framing
        composition = "Overhead composition, zoomed in on the serving dish, the food fills the frame with natural presentation"
        
        # Supporting Ingredients & Props - create realistic supporting elements
        supporting_elements = []
        
        # Add relevant props based on dish type
        if 'wings' in recipe_title.lower() or 'buffalo' in recipe_title.lower():
            supporting_elements = ["fresh celery sticks", "a small bowl of ranch dipping sauce", "a pinch bowl of salt", "folded linen napkin with utensils"]
        elif 'pasta' in recipe_title.lower() or 'noodles' in recipe_title.lower():
            supporting_elements = ["grated parmesan cheese", "fresh herbs", "a wooden spoon", "linen kitchen towel"]
        elif 'soup' in recipe_title.lower() or 'curry' in recipe_title.lower():
            supporting_elements = ["fresh cilantro garnish", "a ladle", "crusty bread slices", "cloth napkin"]
        elif 'salad' in recipe_title.lower():
            supporting_elements = ["wooden serving utensils", "small bowl of dressing", "fresh lemon wedges", "clean kitchen cloth"]
        else:
            supporting_elements = ["fresh herbs for garnish", "serving utensils", "a folded napkin", "small condiment bowl"]
        
        supporting_text = f"Surrounded by {', '.join(supporting_elements)}"
        
        # Lighting & Color Style
        lighting = "Soft natural daylight from the side, warm even lighting, vibrant but true-to-life colors, no harsh shadows"
        
        # Mood / Aesthetic
        aesthetic = "Styled like modern recipe blogs, cozy kitchen atmosphere, rustic but clean, highly appetizing presentation"
        
        # Combine all elements into the final prompt
        full_prompt = f"{composition} of {main_focus}, {texture_desc}. The dish is arranged in a rustic serving dish, {supporting_text}. {lighting}. {aesthetic}."
        
        return full_prompt

    def _generate_ai_dalle_prompt(self, recipe_data: Dict[str, Any]) -> str:
        """Fallback AI-generated DALL-E prompt when baseline image unavailable"""
        recipe_title = recipe_data.get('title', 'Unknown Recipe')
        ingredients = recipe_data.get('ingredients', [])
        
        # Create basic prompt with style requirements
        ingredients_text = ', '.join(ingredients[:5]) if ingredients else 'main ingredients'
        
        return f"Close-up, vibrant {recipe_title} with {ingredients_text}, bright saturated colors, tight crop, dish fills the frame, warm even lighting, overhead view, recipe app photography style, home cooking aesthetic"
    
    def _single_image_vision_analysis(self, image_url: str, recipe_title: str) -> Optional[str]:
        """Fallback single-image vision analysis"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user", 
                        "content": [
                            {
                                "type": "text", 
                                "text": f"""Analyze this food image and create a DALL-E prompt that would recreate a similar realistic food photograph. Focus ONLY on:

1. The food itself - colors, textures, presentation
2. Plating and serving style  
3. Lighting and photography angle
4. Any garnishes or accompaniments visible

Do NOT include:
- Kitchen backgrounds or environments
- People or hands
- Cozy/homey descriptions
- Cooking equipment

Recipe: {recipe_title}

Return ONLY the DALL-E prompt, nothing else."""
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url}
                            }
                        ]
                    }
                ],
                max_tokens=200,
                timeout=60
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self._log_and_print(f"❌ Single-image vision analysis failed: {e}", 'error')
            return None

    def _enhance_dalle_prompt_for_vibrancy(self, original_prompt: str) -> str:
        """Enhance DALL-E prompt to ensure bright, vibrant, recipe app style with tight crop"""
        # Keywords that indicate the prompt already has good style guidance
        good_keywords = ['vibrant', 'bright', 'saturated', 'colorful', 'warm lighting', 'recipe app', 'home cooking']
        crop_keywords = ['close-up', 'tight crop', 'zoomed-in', 'macro', 'fills the frame']
        
        # Check if prompt already has good style guidance
        prompt_lower = original_prompt.lower()
        has_good_style = any(keyword in prompt_lower for keyword in good_keywords)
        has_good_crop = any(keyword in prompt_lower for keyword in crop_keywords)
        
        if has_good_style and has_good_crop:
            # Already has both style and crop guidance, minimal enhancement
            return f"{original_prompt}, vibrant saturated colors, tight crop, dish fills frame"
        elif has_good_style:
            # Has style but needs crop guidance
            return f"{original_prompt}, close-up view, tight crop, dish fills the frame, minimal background, zoomed-in food photography"
        else:
            # Needs major style and crop enhancement
            return f"Close-up, vibrant, colorful {original_prompt} with bright saturated colors, warm even lighting, tight crop, dish fills the frame, minimal background, overhead view, recipe app photography style, home cooking aesthetic, zoomed-in macro food photography, NOT wide shot, NOT lots of background, NOT dark or moody, NOT fine dining style"

    def generate_recipe_image_dalle(self, dalle_prompt: str, save_path: str) -> bool:
        """Generate recipe image using DALL-E API with enhanced style enforcement"""
        self._log_and_print(f"🎨 Generating DALL-E image with prompt: {dalle_prompt[:100]}...")
        
        if not self.openai_client:
            self._log_and_print("❌ OpenAI client not initialized", 'error')
            return False
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Enhance prompt with mandatory style requirements if not already present
            enhanced_prompt = self._enhance_dalle_prompt_for_vibrancy(dalle_prompt)
            self._log_and_print(f"🌟 Enhanced prompt: {enhanced_prompt[:150]}...")
            
            # Generate image
            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=enhanced_prompt,
                size="1024x1024",
                quality="hd",
                style="natural",  # Natural style for home cooking feel
                n=1
            )
            
            # Download and save image
            image_url = response.data[0].url
            image_response = requests.get(image_url, timeout=30)
            image_response.raise_for_status()
            
            # DALL-E returns PNG, so save with .png extension
            if save_path.endswith('.jpg') or save_path.endswith('.jpeg'):
                save_path = save_path.rsplit('.', 1)[0] + '.png'
            
            with open(save_path, 'wb') as f:
                f.write(image_response.content)
            
            self._log_and_print(f"✅ DALL-E image saved: {save_path}")
            return True
            
        except Exception as e:
            self._log_and_print(f"❌ DALL-E image generation failed: {e}", 'error')
            return False
    
    def _refresh_ekitchen_tokens(self) -> bool:
        """Refresh eKitchen authentication tokens before API calls"""
        if not self.ekitchen_refresh_token:
            self._log_and_print("⚠️  No refresh token available, skipping token refresh", 'warning')
            return False

        # Call the ingredient processor's refresh method
        if self.ingredient_processor.refresh_authentication():
            # Update local tokens from ingredient processor
            self.ekitchen_token = self.ingredient_processor.access_token
            self.ekitchen_refresh_token = self.ingredient_processor.refresh_token
            return True
        return False

    def _ensure_ekitchen_auth(self) -> bool:
        """Guarantee a usable eKitchen token, re-authenticating if it has been lost.

        The ingredient_processor owns the authoritative session; we delegate to its
        re-auth (refresh → full re-login from stored admin creds) and re-sync our
        local token copy so the two never drift. Without this, our copy — taken once
        at init — goes stale the moment the ingredient processor re-authenticates,
        and every recipe write would fail with a token the backend already rejected.
        Returns True if a valid token is available.
        """
        ip = self.ingredient_processor
        if not ip.access_token and not ip._reauthenticate():
            return False
        self.ekitchen_token = ip.access_token
        self.ekitchen_refresh_token = ip.refresh_token
        return True

    def create_ekitchen_recipe(self, recipe_data: Dict[str, Any], ai_decisions: Dict[str, Any],
                             formatted_ingredients: List[Dict[str, str]],
                             nutrition_data: Dict[str, float], user_id: Optional[str] = None) -> Optional[str]:
        """Create recipe in eKitchen database using direct API call"""
        self._log_and_print(f"🏗️  Creating recipe in eKitchen: {recipe_data['title']}")

        # Guarantee a fresh, valid token (re-syncs from the ingredient processor's
        # authoritative session, re-authenticating if it has expired mid-run).
        if not self._ensure_ekitchen_auth():
            self._log_and_print("❌ Not authenticated with eKitchen and re-auth failed", 'error')
            return None
        
        # Format steps for eKitchen
        steps = []
        for i, instruction in enumerate(ai_decisions['cozy_instructions']):
            steps.append({
                "position": i + 1,
                "template": instruction
            })
        
        # Prepare recipe data for API
        create_data = {
            "name": recipe_data['title'],
            "description": ai_decisions.get('cozy_description', recipe_data.get('description', '')),
            "steps": steps,
            "prep_time_minutes": recipe_data['prep_time'],
            "cook_time_minutes": recipe_data['cook_time'],
            "total_time_minutes": recipe_data['total_time'],
            "num_servings": recipe_data['yields'],
            "cuisine": ai_decisions['cuisine'],
            "difficulty": ai_decisions['difficulty'],
            "inspired_by_url": recipe_data['url'],
            "ingredients": formatted_ingredients,
            "tag_names": ai_decisions['tags'],

            # Nutrition data
            "calories": nutrition_data['calories'],
            "protein": nutrition_data['protein'],
            "fat": nutrition_data['fat'],
            "carbohydrates": nutrition_data['carbohydrates'],
            "fiber": nutrition_data['fiber'],
            "sugar": nutrition_data['sugar'],

            # User import tracking
            # All three fields set together when user_id is provided
            "user_created": user_id is not None,
            "created_by_user_id": user_id,  # Will be user ID or None
            "imported_from_url": recipe_data['url'] if user_id else None
        }
        
        for attempt in range(2):
            try:
                response = requests.post(
                    f"{self.ingredient_processor.ekitchen_base_url}/global-recipes",
                    headers={
                        'Authorization': f'Bearer {self.ekitchen_token}',
                        'Content-Type': 'application/json'
                    },
                    json=create_data,
                    timeout=30
                )

                response.raise_for_status()
                result = response.json()

                recipe_id = result.get('id')
                if recipe_id:
                    self._log_and_print(f"✅ Recipe created successfully: ID {recipe_id}")
                    return recipe_id
                else:
                    self._log_and_print(f"❌ Recipe creation failed: {result}", 'error')
                    return None

            except requests.exceptions.HTTPError as e:
                # Token expired/rejected mid-run — re-authenticate and retry ONCE.
                status_code = e.response.status_code if e.response is not None else None
                if status_code in (401, 403) and attempt == 0 and self._ensure_ekitchen_auth():
                    self._log_and_print("🔄 eKitchen token rejected creating recipe; re-authenticated, retrying...", 'warning')
                    continue
                self._log_and_print(f"❌ HTTP Error creating recipe: {e}", 'error')
                return None
            except requests.exceptions.RequestException as e:
                self._log_and_print(f"❌ HTTP Error creating recipe: {e}", 'error')
                return None
            except Exception as e:
                self._log_and_print(f"❌ Error creating recipe: {e}", 'error')
                return None
    
    def upload_recipe_image(self, recipe_id: str, image_path: str) -> bool:
        """Upload recipe image to eKitchen"""
        self._log_and_print(f"📤 Uploading image for recipe {recipe_id}: {image_path}")
        
        if not self._ensure_ekitchen_auth():
            self._log_and_print("❌ Not authenticated with eKitchen", 'error')
            return False

        if not os.path.exists(image_path):
            self._log_and_print(f"❌ Image file not found: {image_path}", 'error')
            return False
        
        try:
            # Detect correct content type based on file extension
            content_type = 'image/jpeg'
            if image_path.lower().endswith('.png'):
                content_type = 'image/png'
            elif image_path.lower().endswith(('.jpg', '.jpeg')):
                content_type = 'image/jpeg'
            
            with open(image_path, 'rb') as f:
                # Use correct content type for the file
                files = {'image': (os.path.basename(image_path), f, content_type)}
                data = {'image_type': 'hero'}
                
                response = requests.post(
                    f"{self.ingredient_processor.ekitchen_base_url}/global-recipes/{recipe_id}/images",
                    headers={'Authorization': f'Bearer {self.ekitchen_token}'},
                    files=files,
                    data=data,
                    timeout=60
                )
            
            response.raise_for_status()
            self._log_and_print(f"✅ Image uploaded successfully")
            return True
            
        except requests.exceptions.RequestException as e:
            self._log_and_print(f"❌ HTTP Error uploading image: {e}", 'error')
            return False
        except Exception as e:
            self._log_and_print(f"❌ Error uploading image: {e}", 'error')
            return False
    
    def _resolve_ambiguous_matches_for_recipe(self, recipe_id: str, recipe_name: str) -> None:
        """
        Auto-resolve ambiguous step matches for a specific recipe using GPT-4o-mini.

        This is best-effort: failures are logged but do not block the ingestion pipeline.
        """
        if not self.openai_client:
            self._log_and_print("⚠️  OpenAI client not available, skipping ambiguous match resolution", 'warning')
            return

        if not self._ensure_ekitchen_auth():
            self._log_and_print("⚠️  Not authenticated with eKitchen, skipping ambiguous match resolution", 'warning')
            return

        base_url = self.ingredient_processor.ekitchen_base_url

        # Fetch ambiguous matches for this specific recipe using the filter query param
        resp = requests.get(
            f"{base_url}/global-recipes/ambiguous-step-matches",
            headers={"Authorization": f"Bearer {self.ekitchen_token}"},
            params={"filter": f"recipe_id = '{recipe_id}'", "limit": "100"},
            timeout=30,
        )
        resp.raise_for_status()
        matches = resp.json()

        # Filter to only unresolved matches (in case the API returns all)
        unresolved = [m for m in matches if not m.get("resolved_match")]

        if not unresolved:
            self._log_and_print("✅ No ambiguous step matches to resolve")
            return

        self._log_and_print(f"   Found {len(unresolved)} ambiguous match(es) to resolve")

        # Fetch the full recipe for context (ingredients list, etc.)
        recipe_resp = requests.get(
            f"{base_url}/global-recipes/{recipe_id}",
            headers={"Authorization": f"Bearer {self.ekitchen_token}"},
            timeout=30,
        )
        recipe_resp.raise_for_status()
        recipe = recipe_resp.json()

        # Extract ingredient names for the prompt
        ingredients = recipe.get("ingredients", [])
        ingredient_names = [ing.get("ingredient_name", ing.get("name", "")) for ing in ingredients]
        ingredients_list = ", ".join(ingredient_names) if ingredient_names else "N/A"

        resolved_count = 0

        for match in unresolved:
            match_id = match["id"]
            step_position = match.get("step_position", "?")
            template = match.get("template", "")
            ambiguous_word = match.get("ambiguous_word", "")
            possible_matches = match.get("possible_matches", [])

            if not possible_matches:
                self._log_and_print(f"   SKIP: No possible matches for \"{ambiguous_word}\" in step {step_position}", 'warning')
                continue

            try:
                # Build prompt (same logic as scripts/resolve_ambiguous_matches.py)
                prompt = (
                    f"A recipe step contains an ambiguous ingredient reference that could match multiple ingredients.\n\n"
                    f"Recipe: {recipe_name}\n"
                    f"All ingredients in this recipe: {ingredients_list}\n"
                    f"Step {step_position}: \"{template}\"\n"
                    f"Ambiguous word in the step: \"{ambiguous_word}\"\n"
                    f"Possible ingredient matches: {', '.join(possible_matches)}\n\n"
                    f"Based on the cooking context of this step, which specific ingredient does "
                    f"\"{ambiguous_word}\" most likely refer to?\n\n"
                    f"Respond with ONLY the exact ingredient name from the possible matches list. Nothing else."
                )

                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100,
                    temperature=0.0,
                )

                answer = response.choices[0].message.content.strip()

                # Validate the answer is one of the possible matches
                resolved_match = None
                if answer in possible_matches:
                    resolved_match = answer
                else:
                    # Try case-insensitive match
                    for pm in possible_matches:
                        if answer.lower() == pm.lower():
                            resolved_match = pm
                            break

                    # Try partial match as fallback
                    if not resolved_match:
                        for pm in possible_matches:
                            if answer.lower() in pm.lower() or pm.lower() in answer.lower():
                                resolved_match = pm
                                break

                if not resolved_match:
                    self._log_and_print(
                        f"   SKIP: GPT returned \"{answer}\" which doesn't match any of {possible_matches} "
                        f"for \"{ambiguous_word}\" in step {step_position}",
                        'warning'
                    )
                    continue

                # Resolve via PATCH
                patch_resp = requests.patch(
                    f"{base_url}/global-recipes/ambiguous-step-matches/{match_id}",
                    headers={
                        "Authorization": f"Bearer {self.ekitchen_token}",
                        "Content-Type": "application/json",
                    },
                    json={"resolved_match": resolved_match},
                    timeout=30,
                )
                patch_resp.raise_for_status()
                resolved_count += 1
                self._log_and_print(f"   Resolved: \"{ambiguous_word}\" -> \"{resolved_match}\" in step {step_position}")

            except Exception as e:
                self._log_and_print(f"   ERROR resolving match {match_id}: {e}", 'warning')

        self._log_and_print(f"✅ Auto-resolved {resolved_count}/{len(unresolved)} ambiguous matches for recipe '{recipe_name}'")

    def process_parsed_recipe(self, parsed_recipe: Dict[str, Any], save_images_dir: str = None,
                               use_enhanced_ingredients: bool = True, user_id: Optional[str] = None) -> 'RecipeProcessingResult':
        """
        Process a pre-parsed recipe (e.g., from video transcription).
        
        This method accepts recipe data that has already been extracted/parsed,
        skipping the URL scraping phase. Useful for video recipes or manual input.
        
        Args:
            parsed_recipe: Dict with recipe data in video parser format:
                - name: Recipe title
                - description: Recipe description
                - ingredients: List of ingredient strings
                - steps: List of instruction strings
                - servings: Number of servings (optional)
                - prep_time_minutes: Prep time (optional)
                - cook_time_minutes: Cook time (optional)
                - total_time_minutes: Total time (optional)
                - video_url or source_url: Original source URL
                - image_url: Image URL (optional)
            save_images_dir: Directory to save generated images (optional)
            use_enhanced_ingredients: Use enhanced AI ingredient processing (default: True)
            
        Returns:
            RecipeProcessingResult with success status and details
        """
        # Convert video parser format to internal recipe_data format
        recipe_data = {
            "title": parsed_recipe.get('name', 'Untitled Recipe'),
            "description": parsed_recipe.get('description', ''),
            "ingredients": parsed_recipe.get('ingredients', []),
            "instructions": parsed_recipe.get('steps', []),
            "prep_time": parsed_recipe.get('prep_time_minutes', 0) or 0,
            "cook_time": parsed_recipe.get('cook_time_minutes', 0) or 0,
            "total_time": parsed_recipe.get('total_time_minutes', 0) or 0,
            "yields": parsed_recipe.get('servings', 0) or 0,
            "image_url": parsed_recipe.get('image_url', ''),
            "author": parsed_recipe.get('source_metadata', {}).get('author', ''),
            "url": parsed_recipe.get('video_url') or parsed_recipe.get('source_url', '')
        }
        
        # Now process using the internal pipeline (same as process_recipe_autonomous but skip scraping)
        return self._process_recipe_data(recipe_data, save_images_dir, use_enhanced_ingredients, user_id)
    
    def _process_recipe_data(self, recipe_data: Dict[str, Any], save_images_dir: str = None,
                              use_enhanced_ingredients: bool = True, user_id: Optional[str] = None) -> 'RecipeProcessingResult':
        """
        Internal method to process recipe_data through the full pipeline.
        Called by both process_recipe_autonomous (after scraping) and process_parsed_recipe.
        """
        start_time = time.time()
        
        self._log_and_print("="*80)
        self._log_and_print("🚀 PROCESSING RECIPE DATA")
        self._log_and_print("="*80)
        self._log_and_print(f"🎯 Recipe: {recipe_data.get('title', 'Unknown')}")
        self._log_and_print(f"   Source: {recipe_data.get('url', 'N/A')}")
        
        try:
            # Phase 2: Process ingredients
            if use_enhanced_ingredients:
                self._log_and_print("\n🥘 PHASE 2: ENHANCED INGREDIENT PROCESSING (AI + Proper Quantities/Units)")
                processed_ingredients, ingredient_id_map, formatted_ingredients, ingredients_skipped_by_user = self.process_ingredients_enhanced(
                    recipe_data['ingredients'],
                    allow_ingredient_skipping=False  # No interactive mode for parsed recipes
                )
            else:
                self._log_and_print("\n🥘 PHASE 2: STANDARD INGREDIENT PROCESSING")
                processed_ingredients, ingredient_id_map, ingredients_skipped_by_user = self.ingredient_processor.process_recipe_ingredients(
                    recipe_data['ingredients'],
                    allow_ingredient_skipping=False
                )
                if not ingredients_skipped_by_user:
                    formatted_ingredients = self.ingredient_processor.format_ingredients_for_recipe(
                        recipe_data['ingredients'],
                        ingredient_id_map
                    )
                else:
                    formatted_ingredients = []
            
            if not ingredient_id_map:
                return RecipeProcessingResult(
                    success=False,
                    error_message="No ingredients could be processed",
                    processing_time_seconds=time.time() - start_time
                )
            
            self._log_and_print(f"✅ Processed {len(ingredient_id_map)} ingredients successfully")
            
            # Phase 3: Calculate nutrition
            self._log_and_print("\n🧮 PHASE 3: NUTRITION CALCULATION")
            nutrition_data = self.ingredient_processor.calculate_recipe_nutrition_from_map(
                recipe_data['ingredients'],
                processed_ingredients,
                ingredient_id_map,
                recipe_data['yields'] or 4  # Default to 4 servings if not specified
            )
            
            # Phase 4: Generate AI decisions
            self._log_and_print("\n🤖 PHASE 4: AI RECIPE DECISIONS")
            ai_decisions = self.generate_ai_decisions(recipe_data)

            # Apply AI-estimated times if original times are missing (0 or None)
            if ai_decisions:
                if (not recipe_data['prep_time'] or recipe_data['prep_time'] == 0) and ai_decisions.get('estimated_prep_time_minutes'):
                    recipe_data['prep_time'] = ai_decisions['estimated_prep_time_minutes']
                    self._log_and_print(f"   Using AI-estimated prep time: {recipe_data['prep_time']} minutes")

                if (not recipe_data['cook_time'] or recipe_data['cook_time'] == 0) and ai_decisions.get('estimated_cook_time_minutes'):
                    recipe_data['cook_time'] = ai_decisions['estimated_cook_time_minutes']
                    self._log_and_print(f"   Using AI-estimated cook time: {recipe_data['cook_time']} minutes")

                if (not recipe_data['total_time'] or recipe_data['total_time'] == 0) and ai_decisions.get('estimated_total_time_minutes'):
                    recipe_data['total_time'] = ai_decisions['estimated_total_time_minutes']
                    self._log_and_print(f"   Using AI-estimated total time: {recipe_data['total_time']} minutes")

            # Phase 5: Generate DALL-E image (if save_images_dir provided)
            image_path = None
            if save_images_dir:
                self._log_and_print("\n🎨 PHASE 5: DALL-E IMAGE GENERATION")
                dalle_prompt = self.generate_dalle_prompt_from_recipe(recipe_data)
                if dalle_prompt:
                    os.makedirs(save_images_dir, exist_ok=True)
                    safe_filename = re.sub(r'[^\w\s-]', '', recipe_data['title']).strip().replace(' ', '_')[:50]
                    image_path = os.path.join(save_images_dir, f"{safe_filename}.png")
                    if self.generate_recipe_image_dalle(dalle_prompt, image_path):
                        self._log_and_print(f"✅ Image saved: {image_path}")
                    else:
                        image_path = None
                        self._log_and_print("⚠️  Image generation failed, continuing without image")
            
            # Phase 6: Create recipe in eKitchen
            self._log_and_print("\n📝 PHASE 6: CREATE EKITCHEN RECIPE")
            recipe_id = self.create_ekitchen_recipe(recipe_data, ai_decisions, formatted_ingredients, nutrition_data, user_id)
            
            if not recipe_id:
                return RecipeProcessingResult(
                    success=False,
                    error_message="Failed to create recipe in eKitchen",
                    processing_time_seconds=time.time() - start_time
                )
            
            # Phase 7: Upload image if generated
            if image_path and os.path.exists(image_path):
                self._log_and_print("\n📤 PHASE 7: UPLOAD RECIPE IMAGE")
                if self.upload_recipe_image(recipe_id, image_path):
                    self._log_and_print("✅ Image uploaded successfully")
                else:
                    self._log_and_print("⚠️  Image upload failed")

            # Phase 8: Auto-resolve ambiguous step matches (best-effort)
            self._log_and_print("\n🔍 PHASE 8: AUTO-RESOLVE AMBIGUOUS STEP MATCHES")
            try:
                self._resolve_ambiguous_matches_for_recipe(recipe_id, recipe_data['title'])
            except Exception as e:
                self._log_and_print(f"⚠️  Ambiguous match resolution failed (non-blocking): {e}", 'warning')

            # Success!
            processing_time = time.time() - start_time
            self._log_and_print("\n" + "="*80)
            self._log_and_print("✅ RECIPE PROCESSING COMPLETE")
            self._log_and_print("="*80)
            self._log_and_print(f"📊 Recipe ID: {recipe_id}")
            self._log_and_print(f"📊 Recipe Name: {recipe_data['title']}")
            self._log_and_print(f"📊 Ingredients Processed: {len(ingredient_id_map)}")
            self._log_and_print(f"📊 Image Generated: {image_path is not None}")
            self._log_and_print(f"📊 Processing Time: {processing_time:.1f}s")
            
            return RecipeProcessingResult(
                success=True,
                recipe_id=recipe_id,
                recipe_name=recipe_data['title'],
                ingredients_processed=len(ingredient_id_map),
                image_generated=image_path is not None,
                processing_time_seconds=processing_time
            )
            
        except Exception as e:
            self._log_and_print(f"❌ Error processing recipe: {e}", 'error')
            import traceback
            self._log_and_print(traceback.format_exc(), 'error')
            return RecipeProcessingResult(
                success=False,
                error_message=str(e),
                processing_time_seconds=time.time() - start_time
            )

    def process_recipe_autonomous(self, recipe_url: str, save_images_dir: str = None, use_enhanced_ingredients: bool = True, allow_ingredient_skipping: bool = False, user_id: Optional[str] = None) -> RecipeProcessingResult:
        """
        Complete autonomous recipe processing pipeline
        
        Args:
            recipe_url: URL of recipe to process
            save_images_dir: Directory to save generated images (optional)
            use_enhanced_ingredients: Use enhanced AI ingredient processing (default: True)
            allow_ingredient_skipping: Allow interactive ingredient skipping (default: False)
            
        Returns:
            RecipeProcessingResult with success status and details
        """
        start_time = time.time()
        
        self._log_and_print("="*80)
        self._log_and_print("🚀 STARTING AUTONOMOUS RECIPE PROCESSING")
        self._log_and_print("="*80)
        self._log_and_print(f"🎯 Target URL: {recipe_url}")
        
        try:
            # Phase 1: Scrape recipe data
            self._log_and_print("\n📋 PHASE 1: RECIPE SCRAPING")
            recipe_data = self.scrape_recipe_from_url(recipe_url)
            if not recipe_data:
                return RecipeProcessingResult(
                    success=False,
                    error_message="Failed to scrape recipe data",
                    processing_time_seconds=time.time() - start_time
                )
            
            # Phase 2: Process ingredients
            ingredients_skipped_by_user = False
            if use_enhanced_ingredients:
                self._log_and_print("\n🥘 PHASE 2: ENHANCED INGREDIENT PROCESSING (AI + Proper Quantities/Units)")
                processed_ingredients, ingredient_id_map, formatted_ingredients, ingredients_skipped_by_user = self.process_ingredients_enhanced(
                    recipe_data['ingredients'],
                    allow_ingredient_skipping=allow_ingredient_skipping
                )
            else:
                self._log_and_print("\n🥘 PHASE 2: STANDARD INGREDIENT PROCESSING")
                processed_ingredients, ingredient_id_map, ingredients_skipped_by_user = self.ingredient_processor.process_recipe_ingredients(
                    recipe_data['ingredients'],
                    allow_ingredient_skipping=allow_ingredient_skipping
                )
                # Format ingredients for recipe creation (legacy path)
                if not ingredients_skipped_by_user:
                    formatted_ingredients = self.ingredient_processor.format_ingredients_for_recipe(
                        recipe_data['ingredients'],
                        ingredient_id_map
                    )
                else:
                    formatted_ingredients = []
            
            # Check if user skipped ingredients - if so, abort recipe processing
            if ingredients_skipped_by_user:
                self._log_and_print("\n⏹️  RECIPE PROCESSING ABORTED: User skipped ingredients")
                self._log_and_print("    Image generation and recipe creation will be skipped.")
                return RecipeProcessingResult(
                    success=False,
                    error_message="Recipe processing aborted due to ingredient skipping",
                    processing_time_seconds=time.time() - start_time
                )
            
            if not ingredient_id_map:
                return RecipeProcessingResult(
                    success=False,
                    error_message="No ingredients could be processed",
                    processing_time_seconds=time.time() - start_time
                )
            
            # Phase 3: Calculate nutrition
            self._log_and_print("\n🧮 PHASE 3: NUTRITION CALCULATION")
            nutrition_data = self.ingredient_processor.calculate_recipe_nutrition_from_map(
                recipe_data['ingredients'],
                processed_ingredients,
                ingredient_id_map,
                recipe_data['yields']
            )
            
            # Phase 4: AI decisions
            self._log_and_print("\n🤖 PHASE 4: AI DECISION GENERATION")
            ai_decisions = self.generate_ai_decisions(recipe_data)

            # Check if AI decisions failed
            if ai_decisions is None:
                self._log_and_print("❌ AI decision generation failed - stopping recipe processing", 'error')
                return RecipeProcessingResult(
                    success=False,
                    error_message="AI decision generation failed after retries",
                    processing_time_seconds=time.time() - start_time
                )

            # Apply AI-estimated times if original times are missing (0 or None)
            if (not recipe_data['prep_time'] or recipe_data['prep_time'] == 0) and ai_decisions.get('estimated_prep_time_minutes'):
                recipe_data['prep_time'] = ai_decisions['estimated_prep_time_minutes']
                self._log_and_print(f"   Using AI-estimated prep time: {recipe_data['prep_time']} minutes")

            if (not recipe_data['cook_time'] or recipe_data['cook_time'] == 0) and ai_decisions.get('estimated_cook_time_minutes'):
                recipe_data['cook_time'] = ai_decisions['estimated_cook_time_minutes']
                self._log_and_print(f"   Using AI-estimated cook time: {recipe_data['cook_time']} minutes")

            if (not recipe_data['total_time'] or recipe_data['total_time'] == 0) and ai_decisions.get('estimated_total_time_minutes'):
                recipe_data['total_time'] = ai_decisions['estimated_total_time_minutes']
                self._log_and_print(f"   Using AI-estimated total time: {recipe_data['total_time']} minutes")

            # Phase 6: Generate recipe image
            image_generated = False
            if save_images_dir:
                self._log_and_print("\n🎨 PHASE 5: IMAGE GENERATION")
                os.makedirs(save_images_dir, exist_ok=True)
                
                # Create safe filename
                safe_name = re.sub(r'[^\w\s-]', '', recipe_data['title'])
                safe_name = re.sub(r'[-\s]+', '-', safe_name)
                image_path = os.path.join(save_images_dir, f"{safe_name}.png")
                
                # Generate DALL-E prompt using baseline style and recipe data
                dalle_prompt = ai_decisions['dalle_prompt']  # fallback
                baseline_prompt = self.generate_dalle_prompt_from_recipe(recipe_data)
                if baseline_prompt:
                    dalle_prompt = baseline_prompt
                    self._log_and_print(f"🎨 Using baseline-style prompt: {dalle_prompt[:100]}...")
                else:
                    self._log_and_print("⚠️ Baseline prompt generation failed, using AI fallback")
                
                image_generated = self.generate_recipe_image_dalle(
                    dalle_prompt,
                    image_path
                )
            
            # Phase 7: Create recipe in database
            self._log_and_print("\n🏗️  PHASE 6: RECIPE CREATION")
            recipe_id = self.create_ekitchen_recipe(
                recipe_data,
                ai_decisions,
                formatted_ingredients,
                nutrition_data,
                user_id
            )
            
            if not recipe_id:
                return RecipeProcessingResult(
                    success=False,
                    error_message="Failed to create recipe in database",
                    ingredients_processed=len(ingredient_id_map),
                    image_generated=image_generated,
                    processing_time_seconds=time.time() - start_time
                )
            
            # Phase 8: Upload image (if generated)
            if image_generated and recipe_id:
                self._log_and_print("\n📤 PHASE 7: IMAGE UPLOAD")
                self.upload_recipe_image(recipe_id, image_path)
            
            # Success!
            processing_time = time.time() - start_time
            
            self._log_and_print("\n" + "="*80)
            self._log_and_print("🎉 AUTONOMOUS PROCESSING COMPLETE!")
            self._log_and_print("="*80)
            self._log_and_print(f"✅ Recipe: {recipe_data['title']}")
            self._log_and_print(f"✅ Recipe ID: {recipe_id}")
            self._log_and_print(f"✅ Ingredients Processed: {len(ingredient_id_map)}")
            self._log_and_print(f"✅ Image Generated: {image_generated}")
            self._log_and_print(f"✅ Processing Time: {processing_time:.1f} seconds")
            self._log_and_print("="*80)
            
            return RecipeProcessingResult(
                success=True,
                recipe_id=recipe_id,
                recipe_name=recipe_data['title'],
                ingredients_processed=len(ingredient_id_map),
                image_generated=image_generated,
                processing_time_seconds=processing_time
            )
            
        except Exception as e:
            error_message = f"Unexpected error during processing: {e}"
            self._log_and_print(f"❌ {error_message}", 'error')
            
            return RecipeProcessingResult(
                success=False,
                error_message=error_message,
                processing_time_seconds=time.time() - start_time
            )


def main():
    """Test the direct recipe processor"""
    import sys
    
    if len(sys.argv) < 2:
        print("❌ ERROR: No recipe URL provided")
        print("Usage: python3 direct_recipe_processor.py <RECIPE_URL> [IMAGE_DIR]")
        print("Example: python3 direct_recipe_processor.py 'https://www.allrecipes.com/recipe/123/' './images'")
        return
    
    recipe_url = sys.argv[1]
    image_dir = sys.argv[2] if len(sys.argv) > 2 else "./generated-images"
    
    print(f"🎯 Testing autonomous recipe processing...")
    print(f"📋 Recipe URL: {recipe_url}")
    print(f"🖼️  Image Directory: {image_dir}")
    
    # Initialize processor
    processor = DirectRecipeProcessor(log_to_file=True)
    
    # Process recipe
    result = processor.process_recipe_autonomous(recipe_url, image_dir)
    
    # Print results
    print(f"\n📊 FINAL RESULTS:")
    print(f"   Success: {result.success}")
    if result.success:
        print(f"   Recipe ID: {result.recipe_id}")
        print(f"   Recipe Name: {result.recipe_name}")
        print(f"   Ingredients: {result.ingredients_processed}")
        print(f"   Image Generated: {result.image_generated}")
    else:
        print(f"   Error: {result.error_message}")
    print(f"   Processing Time: {result.processing_time_seconds:.1f}s")

if __name__ == "__main__":
    main()