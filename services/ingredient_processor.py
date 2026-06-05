#!/usr/bin/env python3
"""
Direct API Ingredient Processor
Handles complete ingredient pipeline using direct HTTP API calls to eKitchen and Spoonacular
"""

import json
import urllib.request
import urllib.parse
import urllib.error
import re
import os
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from openai import OpenAI
import urllib.request
import urllib.parse
import urllib.error
import requests
import time
from services.unit_conversion_validator import UnitConversionValidator

def load_env_file(file_path: str) -> Dict[str, str]:
    """Load environment variables from a file"""
    env_vars = {}
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

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
    estimated_cost_per_unit: Optional[float] = None  # Value cost (e.g., $/gram)
    cost_unit: Optional[str] = None  # Unit for value cost (e.g., "gram")
    purchase_unit: Optional[str] = None  # What you buy (e.g., "bag", "dozen")
    purchase_quantity: Optional[float] = None  # Units per package (e.g., 2268 grams)
    purchase_cost: Optional[float] = None  # Actual price at checkout (e.g., $4.99)
    min_purchase_threshold: Optional[float] = None
    unit_conversions: Optional[Dict[str, float]] = None
    
    def __post_init__(self):
        if self.possible_units is None:
            self.possible_units = []
        if self.unit_conversions is None:
            self.unit_conversions = {}

@dataclass
class IngredientData:
    name: str
    id: Optional[str] = None
    calories: Optional[float] = None
    protein: Optional[float] = None
    fat: Optional[float] = None
    carbohydrates: Optional[float] = None
    sugar: Optional[float] = None
    category: str = "other"
    external_id: Optional[str] = None
    tag_names: List[str] = None
    consistency: str = "solid"
    possible_units: List[str] = None
    estimated_cost_value: Optional[float] = None
    estimated_cost_unit: Optional[str] = None
    purchase_info: Optional[str] = None  # JSON string
    unit_conversions: Optional[str] = None  # JSON string
    needs_enrichment: bool = True
    default_decay_rate: Optional[str] = None  # fast, medium, slow, pantry
    typical_shelf_life_days: Optional[int] = None

    def __post_init__(self):
        if self.tag_names is None:
            self.tag_names = []
        if self.possible_units is None:
            self.possible_units = ["cup", "tbsp", "tsp", "oz", "lb", "g", "kg"]


# Single-edible-item cost-unit descriptors that have a well-defined per-item gram weight,
# so grams can be AI-anchored (N6b). Deliberately EXCLUDES packaging/bulk units
# (bag/jar/can/package/box/bottle/container/...) whose weight varies wildly — anchoring
# those would massively misstate nutrition. Mirrors the backend's wholeItemKeys whitelist.
SINGLE_ITEM_UNITS = {
    "medium", "medium whole", "whole", "each", "piece", "large", "small",
    "fruit", "clove", "floret", "leaf", "slice", "sprig", "stalk", "rib",
    "ear", "fillet", "wedge", "link", "half", "head", "bulb", "stick",
}


class DirectIngredientProcessor:
    def __init__(self, log_to_file: bool = True):
        # Load environment configuration
        self.env_config = self._load_env_config()
        self.ekitchen_base_url = self.env_config.get('EKITCHEN_BASE_URL', 'https://ekitchen-production.up.railway.app')
        self.spoonacular_config = self._load_spoonacular_config()
        self.access_token = None
        self.refresh_token = None
        
        # Initialize OpenAI for AI-powered ingredient standardization (REQUIRED)
        try:
            openai_api_key = self.env_config.get('OPENAI_API_KEY', '')
            if openai_api_key:
                self.openai_client = OpenAI(api_key=openai_api_key)
                print("✅ OpenAI client initialized - required for ingredient standardization")
            else:
                print("❌ OpenAI API key not found - recipe processing will fail without it")
                self.openai_client = None
        except Exception as e:
            print(f"❌ OpenAI client initialization failed: {e} - recipe processing will fail")
            self.openai_client = None
        
        # Setup file logging if requested
        self.logger = self._setup_logging(log_to_file)
        self.log_to_file = log_to_file

        # Initialize unit conversion validator
        self.conversion_validator = UnitConversionValidator(self.logger)
        
    def _load_env_config(self) -> Dict[str, str]:
        """Load environment configuration from environment variables first, then local.env file"""
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
        
        # If we have critical keys from environment, we're good
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
    
    def _load_spoonacular_config(self) -> Dict[str, str]:
        """Load Spoonacular API configuration from environment variables"""
        return {
            "api_key": self.env_config.get('SPOONACULAR_API_KEY', ''),
            "base_url": self.env_config.get('SPOONACULAR_BASE_URL', 'https://spoonacular-recipe-food-nutrition-v1.p.rapidapi.com'),
            "rate_limit": {
                "requests_per_minute": int(self.env_config.get('SPOONACULAR_RATE_LIMIT_PER_MINUTE', 150)),
                "requests_per_day": int(self.env_config.get('SPOONACULAR_RATE_LIMIT_PER_DAY', 5000))
            },
            "request_timeout": int(self.env_config.get('SPOONACULAR_REQUEST_TIMEOUT', 30)),
            "max_retries": int(self.env_config.get('SPOONACULAR_MAX_RETRIES', 3)),
            "retry_delay": float(self.env_config.get('SPOONACULAR_RETRY_DELAY', 1.0))
        }
    
    def _setup_logging(self, log_to_file: bool) -> logging.Logger:
        """Setup file-based logging for debugging"""
        logger = logging.getLogger('ingredient_processor')
        logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        if log_to_file:
            # Create logs directory if it doesn't exist
            log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            # Create timestamped log file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = os.path.join(log_dir, f'ingredient_processor_{timestamp}.log')
            
            # File handler with detailed formatting
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            print(f"📝 Debug logging enabled: {log_file}")
        
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
    
    def authenticate_ekitchen(self, admin_email: str, admin_password: str) -> bool:
        """Authenticate with eKitchen API and get access token"""
        # Remember creds so we can fully re-authenticate if the token expires mid-run.
        self._admin_email = admin_email
        self._admin_password = admin_password
        self._log_and_print(f"🔐 Authenticating with eKitchen as {admin_email}...")
        self._log_and_print(f"DEBUG: Using base URL: {self.ekitchen_base_url}", 'debug')
        
        login_data = {
            "email": admin_email,
            "password": admin_password
        }
        
        # Retry transient failures (Railway prod can be slow/cold-starting; a single
        # timed-out login otherwise leaves the whole worker unauthenticated).
        data = json.dumps(login_data).encode('utf-8')
        last_err = None
        for attempt in range(4):
            try:
                req = urllib.request.Request(
                    f"{self.ekitchen_base_url}/auth/login",
                    data=data,
                    headers={'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(req, timeout=45) as response:
                    result = json.loads(response.read().decode('utf-8'))

                if result.get('access_token'):
                    self.access_token = result['access_token']
                    self.refresh_token = result.get('refresh_token')
                    self._log_and_print("✅ eKitchen authentication successful")
                    return True
                self._log_and_print(f"❌ Authentication failed: {result}", 'error')
                return False
            except urllib.error.HTTPError as e:
                # HTTP errors (e.g. 401 bad credentials) are not transient — don't retry.
                error_body = e.read().decode('utf-8') if hasattr(e, 'read') else 'No error body'
                self._log_and_print(f"❌ HTTP Error during authentication: {e.code} {e.reason}", 'error')
                self._log_and_print(f"DEBUG: Auth error body: {error_body}", 'debug')
                return False
            except Exception as e:
                last_err = e
                self._log_and_print(f"⚠️  Auth attempt {attempt + 1}/4 failed ({e}); retrying...", 'warning')
                if attempt < 3:
                    time.sleep(3 * (attempt + 1))  # 3s, 6s, 9s backoff
        self._log_and_print(f"❌ Error during authentication after retries: {last_err}", 'error')
        return False

    def refresh_authentication(self) -> bool:
        """Refresh authentication tokens using the refresh token"""
        if not self.refresh_token:
            self._log_and_print("⚠️  No refresh token available, cannot refresh authentication", 'warning')
            return False

        self._log_and_print("🔄 Refreshing authentication tokens...")
        self._log_and_print(f"DEBUG: Using base URL: {self.ekitchen_base_url}", 'debug')

        refresh_data = {
            "refresh_token": self.refresh_token
        }

        try:
            # Prepare the request
            data = json.dumps(refresh_data).encode('utf-8')
            req = urllib.request.Request(
                f"{self.ekitchen_base_url}/auth/refresh",
                data=data,
                headers={
                    'Content-Type': 'application/json'
                }
            )

            # Make the request
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))

            # Extract tokens from response (handle both direct and nested data structure)
            data = result.get('data', result)

            if data.get('access_token'):
                self.access_token = data['access_token']
                self.refresh_token = data.get('refresh_token')  # Update refresh token too
                self._log_and_print("✅ Token refresh successful")
                self._log_and_print(f"DEBUG: New access token length: {len(self.access_token)}", 'debug')
                if self.refresh_token:
                    self._log_and_print(f"DEBUG: New refresh token stored (length: {len(self.refresh_token)})", 'debug')
                return True
            else:
                self._log_and_print(f"❌ Token refresh failed: {result}", 'error')
                return False

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if hasattr(e, 'read') else 'No error body'
            self._log_and_print(f"❌ HTTP Error during token refresh: {e.code} {e.reason}", 'error')
            self._log_and_print(f"DEBUG: Refresh error body: {error_body}", 'debug')
            # If refresh fails, tokens might be expired - clear them
            if e.code == 401:
                self._log_and_print("⚠️  Refresh token expired, clearing tokens", 'warning')
                self.access_token = None
                self.refresh_token = None
            return False
        except Exception as e:
            self._log_and_print(f"❌ Error during token refresh: {e}", 'error')
            return False

    def _reauthenticate(self) -> bool:
        """Restore a valid eKitchen session: try a token refresh first, then a full
        re-login with stored admin creds. Used when a token expires mid-run."""
        if self.refresh_token and self.refresh_authentication():
            return True
        if getattr(self, '_admin_email', None) and getattr(self, '_admin_password', None):
            return self.authenticate_ekitchen(self._admin_email, self._admin_password)
        return False

    def search_ekitchen_ingredient(self, query: str) -> List[Dict[str, Any]]:
        """Search for ingredients in eKitchen.

        IMPORTANT: this NEVER returns [] for an auth/transport failure — only for a
        genuine empty result. An auth failure triggers re-auth + retry; if that fails
        it RAISES. This prevents the caller from mistaking a lost-auth error for
        'ingredient not found' and creating a duplicate ingredient via Spoonacular.
        """
        if not self.access_token and not self._reauthenticate():
            raise RuntimeError(
                "eKitchen not authenticated and re-auth failed; refusing to search "
                f"'{query}' (would risk creating a duplicate ingredient)"
            )

        encoded_query = urllib.parse.quote(query)
        url = f"{self.ekitchen_base_url}/global-ingredients/search?q={encoded_query}&limit=5"

        for attempt in range(2):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        'Authorization': f'Bearer {self.access_token}',
                        'Content-Type': 'application/json',
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode('utf-8'))

                ingredients = result if isinstance(result, list) else result.get('ingredients', [])
                self._log_and_print(f"🔍 Found {len(ingredients)} eKitchen ingredients for '{query}'")
                return ingredients

            except urllib.error.HTTPError as e:
                # Auth rejected mid-run (expired token) — re-authenticate and retry ONCE.
                # Do NOT fall through to a [] return (which would masquerade as not-found).
                if e.code in (401, 403) and attempt == 0:
                    self._log_and_print("🔄 eKitchen token rejected; re-authenticating before retry...", 'warning')
                    if not self._reauthenticate():
                        raise RuntimeError(
                            f"eKitchen auth lost and re-auth failed while searching '{query}'; "
                            "aborting recipe to avoid duplicate ingredients"
                        )
                    continue
                # Non-auth HTTP errors: raise, don't masquerade as 'not found'.
                error_body = e.read().decode('utf-8') if hasattr(e, 'read') else 'No error body'
                self._log_and_print(f"❌ HTTP Error searching '{query}': {e.code} {e.reason} — {error_body[:100]}", 'error')
                raise
        # Exhausted retries on auth — never reached for genuine empty results.
        raise RuntimeError(f"eKitchen ingredient search failed for '{query}' after re-auth")
    
    def search_spoonacular_ingredient_enhanced(self, ingredient_name: str) -> Optional[SpoonacularIngredientData]:
        """Enhanced Spoonacular search with full nutrition data and cost estimation"""
        api_key = self.spoonacular_config.get('api_key')
        if not api_key:
            self._log_and_print("⚠️  Spoonacular API key not found - skipping enrichment")
            return None
            
        try:
            # Clean ingredient name for search
            clean_name = ingredient_name.strip().lower()
            
            # Search for ingredients - use config-based URL and headers
            base_url = self.spoonacular_config.get('base_url', 'https://api.spoonacular.com')
            search_url = f"{base_url}/food/ingredients/search"
            
            params = {
                'query': clean_name,
                'number': 5,
                'metaInformation': True
            }
            
            # Determine if we're using RapidAPI or direct Spoonacular API
            if 'rapidapi.com' in base_url:
                # RapidAPI format
                headers = {
                    'X-RapidAPI-Key': api_key,
                    'X-RapidAPI-Host': base_url.replace('https://', '').replace('http://', '')
                }
            else:
                # Direct Spoonacular API format
                params['apiKey'] = api_key
                headers = {}
            
            response = requests.get(search_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if not results:
                    self._log_and_print(f"   🔍 No Spoonacular results for '{ingredient_name}'")
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
                nutrition_data = self.get_spoonacular_nutrition_enhanced(spoon_id, ingredient_name)
                return nutrition_data
                
            else:
                self._log_and_print(f"   ❌ Spoonacular search failed for '{ingredient_name}': {response.status_code}")
                return None
                
        except Exception as e:
            self._log_and_print(f"   ❌ Error searching Spoonacular for '{ingredient_name}': {e}")
            return None
    
    def search_spoonacular_ingredient(self, ingredient_name: str) -> Optional[Dict[str, Any]]:
        """Search ingredient in Spoonacular API - legacy method for backward compatibility"""
        api_key = self.spoonacular_config.get('api_key')
        if not api_key:
            print("❌ Spoonacular API key not found")
            return None
            
        try:
            # URL encode the ingredient name
            encoded_name = urllib.parse.quote(ingredient_name)
            url = f"https://api.spoonacular.com/food/ingredients/search?query={encoded_name}&number=1&apiKey={api_key}"
            
            req = urllib.request.Request(url, headers={'User-Agent': 'eKitchen-Ingestion/1.0'})
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            results = result.get('results', [])
            return results[0] if results else None
            
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print(f"❌ Spoonacular API access forbidden for {ingredient_name}")
            else:
                print(f"❌ HTTP Error enriching {ingredient_name}: {e.code} {e.reason}")
            return None
        except Exception as e:
            print(f"❌ Error enriching {ingredient_name}: {e}")
            return None
    
    def get_spoonacular_nutrition_enhanced(self, spoonacular_id: int, ingredient_name: str) -> Optional[SpoonacularIngredientData]:
        """Get detailed nutrition information and cost estimates from Spoonacular"""
        api_key = self.spoonacular_config.get('api_key')
        if not api_key:
            return None
            
        try:
            # Get ingredient information - use config-based URL and headers
            base_url = self.spoonacular_config.get('base_url', 'https://api.spoonacular.com')
            info_url = f"{base_url}/food/ingredients/{spoonacular_id}/information"
            
            params = {
                'amount': 100,  # Per 100g
                'unit': 'grams'
            }
            
            # Determine if we're using RapidAPI or direct Spoonacular API
            if 'rapidapi.com' in base_url:
                # RapidAPI format
                headers = {
                    'X-RapidAPI-Key': api_key,
                    'X-RapidAPI-Host': base_url.replace('https://', '').replace('http://', '')
                }
            else:
                # Direct Spoonacular API format
                params['apiKey'] = api_key
                headers = {}
            
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
                
                # Extract Spoonacular's estimatedCost (value in US Cents for the requested amount)
                spoonacular_cost_cents = None
                estimated_cost_data = data.get('estimatedCost', {})
                if estimated_cost_data and 'value' in estimated_cost_data:
                    spoonacular_cost_cents = estimated_cost_data.get('value')  # Cost in US cents
                    self._log_and_print(f"   💵 Spoonacular cost: {spoonacular_cost_cents} cents per 100g")
                
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
                
                # Use Spoonacular's estimatedCost for value cost (convert cents to dollars per gram)
                if spoonacular_cost_cents is not None:
                    # Spoonacular returns cost in cents for 100g, convert to dollars per gram
                    spoon_data.estimated_cost_per_unit = (spoonacular_cost_cents / 100.0) / 100.0  # cents->dollars, per 100g->per gram
                    spoon_data.cost_unit = "gram"
                    self._log_and_print(f"   💰 Value cost: ${spoon_data.estimated_cost_per_unit:.6f}/gram (from Spoonacular)")
                
                # Use AI for purchase information (Spoonacular doesn't provide package sizes/prices)
                cost_info = self.estimate_ingredient_cost_with_ai(
                    ingredient_name, 
                    possible_units,
                    spoonacular_cost_per_gram=spoon_data.estimated_cost_per_unit
                )
                if cost_info:
                    # Keep Spoonacular's value cost if available, otherwise use AI's cost_per_unit
                    if spoon_data.estimated_cost_per_unit is None:
                        spoon_data.estimated_cost_per_unit = cost_info['cost_per_unit']
                        spoon_data.cost_unit = cost_info['cost_unit']
                    
                    # Purchase information from AI
                    spoon_data.purchase_unit = cost_info['purchase_unit']
                    spoon_data.purchase_quantity = cost_info['purchase_quantity']
                    spoon_data.purchase_cost = cost_info['purchase_cost']  # NEW: actual package price
                    spoon_data.min_purchase_threshold = cost_info['min_purchase_threshold']
                    
                    # Add purchase unit to possible_units if not already present
                    if cost_info['purchase_unit'] and cost_info['purchase_unit'] not in possible_units:
                        possible_units = possible_units + [cost_info['purchase_unit']]
                        spoon_data.possible_units = possible_units
                        self._log_and_print(f"     ➕ Added purchase unit '{cost_info['purchase_unit']}' to possible_units")
                    
                    # Get optimized unit conversions (AI-only for purchase units)
                    spoon_data.unit_conversions = self.get_unit_conversions_optimized(
                        ingredient_name, possible_units, cost_info['cost_unit'],
                        cost_info['purchase_unit'], cost_info['purchase_quantity']
                    )
                
                self._log_and_print(f"   ✅ Enhanced Spoonacular data retrieved for '{ingredient_name}'")
                return spoon_data
            else:
                self._log_and_print(f"   ❌ Failed to get Spoonacular nutrition for '{ingredient_name}': {response.status_code}")
                return None
                
        except Exception as e:
            self._log_and_print(f"   ❌ Error getting Spoonacular nutrition for '{ingredient_name}': {e}")
            return None
    
    def get_spoonacular_nutrition(self, ingredient_id: int, amount: float = 100) -> Optional[Dict[str, Any]]:
        """Get nutrition information from Spoonacular - legacy method for backward compatibility"""
        api_key = self.spoonacular_config.get('api_key')
        if not api_key:
            return None
            
        try:
            url = f"https://api.spoonacular.com/food/ingredients/{ingredient_id}/information?amount={amount}&unit=grams&apiKey={api_key}"
            
            req = urllib.request.Request(url, headers={'User-Agent': 'eKitchen-Ingestion/1.0'})
            
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
                
        except Exception as e:
            print(f"❌ Error getting nutrition for ID {ingredient_id}: {e}")
            return None
    
    def create_ekitchen_ingredient(self, ingredient_data: IngredientData) -> Optional[str]:
        """Create ingredient in eKitchen database with comprehensive enrichment"""
        # Self-heal a lost/expired session instead of bailing — the auth token is a
        # short-lived Firebase JWT, and a single cleared token would otherwise poison
        # every ingredient for the rest of the processor's (singleton) lifetime.
        if not self.access_token and not self._reauthenticate():
            self._log_and_print("❌ Not authenticated with eKitchen and re-auth failed", 'error')
            return None
            
        self._log_and_print(f"\n🌱 Creating ingredient with enrichment: {ingredient_data.name}")
        
        # Step 1: Try to get enhanced Spoonacular data if not already enriched
        spoon_data = None
        if not ingredient_data.external_id:  # Not previously enriched
            self._log_and_print(f"   🔍 Searching Spoonacular for enhanced data...")
            spoon_data = self.search_spoonacular_ingredient_enhanced(ingredient_data.name)
            
            if spoon_data:
                # Update ingredient data with Spoonacular enrichment
                ingredient_data.external_id = str(spoon_data.id)
                ingredient_data.consistency = spoon_data.consistency or "solid"
                ingredient_data.possible_units = spoon_data.possible_units or ["cup", "tbsp", "tsp", "oz", "g"]
                
                # Add nutrition data if available
                if spoon_data.calories is not None:
                    ingredient_data.calories = spoon_data.calories
                if spoon_data.protein is not None:
                    ingredient_data.protein = spoon_data.protein
                if spoon_data.fat is not None:
                    ingredient_data.fat = spoon_data.fat
                if spoon_data.carbohydrates is not None:
                    ingredient_data.carbohydrates = spoon_data.carbohydrates
                if spoon_data.sugar is not None:
                    ingredient_data.sugar = spoon_data.sugar
                
                # Add cost information if available
                if spoon_data.estimated_cost_per_unit is not None:
                    ingredient_data.estimated_cost_value = spoon_data.estimated_cost_per_unit
                    ingredient_data.estimated_cost_unit = spoon_data.cost_unit
                    
                    # Store purchase info as JSON string (matches backend schema)
                    # Calculate purchase_cost if not explicitly set
                    purchase_cost = spoon_data.purchase_cost if hasattr(spoon_data, 'purchase_cost') and spoon_data.purchase_cost else None
                    if purchase_cost is None and spoon_data.estimated_cost_per_unit and spoon_data.purchase_quantity:
                        purchase_cost = spoon_data.estimated_cost_per_unit * spoon_data.purchase_quantity
                    
                    purchase_info = {
                        "purchase_unit": spoon_data.purchase_unit,
                        "purchase_quantity": spoon_data.purchase_quantity,
                        "purchase_cost": purchase_cost,  # Actual price at checkout
                        "min_purchase_threshold": spoon_data.min_purchase_threshold,
                        "supplier": "Spoonacular + AI Estimate"
                    }
                    ingredient_data.purchase_info = json.dumps(purchase_info)
                    
                    # Store unit conversions as JSON string (matches backend schema)
                    if spoon_data.unit_conversions:
                        ingredient_data.unit_conversions = json.dumps(spoon_data.unit_conversions)
                
                # Mark as enriched since we got Spoonacular data
                ingredient_data.needs_enrichment = False
                self._log_and_print(f"   ✅ Enhanced with Spoonacular data")
            else:
                self._log_and_print(f"   ❌ No Spoonacular data found")
        
        # Step 2: Use AI for categorization (more accurate than keyword matching)
        if ingredient_data.category == "other":
            ingredient_data.category = self.categorize_ingredient_with_ai(ingredient_data.name)

        # Step 2.5: Determine decay rate and shelf life based on category
        if not ingredient_data.default_decay_rate or not ingredient_data.typical_shelf_life_days:
            decay_rate, shelf_life = self.determine_decay_rate_and_shelf_life(
                ingredient_data.name,
                ingredient_data.category
            )
            ingredient_data.default_decay_rate = decay_rate
            ingredient_data.typical_shelf_life_days = shelf_life
            self._log_and_print(f"   🕐 Shelf life configured: {decay_rate} decay, {shelf_life} days")

        # Step 3: Update tags based on AI categorization
        ingredient_data.tag_names = self.generate_tags_for_ingredient(ingredient_data.name, ingredient_data.category)
        
        # Step 4: Set needs_enrichment flag
        if not spoon_data:
            ingredient_data.needs_enrichment = True
            ingredient_data.tag_names.append("Needs Review")  # Flag for manual review
        
        # Prepare ingredient data for API
        create_data = {
            "name": ingredient_data.name,
            "category": ingredient_data.category,
            "consistency": ingredient_data.consistency,
            "tag_names": ingredient_data.tag_names,
            "possible_units": ingredient_data.possible_units,
            "needs_enrichment": ingredient_data.needs_enrichment
        }

        # Add decay rate and shelf life if set
        if ingredient_data.default_decay_rate:
            create_data["default_decay_rate"] = ingredient_data.default_decay_rate
        if ingredient_data.typical_shelf_life_days:
            create_data["typical_shelf_life_days"] = ingredient_data.typical_shelf_life_days
        
        # Add nutrition data if available
        if ingredient_data.calories is not None:
            create_data["calories"] = ingredient_data.calories
        if ingredient_data.protein is not None:
            create_data["protein"] = ingredient_data.protein
        if ingredient_data.fat is not None:
            create_data["fat"] = ingredient_data.fat
        if ingredient_data.carbohydrates is not None:
            create_data["carbohydrates"] = ingredient_data.carbohydrates
        if ingredient_data.sugar is not None:
            create_data["sugar"] = ingredient_data.sugar
        if ingredient_data.external_id is not None:
            create_data["external_id"] = ingredient_data.external_id
        
        # Add cost information if available
        if ingredient_data.estimated_cost_value is not None:
            create_data["estimated_cost_value"] = ingredient_data.estimated_cost_value
        if ingredient_data.estimated_cost_unit is not None:
            create_data["estimated_cost_unit"] = ingredient_data.estimated_cost_unit
        if ingredient_data.purchase_info is not None:
            create_data["purchase_info"] = ingredient_data.purchase_info
        if ingredient_data.unit_conversions is not None:
            create_data["unit_conversions"] = ingredient_data.unit_conversions
        
        # DEBUG: Log what we're sending
        self._log_and_print(f"   📦 DEBUG: Sending to API - cost_value: {ingredient_data.estimated_cost_value}, cost_unit: {ingredient_data.estimated_cost_unit}")
        self._log_and_print(f"   📦 DEBUG: purchase_info: {ingredient_data.purchase_info}")
        self._log_and_print(f"   📦 DEBUG: unit_conversions: {ingredient_data.unit_conversions}")
        self._log_and_print(f"   📦 DEBUG: decay_rate: {ingredient_data.default_decay_rate}, shelf_life: {ingredient_data.typical_shelf_life_days}")
        
        # Log the EXACT JSON being sent
        self._log_and_print(f"   📤 FULL REQUEST BODY:")
        self._log_and_print(f"   {json.dumps(create_data, indent=2)}")
            
        data = json.dumps(create_data).encode('utf-8')
        for attempt in range(2):
            try:
                req = urllib.request.Request(
                    f"{self.ekitchen_base_url}/global-ingredients",
                    data=data,
                    headers={
                        'Authorization': f'Bearer {self.access_token}',
                        'Content-Type': 'application/json'
                    }
                )

                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode('utf-8'))

                ingredient_id = result.get('id')
                if ingredient_id:
                    status = "🌟 ENRICHED" if not ingredient_data.needs_enrichment else "🔄 BASIC"
                    self._log_and_print(f"   ✅ Created {ingredient_data.name}: ID {ingredient_id} ({status})")
                    return ingredient_id
                else:
                    self._log_and_print(f"   ❌ Failed to create {ingredient_data.name}: {result}", 'error')
                    return None

            except urllib.error.HTTPError as e:
                # Token expired/rejected mid-run — re-authenticate and retry ONCE.
                if e.code in (401, 403) and attempt == 0 and self._reauthenticate():
                    self._log_and_print(f"   🔄 eKitchen token rejected creating {ingredient_data.name}; re-authenticated, retrying...", 'warning')
                    continue
                self._log_and_print(f"   ❌ HTTP Error creating {ingredient_data.name}: {e.code} {e.reason}", 'error')
                return None
            except Exception as e:
                self._log_and_print(f"   ❌ Error creating {ingredient_data.name}: {e}", 'error')
                return None
    
    # ─── Similarity / Duplicate Detection ──────────────────────────────

    # Common suffixes that can be stripped to find a base ingredient name
    INGREDIENT_SUFFIXES = [
        "powder", "ground", "fresh", "dried", "whole", "crushed",
        "minced", "chopped", "sliced", "flakes", "extract", "paste",
        "seeds", "seed", "leaves", "leaf", "pieces", "chunks",
        "granulated", "shredded", "grated", "frozen", "canned",
        "organic", "raw", "cooked", "roasted", "smoked", "pickled",
    ]

    def _find_similar_ingredient(self, standardized_name: str) -> Optional[Dict]:
        """
        Search the backend for an existing ingredient that might be a duplicate
        of *standardized_name*.

        Returns a dict with keys  id, name, match_type  if a likely match is
        found, otherwise None.
        """
        if not self.access_token and not self._reauthenticate():
            self._log_and_print("⚠️  Cannot search for similar ingredients - not authenticated", 'warning')
            return None

        # 1. Exact search – the backend already does ILIKE '%query%'
        exact_results = self.search_ekitchen_ingredient(standardized_name)
        if exact_results:
            for ingredient in exact_results:
                existing_name = ingredient.get('name', '').lower().strip()
                query_name = standardized_name.lower().strip()
                # Exact match (case-insensitive)
                if existing_name == query_name:
                    self._log_and_print(
                        f"   🔎 Exact match found: '{ingredient.get('name')}' (ID: {ingredient.get('id')})"
                    )
                    return {
                        "id": ingredient.get('id'),
                        "name": ingredient.get('name'),
                        "match_type": "exact",
                    }

            # Check if any result is a close variant (one is substring of other)
            for ingredient in exact_results:
                existing_name = ingredient.get('name', '').lower().strip()
                query_name = standardized_name.lower().strip()
                if (existing_name in query_name or query_name in existing_name) and existing_name != query_name:
                    self._log_and_print(
                        f"   🔎 Substring match found: '{ingredient.get('name')}' for query '{standardized_name}'"
                    )
                    return {
                        "id": ingredient.get('id'),
                        "name": ingredient.get('name'),
                        "match_type": "substring",
                    }

        # 2. Strip common suffixes and search for the base name
        base_name = self._strip_ingredient_suffixes(standardized_name)
        if base_name and base_name.lower() != standardized_name.lower():
            self._log_and_print(
                f"   🔎 Trying base name search: '{base_name}' (stripped from '{standardized_name}')", 'debug'
            )
            base_results = self.search_ekitchen_ingredient(base_name)
            if base_results:
                for ingredient in base_results:
                    existing_name = ingredient.get('name', '').lower().strip()
                    base_lower = base_name.lower().strip()
                    if existing_name == base_lower or base_lower in existing_name or existing_name in base_lower:
                        self._log_and_print(
                            f"   🔎 Base-name match found: '{ingredient.get('name')}' for base '{base_name}'"
                        )
                        return {
                            "id": ingredient.get('id'),
                            "name": ingredient.get('name'),
                            "match_type": "base_name",
                        }

        # 3. Also try searching the full name against existing names that share
        #    the base (e.g., "paprika" searching might surface "paprika powder")
        #    — this is already covered by the ILIKE in the API, but we double-check
        #    the reverse: strip suffixes from *existing* names returned by exact search
        if exact_results:
            for ingredient in exact_results:
                existing_base = self._strip_ingredient_suffixes(ingredient.get('name', ''))
                if existing_base and existing_base.lower() == standardized_name.lower():
                    self._log_and_print(
                        f"   🔎 Reverse base-name match: '{ingredient.get('name')}' base='{existing_base}'"
                    )
                    return {
                        "id": ingredient.get('id'),
                        "name": ingredient.get('name'),
                        "match_type": "reverse_base",
                    }

        self._log_and_print(f"   🔎 No similar ingredient found for '{standardized_name}'", 'debug')
        return None

    def _strip_ingredient_suffixes(self, name: str) -> str:
        """Remove common suffixes/modifiers from an ingredient name to get the base form."""
        words = name.lower().strip().split()
        # Remove trailing suffix words
        stripped = [w for w in words if w not in self.INGREDIENT_SUFFIXES]
        result = " ".join(stripped).strip()
        # If we stripped everything, return original
        return result if result else name.strip()

    def _resolve_canonical_name(self, new_name: str, existing_name: str) -> Dict:
        """
        Use GPT-4o-mini to decide whether *new_name* and *existing_name* refer to
        the same ingredient, and if so, which name is canonical.

        Returns a dict with keys: same_ingredient (bool), canonical_name (str), reason (str).
        """
        if not self.openai_client:
            self._log_and_print("⚠️  OpenAI client not available – assuming different ingredients", 'warning')
            return {"same_ingredient": False, "canonical_name": new_name, "reason": "OpenAI unavailable"}

        prompt = f"""Two ingredient names were found that might be the same ingredient:
- Existing in database: "{existing_name}"
- New from recipe: "{new_name}"

Are these the same ingredient? If yes, which name is the canonical (most standard) name?

Respond in JSON only — no markdown fences:
{{"same_ingredient": true/false, "canonical_name": "the standard name", "reason": "brief explanation"}}

Examples:
- "paprika powder" vs "paprika" → same, canonical: "paprika"
- "all purpose flour" vs "flour" → same, canonical: "flour"
- "almond" vs "almond milk" → different
- "basil" vs "thai basil" → different
- "anchovy filet" vs "anchovy fillet" → same, canonical: "anchovy fillet"
- "green onion" vs "scallion" → same, canonical: "green onion"
- "cilantro" vs "coriander" → different (leaves vs seeds in US English)
"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)

            result = json.loads(raw)
            self._log_and_print(
                f"   🤖 Canonical resolution: same={result.get('same_ingredient')}, "
                f"canonical='{result.get('canonical_name')}' — {result.get('reason')}"
            )
            return result
        except Exception as e:
            self._log_and_print(f"   ⚠️  Canonical name resolution failed: {e}", 'warning')
            return {"same_ingredient": False, "canonical_name": new_name, "reason": f"Error: {e}"}

    def rename_ingredient(self, ingredient_id: str, new_name: str) -> bool:
        """
        Rename an existing global ingredient via the backend API.

        Calls PATCH /global-ingredients/{id}/rename-ingredient with {"new_name": new_name}.
        The backend cascades the rename to all recipe step references.
        """
        if not self.access_token and not self._reauthenticate():
            self._log_and_print("❌ Not authenticated with eKitchen – cannot rename ingredient", 'error')
            return False

        url = f"{self.ekitchen_base_url}/global-ingredients/{ingredient_id}/rename-ingredient"
        body = json.dumps({"new_name": new_name}).encode('utf-8')

        self._log_and_print(f"   ✏️  Renaming ingredient {ingredient_id} → '{new_name}'")

        for attempt in range(2):
            try:
                req = urllib.request.Request(
                    url,
                    data=body,
                    method='PATCH',
                    headers={
                        'Authorization': f'Bearer {self.access_token}',
                        'Content-Type': 'application/json',
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    self._log_and_print(f"   ✅ Rename successful: {result.get('message', 'OK')}")
                    return True

            except urllib.error.HTTPError as e:
                # Token expired/rejected mid-run — re-authenticate and retry ONCE.
                if e.code in (401, 403) and attempt == 0 and self._reauthenticate():
                    self._log_and_print(f"   🔄 eKitchen token rejected renaming ingredient {ingredient_id}; re-authenticated, retrying...", 'warning')
                    continue
                error_body = e.read().decode('utf-8') if hasattr(e, 'read') else 'No error body'
                self._log_and_print(
                    f"   ❌ HTTP Error renaming ingredient {ingredient_id}: {e.code} {e.reason} — {error_body}",
                    'error',
                )
                return False
            except Exception as e:
                self._log_and_print(f"   ❌ Error renaming ingredient {ingredient_id}: {e}", 'error')
                return False
        return False

    # ─── End Similarity / Duplicate Detection ────────────────────────────

    def standardize_ingredient_with_ai(self, ingredient_text: str) -> Dict[str, str]:
        """Use AI to standardize ingredient name and extract reference_as field"""
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
            print(f"🤖 AI raw response: '{result_text}'")
            
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
                
                print(f"✅ AI JSON parsed successfully")
                return {
                    "standardized_name": standardized_name,
                    "reference_as": reference_as or standardized_name
                }
            except json.JSONDecodeError:
                # Fallback: try to extract from text response with better cleaning
                print(f"⚠️  JSON parsing failed for: '{result_text}' - using fallback extraction")
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
                    reference_as = standardized_name
                    
                return {
                    "standardized_name": standardized_name,
                    "reference_as": reference_as
                }
            
        except Exception as e:
            print(f"❌ AI standardization failed for '{ingredient_text}': {e}")
            print(f"❌ Recipe processing will be aborted - OpenAI parsing is required for data quality")
            raise Exception(f"OpenAI ingredient standardization failed: {e}") from e
    

    def clean_ingredient_name(self, raw_ingredient: str) -> str:
        """Extract clean ingredient name - requires OpenAI for quality"""
        if not self.openai_client:
            print(f"❌ OpenAI client not initialized - cannot process ingredient: '{raw_ingredient}'")
            print(f"❌ Recipe processing will be aborted - OpenAI parsing is required for data quality")
            raise Exception("OpenAI client not available - ingredient standardization failed")
        
        # Use AI standardization (will raise exception if it fails)
        result = self.standardize_ingredient_with_ai(raw_ingredient)
        standardized_name = result["standardized_name"]
        self._log_and_print(f"🤖 AI Cleaned: '{raw_ingredient}' → '{standardized_name}'")
        return standardized_name
    
    def categorize_ingredient_with_ai(self, ingredient_name: str) -> str:
        """Use OpenAI to categorize an ingredient - more accurate than keyword matching"""
        if not self.openai_client:
            print(f"⚠️  OpenAI not available, falling back to basic categorization for '{ingredient_name}'")
            return self.categorize_ingredient_fallback(ingredient_name)
        
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
                self._log_and_print(f"   ⚠️ AI returned invalid category '{category}', using fallback")
                return self.categorize_ingredient_fallback(ingredient_name)
            
            self._log_and_print(f"   🤖 AI categorized '{ingredient_name}' as '{category}'")
            return category
            
        except Exception as e:
            self._log_and_print(f"   ❌ AI categorization failed for '{ingredient_name}': {e}")
            return self.categorize_ingredient_fallback(ingredient_name)
    
    def categorize_ingredient_fallback(self, ingredient_name: str) -> str:
        """Fallback ingredient categorization using keyword matching"""
        name_lower = ingredient_name.lower()
        
        if any(meat in name_lower for meat in ['chicken', 'beef', 'pork', 'turkey', 'fish', 'salmon', 'tuna']):
            return 'proteins'
        elif any(dairy in name_lower for dairy in ['milk', 'cheese', 'butter', 'cream', 'yogurt']):
            return 'dairy'
        elif any(veg in name_lower for veg in ['tomato', 'onion', 'pepper', 'carrot', 'celery', 'spinach', 'lettuce']):
            return 'vegetables'
        elif any(fruit in name_lower for fruit in ['apple', 'banana', 'orange', 'lemon', 'lime', 'berry']):
            return 'fruits'
        elif any(grain in name_lower for grain in ['rice', 'pasta', 'bread', 'flour', 'oat', 'quinoa']):
            return 'grains'
        elif any(spice in name_lower for spice in ['salt', 'pepper', 'cumin', 'paprika', 'garlic', 'ginger', 'oregano', 'basil', 'thyme', 'seasoning', 'powder']):
            return 'spices'
        elif any(condiment in name_lower for condiment in ['sauce', 'oil', 'vinegar', 'broth', 'stock', 'paste']):
            return 'condiments'
        elif any(beverage in name_lower for beverage in ['juice', 'wine', 'beer', 'coffee', 'tea']):
            return 'beverages'
        else:
            return 'other'

    def determine_decay_rate_and_shelf_life(self, ingredient_name: str, category: str) -> tuple[str, int]:
        """
        Determine decay rate and typical shelf life based on category and AI analysis.

        Mapping Rules:
            proteins     → fast, 5 days
            dairy        → medium, 10 days
            vegetables   → fast/slow (AI decides: leafy→fast, root→slow), 7 or 21 days
            fruits       → fast/slow (AI decides: berries→fast, citrus→slow), 7 or 21 days
            grains       → pantry, 365 days
            condiments   → pantry, 180 days
            spices       → pantry, 730 days
            beverages    → pantry/medium (AI decides: bottled→pantry, fresh→medium), 180 or 14 days
            other        → medium, 30 days (default fallback)

        Returns:
            Tuple of (decay_rate, shelf_life_days)
        """
        # Category-based decay rate mappings
        CATEGORY_DECAY_MAP = {
            'proteins': ('fast', 5),
            'dairy': ('medium', 10),
            'vegetables': ('needs_ai', None),
            'fruits': ('needs_ai', None),
            'grains': ('pantry', 365),
            'condiments': ('pantry', 180),
            'spices': ('pantry', 730),
            'beverages': ('needs_ai', None),
            'other': ('medium', 30)
        }

        if category not in CATEGORY_DECAY_MAP:
            self._log_and_print(f"   ⚠️ Unknown category '{category}', using default: medium/30 days")
            return ('medium', 30)

        decay_rate, shelf_life = CATEGORY_DECAY_MAP[category]

        # Check if AI decision is needed
        if decay_rate == 'needs_ai':
            return self._determine_decay_rate_with_ai(ingredient_name, category)
        else:
            self._log_and_print(f"   📊 Decay rate: {decay_rate}, Shelf life: {shelf_life} days")
            return (decay_rate, shelf_life)

    def _determine_decay_rate_with_ai(self, ingredient_name: str, category: str) -> tuple[str, int]:
        """Use AI to determine decay rate for ambiguous categories"""
        if not self.openai_client:
            self._log_and_print(f"   ⚠️ OpenAI not available, using default: medium/14 days")
            return ('medium', 14)

        try:
            if category == 'vegetables':
                prompt = f"""Categorize this vegetable for shelf life: "{ingredient_name}"

Is this a LEAFY/SOFT vegetable (decays fast) or ROOT/HARD vegetable (decays slower)?

Examples:
- LEAFY/SOFT: lettuce, spinach, kale, herbs, tomatoes, cucumbers, peppers (fast decay, 7 days)
- ROOT/HARD: potatoes, carrots, onions, garlic, beets, turnips, squash (slow decay, 21 days)

Return ONLY "fast" or "slow", nothing else."""

            elif category == 'fruits':
                prompt = f"""Categorize this fruit for shelf life: "{ingredient_name}"

Is this a SOFT/BERRY fruit (decays fast) or CITRUS/HARD fruit (decays slower)?

Examples:
- SOFT/BERRY: berries, grapes, bananas, peaches, plums, mangoes (fast decay, 7 days)
- CITRUS/HARD: oranges, lemons, limes, apples, pears, melons (slow decay, 21 days)

Return ONLY "fast" or "slow", nothing else."""

            elif category == 'beverages':
                prompt = f"""Categorize this beverage for shelf life: "{ingredient_name}"

Is this a SHELF-STABLE beverage (pantry storage) or FRESH beverage (refrigerated)?

Examples:
- SHELF-STABLE: bottled water, soda, wine, beer, shelf-stable milk, juice boxes (pantry, 180 days)
- FRESH: fresh milk, fresh juice, smoothies, fresh brewed coffee/tea (medium, 14 days)

Return ONLY "pantry" or "medium", nothing else."""

            else:
                # Shouldn't get here, but fallback
                return ('medium', 30)

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.1
            )

            decay_rate = response.choices[0].message.content.strip().lower()

            # Map AI decision to shelf life
            if category == 'vegetables' or category == 'fruits':
                if decay_rate == 'fast':
                    shelf_life = 7
                elif decay_rate == 'slow':
                    shelf_life = 21
                else:
                    self._log_and_print(f"   ⚠️ AI returned unexpected value '{decay_rate}', using medium/14")
                    decay_rate = 'medium'
                    shelf_life = 14

            elif category == 'beverages':
                if decay_rate == 'pantry':
                    shelf_life = 180
                elif decay_rate == 'medium':
                    shelf_life = 14
                else:
                    self._log_and_print(f"   ⚠️ AI returned unexpected value '{decay_rate}', using pantry/180")
                    decay_rate = 'pantry'
                    shelf_life = 180

            self._log_and_print(f"   🤖 AI decay analysis: {decay_rate}, {shelf_life} days")
            return (decay_rate, shelf_life)

        except Exception as e:
            self._log_and_print(f"   ❌ AI decay determination failed: {e}, using medium/14 days")
            return ('medium', 14)

    def estimate_ingredient_cost_with_ai(self, ingredient_name: str, possible_units: List[str], spoonacular_cost_per_gram: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Use OpenAI to estimate purchase information for an ingredient.
        
        We use Spoonacular for VALUE cost (cost per gram) when available.
        AI is used for PURCHASE information (what you actually buy at the store).
        """
        if not self.openai_client:
            self._log_and_print(f"   ⚠️ OpenAI not available for cost estimation of '{ingredient_name}'")
            return None
            
        try:
            units_list = ", ".join(possible_units[:5]) if possible_units else "cup, tablespoon, teaspoon, ounce"
            
            # Include Spoonacular cost if available for context
            spoon_context = ""
            if spoonacular_cost_per_gram is not None:
                spoon_context = f"\nNote: Spoonacular indicates this costs approximately ${spoonacular_cost_per_gram:.4f}/gram (${spoonacular_cost_per_gram * 100:.2f} per 100g)."
            
            prompt = f"""Estimate PURCHASE information for this ingredient: "{ingredient_name}"
Available units: {units_list}{spoon_context}

Provide realistic US grocery store estimates in this EXACT JSON format:
{{
  "cost_per_unit": [number - cost per smallest practical unit],
  "cost_unit": "[smallest practical unit for costing - gram, tablespoon, etc]",
  "purchase_unit": "[what you actually buy at store - bottle, jar, bag, dozen, etc]",
  "purchase_quantity": [how many cost_units in one purchase_unit],
  "purchase_cost": [actual price you pay for one purchase_unit at store],
  "min_purchase_threshold": [if recipe needs this many cost_units or more, buy full purchase_unit]
}}

Examples:
- Honey: cost_per_unit: 0.12, cost_unit: "tablespoon", purchase_unit: "bottle", purchase_quantity: 32, purchase_cost: 3.84, min_purchase_threshold: 8
- All-purpose flour: cost_per_unit: 0.0022, cost_unit: "gram", purchase_unit: "bag", purchase_quantity: 2268, purchase_cost: 4.99, min_purchase_threshold: 500
- Eggs: cost_per_unit: 0.33, cost_unit: "piece", purchase_unit: "dozen", purchase_quantity: 12, purchase_cost: 3.99, min_purchase_threshold: 6
- Salt: cost_per_unit: 0.02, cost_unit: "teaspoon", purchase_unit: "container", purchase_quantity: 192, purchase_cost: 1.99, min_purchase_threshold: 48

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
                
                # Validate required fields (purchase_cost is now required)
                required_fields = ['cost_per_unit', 'cost_unit', 'purchase_unit', 'purchase_quantity', 'purchase_cost', 'min_purchase_threshold']
                if all(field in cost_info for field in required_fields):
                    self._log_and_print(f"   🛒 AI purchase info: {cost_info['purchase_unit']} = ${cost_info['purchase_cost']:.2f} ({cost_info['purchase_quantity']} {cost_info['cost_unit']}s)")
                    return cost_info
                else:
                    missing = [f for f in required_fields if f not in cost_info]
                    self._log_and_print(f"   ⚠️ AI cost estimation missing fields for '{ingredient_name}': {missing}")
                    # Try to calculate purchase_cost if only that's missing
                    if 'purchase_cost' not in cost_info and 'cost_per_unit' in cost_info and 'purchase_quantity' in cost_info:
                        cost_info['purchase_cost'] = cost_info['cost_per_unit'] * cost_info['purchase_quantity']
                        self._log_and_print(f"   📊 Calculated purchase_cost: ${cost_info['purchase_cost']:.2f}")
                        if all(f in cost_info for f in required_fields):
                            return cost_info
                    return None
                    
            except json.JSONDecodeError:
                self._log_and_print(f"   ⚠️ AI cost estimation returned invalid JSON for '{ingredient_name}': {response_text}")
                return None
            
        except Exception as e:
            self._log_and_print(f"   ❌ AI cost estimation failed for '{ingredient_name}': {e}")
            return None

    def estimate_nutrition_with_ai(self, ingredient_name: str) -> Optional[Dict[str, float]]:
        """Use OpenAI to estimate per-100g nutrition when Spoonacular has no data.

        Returns {calories, protein, fat, carbohydrates, sugar} per 100g, or None. Values
        are approximate (caller should flag them as AI-sourced). Calories are sanity-capped
        — nothing edible exceeds ~900 kcal/100g (pure fat).
        """
        if not self.openai_client:
            self._log_and_print(f"   ⚠️ OpenAI not available for nutrition estimation of '{ingredient_name}'")
            return None

        try:
            prompt = f"""Estimate the nutrition per 100 grams of this food ingredient: "{ingredient_name}"

Provide typical USDA-style values in this EXACT JSON format (numbers only, per 100g):
{{
  "calories": [kcal per 100g],
  "protein": [grams per 100g],
  "fat": [grams per 100g],
  "carbohydrates": [grams per 100g],
  "sugar": [grams per 100g]
}}

Rules:
- Use well-known reference values for the food.
- For a blend/compound name (e.g. "salt and pepper"), estimate the dominant edible component.
- If it is not a real edible food, return all zeros.

Examples:
- egg white: {{"calories": 52, "protein": 11, "fat": 0.2, "carbohydrates": 0.7, "sugar": 0.7}}
- olive oil: {{"calories": 884, "protein": 0, "fat": 100, "carbohydrates": 0, "sugar": 0}}
- cayenne powder: {{"calories": 318, "protein": 12, "fat": 17, "carbohydrates": 57, "sugar": 10}}

Return ONLY the JSON, no other text."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
                temperature=0.1,
            )
            response_text = response.choices[0].message.content.strip()
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()

            try:
                data = json.loads(response_text)
            except json.JSONDecodeError:
                self._log_and_print(f"   ⚠️ AI nutrition returned invalid JSON for '{ingredient_name}': {response_text}")
                return None

            required = ['calories', 'protein', 'fat', 'carbohydrates', 'sugar']
            if not all(f in data for f in required):
                self._log_and_print(f"   ⚠️ AI nutrition missing fields for '{ingredient_name}'")
                return None
            try:
                nutrition = {k: float(data[k]) for k in required}
            except (TypeError, ValueError):
                self._log_and_print(f"   ⚠️ AI nutrition non-numeric for '{ingredient_name}'")
                return None
            if not (0 <= nutrition['calories'] <= 1000):
                self._log_and_print(f"   ⚠️ AI nutrition implausible calories ({nutrition['calories']}) for '{ingredient_name}'")
                return None

            self._log_and_print(f"   🥗 AI nutrition: {nutrition['calories']:.0f} cal/100g for '{ingredient_name}'")
            return nutrition
        except Exception as e:
            self._log_and_print(f"   ❌ AI nutrition estimation failed for '{ingredient_name}': {e}")
            return None

    def estimate_item_weight_grams(self, ingredient_name: str, item_unit: str) -> Optional[float]:
        """Use OpenAI to estimate the weight in grams of ONE whole edible item.

        Used to anchor grams for count-cost-unit produce (e.g. cost_unit "small" onion,
        "fruit" lemon, "medium whole" tomato) that Spoonacular can't gram-convert. Only
        meaningful for single-item descriptors — callers must NOT pass packaging units
        (bag/jar/can/...), whose weight is ill-defined. Returns grams (1..5000) or None.
        """
        if not self.openai_client:
            self._log_and_print(f"   ⚠️ OpenAI not available for item-weight estimation of '{ingredient_name}'")
            return None

        try:
            prompt = f"""Estimate the typical edible weight in grams of ONE "{item_unit}" of "{ingredient_name}".

This is the weight of a single whole item as commonly used in a recipe (e.g. one medium
onion, one fruit lemon, one clove of garlic).

Provide your answer in this EXACT JSON format (number only, grams):
{{"grams": [grams for one {item_unit}]}}

Rules:
- Use well-known reference weights for the food at the given size descriptor.
- Account for the size word ("small" < "medium" < "large").
- If "{ingredient_name}" is not a single countable edible item (e.g. a liquid, powder,
  or bulk package), return {{"grams": 0}}.

Examples:
- one small onion: {{"grams": 70}}
- one medium whole tomato: {{"grams": 123}}
- one fruit lemon: {{"grams": 58}}
- one clove garlic: {{"grams": 3}}
- one rib green onion: {{"grams": 15}}

Return ONLY the JSON, no other text."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=40,
                temperature=0.1,
            )
            response_text = response.choices[0].message.content.strip()
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()

            try:
                data = json.loads(response_text)
            except json.JSONDecodeError:
                self._log_and_print(f"   ⚠️ AI item-weight invalid JSON for '{ingredient_name}': {response_text}")
                return None

            if 'grams' not in data:
                self._log_and_print(f"   ⚠️ AI item-weight missing 'grams' for '{ingredient_name}'")
                return None
            try:
                grams = float(data['grams'])
            except (TypeError, ValueError):
                self._log_and_print(f"   ⚠️ AI item-weight non-numeric for '{ingredient_name}'")
                return None
            if not (0 < grams <= 5000):
                # 0 = AI says not a countable item; >5000 = implausible single item.
                self._log_and_print(f"   ⚠️ AI item-weight not usable ({grams}g) for '{item_unit} {ingredient_name}'")
                return None

            self._log_and_print(f"   ⚖️ AI item-weight: 1 {item_unit} {ingredient_name} = {grams:.0f}g")
            return grams
        except Exception as e:
            self._log_and_print(f"   ❌ AI item-weight estimation failed for '{ingredient_name}': {e}")
            return None

    def get_unit_conversions(self, ingredient_name: str, possible_units: List[str], cost_unit: str) -> Dict[str, float]:
        """Get conversion factors from all possible units to the cost unit"""
        api_key = self.spoonacular_config.get('api_key')
        if not api_key or not possible_units:
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

        # Always anchor grams (even if not a possible_unit). Recipe nutrition converts any
        # recipe unit -> grams via the gram entry, so every ingredient needs one. Adding the
        # gram key also makes all other units gram-convertible (cost-unit-relative ratios).
        if 'gram' not in units_to_convert and cost_unit not in ('gram', 'grams', 'g'):
            units_to_convert.append('gram')

        self._log_and_print(f"   🔄 Getting conversion factors for {len(units_to_convert)} units...")
        
        for unit in units_to_convert:
            try:
                # Convert 1 unit to cost_unit - use config-based URL and headers
                base_url = self.spoonacular_config.get('base_url', 'https://api.spoonacular.com')
                convert_url = f"{base_url}/recipes/convert"
                
                params = {
                    'ingredientName': ingredient_name,
                    'sourceAmount': 1,
                    'sourceUnit': unit,
                    'targetUnit': cost_unit
                }
                
                # Determine if we're using RapidAPI or direct Spoonacular API
                if 'rapidapi.com' in base_url:
                    # RapidAPI format
                    headers = {
                        'X-RapidAPI-Key': api_key,
                        'X-RapidAPI-Host': base_url.replace('https://', '').replace('http://', '')
                    }
                else:
                    # Direct Spoonacular API format
                    params['apiKey'] = api_key
                    headers = {}
                
                response = requests.get(convert_url, params=params, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('type') == 'CONVERSION':
                        conversion_factor = data.get('targetAmount', 1.0)
                        # Only include positive conversion factors
                        if conversion_factor > 0:
                            conversions[unit] = conversion_factor
                            self._log_and_print(f"     ✅ 1 {unit} = {conversion_factor:.3f} {cost_unit}")
                        else:
                            self._log_and_print(f"     ⚠️ Invalid conversion factor (≤ 0): {unit} → {cost_unit}")
                    else:
                        self._log_and_print(f"     ⚠️ No conversion available: {unit} → {cost_unit}")
                else:
                    self._log_and_print(f"     ❌ Conversion failed: {unit} → {cost_unit} ({response.status_code})")
                
                # Small delay to be respectful to API
                time.sleep(0.2)
                
            except Exception as e:
                self._log_and_print(f"     ❌ Error converting {unit} → {cost_unit}: {e}")
        
        # Always include the identity conversion (cost_unit to itself)
        conversions[cost_unit] = 1.0

        # N6b: if Spoonacular couldn't anchor grams and the cost unit is a single edible
        # item (small/medium/fruit/clove/...), AI-estimate the per-item gram weight so the
        # ingredient still gets a gram anchor. 1 gram = (1 / grams_per_item) cost_units.
        if not any(k.lower() in ('g', 'gram', 'grams') for k in conversions) \
                and cost_unit and cost_unit.lower() in SINGLE_ITEM_UNITS:
            grams_per_item = self.estimate_item_weight_grams(ingredient_name, cost_unit)
            if grams_per_item and grams_per_item > 0:
                conversions['gram'] = 1.0 / grams_per_item

        self._log_and_print(f"   📄 Got {len(conversions)} conversion factors")
        return conversions

    def estimate_purchase_unit_conversion(self, ingredient_name: str, purchase_unit: str, cost_unit: str, purchase_quantity: float) -> float:
        """Use AI to estimate how purchase unit converts to cost unit"""
        if not self.openai_client:
            self._log_and_print(f"     ⚠️ OpenAI not available, using purchase_quantity fallback: {purchase_quantity}")
            return purchase_quantity  # Fallback to purchase_quantity
        
        try:
            prompt = f"""Given this ingredient: "{ingredient_name}"

We know that:
- 1 {purchase_unit} contains approximately {purchase_quantity} {cost_unit}
- We need the conversion factor: 1 {purchase_unit} = ? {cost_unit}

Based on typical grocery packaging for "{ingredient_name}", how many {cost_unit} are in 1 {purchase_unit}?

Consider standard package sizes and realistic measurements. For example:
- 1 bottle honey = 32 tablespoons
- 1 can diced tomatoes = 14 ounces  
- 1 jar peanut butter = 64 tablespoons
- 1 bag flour = 80 cups

Return ONLY a number (the conversion factor)."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20,
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content.strip()
            result = float(result_text)
            
            # Sanity check - result should be positive and reasonable
            if result <= 0 or result > 10000:
                self._log_and_print(f"     ⚠️ AI returned unreasonable conversion ({result}), using fallback: {purchase_quantity}")
                return purchase_quantity
            
            self._log_and_print(f"     🤖 AI estimated: 1 {purchase_unit} = {result} {cost_unit}")
            return result
            
        except Exception as e:
            self._log_and_print(f"     ⚠️ AI estimation failed ({e}), using purchase_quantity fallback: {purchase_quantity}")
            return purchase_quantity
    
    def get_unit_conversions_enhanced(self, ingredient_name: str, possible_units: List[str], cost_unit: str, purchase_unit: str = None, purchase_quantity: float = None) -> Dict[str, float]:
        """Enhanced unit conversions that includes purchase unit bridges"""
        self._log_and_print(f"   🔄 Getting enhanced unit conversions (including purchase unit: {purchase_unit})...")
        
        # Get existing Spoonacular conversions
        conversions = self.get_unit_conversions(ingredient_name, possible_units, cost_unit)
        
        # Add purchase unit conversion using AI estimation
        if purchase_unit and purchase_quantity and purchase_unit != cost_unit:
            # Only add if purchase unit isn't already in conversions
            if purchase_unit not in conversions:
                purchase_conversion = self.estimate_purchase_unit_conversion(
                    ingredient_name, purchase_unit, cost_unit, purchase_quantity
                )
                if purchase_conversion and purchase_conversion > 0:
                    conversions[purchase_unit] = purchase_conversion
                    self._log_and_print(f"     ✅ Added purchase unit conversion: {purchase_unit} = {purchase_conversion} {cost_unit}")
                else:
                    self._log_and_print(f"     ❌ Failed to get valid purchase unit conversion for {purchase_unit}")
            else:
                self._log_and_print(f"     ✅ Purchase unit {purchase_unit} already in conversions: {conversions[purchase_unit]}")
        
        self._log_and_print(f"   📄 Enhanced conversions complete: {len(conversions)} total factors")
        return conversions
    
    def get_unit_conversions_optimized(self, ingredient_name: str, possible_units: List[str], cost_unit: str, purchase_unit: str = None, purchase_quantity: float = None) -> Dict[str, float]:
        """Optimized unit conversions - AI-only for purchase units, skip Spoonacular for efficiency"""
        self._log_and_print(f"   🚀 Getting optimized unit conversions (AI-only for purchase unit: {purchase_unit})...")

        # Start with minimal conversions - just the cost unit identity
        conversions = {cost_unit: 1.0}

        # Add purchase unit conversion using AI estimation (no Spoonacular needed)
        if purchase_unit and purchase_quantity and purchase_unit != cost_unit:
            purchase_conversion = self.estimate_purchase_unit_conversion(
                ingredient_name, purchase_unit, cost_unit, purchase_quantity
            )
            if purchase_conversion and purchase_conversion > 0:
                # Validate the conversion to prevent inversion
                is_valid, error_msg, suggested_value = self.conversion_validator.validate_conversion(
                    purchase_unit, purchase_conversion, cost_unit, ingredient_name
                )

                if not is_valid:
                    self._log_and_print(f"     ⚠️ {error_msg}", 'warning')
                    self._log_and_print(f"     🔧 Using corrected value: {suggested_value:.2f}")
                    conversions[purchase_unit] = suggested_value
                else:
                    conversions[purchase_unit] = purchase_conversion
                    self._log_and_print(f"     ✅ AI generated purchase unit conversion: {purchase_unit} = {purchase_conversion} {cost_unit}")
            else:
                self._log_and_print(f"     ⚠️ Failed to generate purchase unit conversion, using purchase_quantity fallback")
                conversions[purchase_unit] = purchase_quantity

        # Always anchor grams so recipe nutrition can convert any unit -> grams. AI-only to
        # stay consistent with this path's no-Spoonacular design. With the gram entry present,
        # every other cost-unit-relative conversion becomes gram-convertible too.
        if cost_unit not in ('gram', 'grams', 'g'):
            gram_conversion = self.estimate_purchase_unit_conversion(
                ingredient_name, 'gram', cost_unit, 1.0
            )
            if gram_conversion and gram_conversion > 0:
                conversions['gram'] = gram_conversion
                self._log_and_print(f"     ✅ Gram anchor: 1 gram = {gram_conversion} {cost_unit}")
            elif cost_unit and cost_unit.lower() in SINGLE_ITEM_UNITS:
                # N6b: single edible item (small/medium/fruit/...) — anchor via per-item weight.
                grams_per_item = self.estimate_item_weight_grams(ingredient_name, cost_unit)
                if grams_per_item and grams_per_item > 0:
                    conversions['gram'] = 1.0 / grams_per_item
                    self._log_and_print(f"     ✅ Gram anchor (item-weight): 1 {cost_unit} = {grams_per_item:.0f}g")
                else:
                    self._log_and_print(f"     ⚠️ Could not anchor grams for {ingredient_name}", 'warning')
            else:
                self._log_and_print(f"     ⚠️ Could not anchor grams for {ingredient_name}", 'warning')

        # Validate all conversions before returning
        validated_conversions = self.conversion_validator.validate_all_conversions(
            conversions, cost_unit, ingredient_name
        )

        # For new ingredient processing, we prioritize having the purchase unit conversion
        # Spoonacular conversions can be added later if needed via the enhanced method
        self._log_and_print(f"   📄 Optimized conversions complete: {len(validated_conversions)} total factors (purchase-focused)")
        return validated_conversions
    
    def generate_tags_for_ingredient(self, ingredient_name: str, category: str) -> List[str]:
        """Generate appropriate tags for an ingredient"""
        tags = []
        name_lower = ingredient_name.lower()
        
        # Add category-based tags
        if category == 'proteins':
            tags.extend(['Protein', 'Main Ingredient'])
            if 'chicken' in name_lower:
                tags.extend(['Poultry', 'Lean Protein'])
            elif any(meat in name_lower for meat in ['beef', 'pork']):
                tags.extend(['Red Meat'])
            elif any(fish in name_lower for fish in ['fish', 'salmon', 'tuna']):
                tags.extend(['Seafood', 'Omega-3'])
        elif category == 'spices':
            tags.extend(['Seasoning', 'Flavor Enhancer'])
            if 'taco' in name_lower or 'mexican' in name_lower:
                tags.extend(['Mexican', 'Tex-Mex'])
        elif category == 'condiments':
            tags.extend(['Liquid', 'Flavor Base'])
            if 'broth' in name_lower:
                tags.extend(['Stock', 'Cooking Liquid'])
        
        # Add cuisine-specific tags
        if any(mexican in name_lower for mexican in ['taco', 'salsa', 'cumin', 'chile', 'cilantro']):
            tags.append('Mexican')
        
        # Add dietary tags
        if not any(animal in name_lower for animal in ['chicken', 'beef', 'pork', 'fish', 'milk', 'cheese', 'butter', 'egg']):
            tags.append('Vegan')
        
        if not any(gluten in name_lower for gluten in ['flour', 'bread', 'pasta', 'wheat']):
            tags.append('Gluten-Free')
        
        # Add "Needs Review" for failed enrichment
        if category == 'other':
            tags.append('Needs Review')
            
        return list(set(tags))  # Remove duplicates
    
    def process_recipe_ingredients(self, raw_ingredients: List[str], allow_ingredient_skipping: bool = False) -> tuple:
        """Process all ingredients for a recipe and return both data and ID mapping
        
        Args:
            raw_ingredients: List of raw ingredient strings from recipe
            allow_ingredient_skipping: If True, allows user to skip ingredients interactively
        
        Returns:
            Tuple containing:
            - Dict[str, IngredientData]: Full ingredient data mapping
            - Dict[str, str]: Simple ingredient name to ID mapping for pipeline use
            - bool: True if any ingredients were explicitly skipped by user
        """
        self._log_and_print(f"🚀 Starting direct API ingredient processing for {len(raw_ingredients)} ingredients...")
        self._log_and_print(f"DEBUG: Raw ingredients list: {raw_ingredients}", 'debug')
        self._log_and_print(f"DEBUG: Authentication status - has token: {self.access_token is not None}", 'debug')
        self._log_and_print(f"DEBUG: Interactive skipping enabled: {allow_ingredient_skipping}", 'debug')
        
        # Track if user explicitly skips ingredients
        ingredients_skipped_by_user = False
        
        # Step 1: Clean ingredient names and store reference mappings  
        cleaned_ingredients = []
        ingredient_reference_map = {}  # Maps cleaned name to reference_as
        
        self._log_and_print(f"🧹 Processing {len(raw_ingredients)} raw ingredients:")
        for raw in raw_ingredients:
            if not self.openai_client:
                print(f"❌ OpenAI client not initialized - cannot process ingredients for recipe")
                print(f"❌ Recipe processing will be aborted - OpenAI parsing is required for data quality")
                raise Exception("OpenAI client not available - recipe ingredient processing failed")
            
            # Interactive ingredient skipping
            skip_this_ingredient = False
            if allow_ingredient_skipping:
                while True:
                    print(f"\n📋 Ingredient: '{raw}'")
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
                            print(f"⏭️  Skipping ingredient: '{raw}'")
                            self._log_and_print(f"   '{raw}' → SKIPPED BY USER")
                            skip_this_ingredient = True
                            ingredients_skipped_by_user = True
                            break
                        elif choice == "3":
                            print(f"⏹️  User chose to skip remaining ingredients and abort recipe")
                            self._log_and_print("⏹️  Recipe processing aborted by user (skip remaining ingredients)")
                            ingredients_skipped_by_user = True
                            return {}, {}, ingredients_skipped_by_user
                        else:
                            print("❌ Invalid choice. Please enter 1, 2, or 3.")
                            continue
                    except (EOFError, KeyboardInterrupt):
                        print(f"\n⏹️  Recipe processing aborted by user")
                        ingredients_skipped_by_user = True
                        return {}, {}, ingredients_skipped_by_user
            
            # Skip processing if user chose to skip this ingredient
            if skip_this_ingredient:
                continue
            
            # Use AI for both standardized name and reference_as (will raise exception if it fails)
            ai_result = self.standardize_ingredient_with_ai(raw)
            cleaned = ai_result["standardized_name"]
            reference_as = ai_result["reference_as"]
            
            if cleaned and len(cleaned) > 2:  # Skip very short names
                cleaned_ingredients.append(cleaned)
                ingredient_reference_map[cleaned] = reference_as
                self._log_and_print(f"   '{raw}' → '{cleaned}' (ref: '{reference_as}')")
                self._log_and_print(f"   DEBUG: Processing '{raw}' → standardized: '{cleaned}', reference: '{reference_as}'", 'debug')
            else:
                self._log_and_print(f"   '{raw}' → SKIPPED (too short: '{cleaned}')")
                self._log_and_print(f"   DEBUG: Skipped '{raw}' - cleaned to '{cleaned}' (too short)", 'debug')
        
        unique_ingredients = list(set(cleaned_ingredients))
        self._log_and_print(f"📋 Cleaned to {len(unique_ingredients)} unique ingredients: {unique_ingredients}")
        self._log_and_print(f"DEBUG: Unique ingredients for processing: {unique_ingredients}", 'debug')
        
        result_mapping = {}
        ingredient_id_map = {}  # Clear mapping for pipeline use
        
        # Step 2: Search existing ingredients in eKitchen
        self._log_and_print(f"🔍 Searching {len(unique_ingredients)} ingredients in eKitchen database...")
        existing_count = 0
        need_creation = []
        
        for ingredient_name in unique_ingredients:
            self._log_and_print(f"  🔍 Searching: '{ingredient_name}'")
            self._log_and_print(f"    DEBUG: About to search for '{ingredient_name}'", 'debug')
            existing = self.search_ekitchen_ingredient(ingredient_name)
            self._log_and_print(f"    DEBUG: Search returned {len(existing) if existing else 0} results", 'debug')
            
            if existing:
                ingredient_id = existing[0]['id']
                self._log_and_print(f"    ✅ Found existing: {existing[0]['name']} (ID: {ingredient_id})")
                self._log_and_print(f"    DEBUG: Using existing ingredient data: {existing[0]}", 'debug')
                result_mapping[ingredient_name] = IngredientData(
                    name=existing[0]['name'],
                    id=ingredient_id
                )
                # Save to clear ID map
                ingredient_id_map[ingredient_name] = ingredient_id
                existing_count += 1
            else:
                self._log_and_print(f"    ❌ Not found - needs creation")
                self._log_and_print(f"    DEBUG: No existing ingredient found for '{ingredient_name}'", 'debug')
                need_creation.append(ingredient_name)
        
        self._log_and_print(f"✅ eKitchen search complete: {existing_count} found, {len(need_creation)} need creation")
        self._log_and_print(f"DEBUG: Ingredients needing creation: {need_creation}", 'debug')
        
        # Step 3: Enrich missing ingredients with Spoonacular
        if need_creation:
            self._log_and_print(f"🌶️  Enriching {len(need_creation)} ingredients with Spoonacular...")
            self._log_and_print(f"DEBUG: Ingredients to enrich: {need_creation}", 'debug')
            
            for ingredient_name in need_creation:
                self._log_and_print(f"  Enriching: {ingredient_name}")
                self._log_and_print(f"  DEBUG: Starting enrichment for '{ingredient_name}'", 'debug')
                
                # Search Spoonacular
                spoon_result = self.search_spoonacular_ingredient_enhanced(ingredient_name)
                
                if spoon_result:
                    # Enhanced method already includes nutrition data
                    # Convert to old format for compatibility
                    nutrition_data = {
                        'id': spoon_result.id,
                        'name': spoon_result.name,
                        'nutrition': {
                            'nutrients': []
                        }
                    }
                    
                    # Add nutrients if available
                    if spoon_result.calories is not None:
                        nutrition_data['nutrition']['nutrients'].append({
                            'name': 'Calories', 'amount': spoon_result.calories, 'unit': 'kcal'
                        })
                    if spoon_result.protein is not None:
                        nutrition_data['nutrition']['nutrients'].append({
                            'name': 'Protein', 'amount': spoon_result.protein, 'unit': 'g'
                        })
                    if spoon_result.fat is not None:
                        nutrition_data['nutrition']['nutrients'].append({
                            'name': 'Fat', 'amount': spoon_result.fat, 'unit': 'g'
                        })
                    if spoon_result.carbohydrates is not None:
                        nutrition_data['nutrition']['nutrients'].append({
                            'name': 'Carbohydrates', 'amount': spoon_result.carbohydrates, 'unit': 'g'
                        })
                    if spoon_result.sugar is not None:
                        nutrition_data['nutrition']['nutrients'].append({
                            'name': 'Sugar', 'amount': spoon_result.sugar, 'unit': 'g'
                        })
                    
                    nutrition = nutrition_data
                    
                    if nutrition:
                        self._log_and_print(f"    ✅ Enriched with Spoonacular data")
                        self._log_and_print(f"    DEBUG: Spoonacular nutrition data: {nutrition}", 'debug')
                        category = self.categorize_ingredient_with_ai(ingredient_name)
                        tags = self.generate_tags_for_ingredient(ingredient_name, category)
                        
                        ingredient_data = IngredientData(
                            name=ingredient_name,
                            calories=nutrition.get('nutrition', {}).get('nutrients', [{}])[0].get('amount', 0),
                            category=category,
                            external_id=str(spoon_result['id']),
                            tag_names=tags,
                            consistency="solid"
                        )
                        
                        # Extract other nutrients
                        nutrients = nutrition.get('nutrition', {}).get('nutrients', [])
                        for nutrient in nutrients:
                            name = nutrient.get('name', '').lower()
                            amount = nutrient.get('amount', 0)
                            
                            if 'protein' in name:
                                ingredient_data.protein = amount
                            elif 'fat' in name and 'saturated' not in name:
                                ingredient_data.fat = amount
                            elif 'carbohydrate' in name:
                                ingredient_data.carbohydrates = amount
                            elif 'sugar' in name:
                                ingredient_data.sugar = amount
                        
                        result_mapping[ingredient_name] = ingredient_data
                    else:
                        self._log_and_print(f"    ❌ Failed to get nutrition data", 'warning')
                        self._create_fallback_ingredient_data(ingredient_name, result_mapping)
                else:
                    self._log_and_print(f"    ❌ Not found in Spoonacular", 'warning')
                    self._create_fallback_ingredient_data(ingredient_name, result_mapping)
        
        # Step 4: Create missing ingredients in eKitchen and update ID map
        self._log_and_print(f"🏗️  Creating {len([i for i in result_mapping.values() if not i.id])} ingredients in eKitchen...")
        creation_count = 0
        for ingredient_name, ingredient_data in result_mapping.items():
            if not ingredient_data.id:  # Needs to be created
                self._log_and_print(f"  Creating: {ingredient_name}")
                self._log_and_print(f"  DEBUG: Creating ingredient with data: {ingredient_data}", 'debug')
                created_id = self.create_ekitchen_ingredient(ingredient_data)
                if created_id:
                    ingredient_data.id = created_id
                    # Save to clear ID map
                    ingredient_id_map[ingredient_name] = created_id
                    creation_count += 1
                    self._log_and_print(f"    ✅ Created with ID: {created_id}")
                else:
                    self._log_and_print(f"    ❌ Failed to create {ingredient_name} - excluding from recipe", 'error')
        
        self._log_and_print(f"✅ eKitchen creation complete: {creation_count}/{len(need_creation)} successfully created")
        self._log_and_print(f"DEBUG: Final ingredient_id_map: {ingredient_id_map}", 'debug')
        
        # Summary
        self._log_and_print("\n" + "="*60)
        self._log_and_print("🎉 INGREDIENT PROCESSING COMPLETE")
        self._log_and_print("="*60)
        self._log_and_print(f"📊 Processing Results:")
        self._log_and_print(f"   Total Ingredients: {len(unique_ingredients)}")
        self._log_and_print(f"   ✅ Existing in eKitchen: {existing_count}")
        self._log_and_print(f"   🆕 Created in eKitchen: {creation_count}")
        self._log_and_print(f"   📈 Success Rate: {((existing_count + creation_count) / len(unique_ingredients) * 100):.1f}%")
        self._log_and_print("="*60)
        self._log_and_print("🗺️  INGREDIENT ID MAP:")
        for name, id_val in ingredient_id_map.items():
            self._log_and_print(f"   {name} → {id_val}")
        self._log_and_print("="*60)
        
        # Final debug logging
        self._log_and_print(f"DEBUG: Final processing summary - {existing_count} existing + {creation_count} created = {existing_count + creation_count} total processed", 'debug')
        self._log_and_print(f"DEBUG: Full result_mapping keys: {list(result_mapping.keys())}", 'debug')
        
        return result_mapping, ingredient_id_map, ingredients_skipped_by_user
    
    def _create_fallback_ingredient_data(self, ingredient_name: str, result_mapping: Dict[str, IngredientData]):
        """Create fallback ingredient data for failed enrichment"""
        category = self.categorize_ingredient_with_ai(ingredient_name)
        tags = self.generate_tags_for_ingredient(ingredient_name, category)
        tags.append("Needs Review")  # Flag for manual review
        
        result_mapping[ingredient_name] = IngredientData(
            name=ingredient_name,
            category=category,
            tag_names=tags,
            consistency="solid",
            calories=0.0,
            protein=0.0,
            fat=0.0,
            carbohydrates=0.0,
            needs_enrichment=True  # Mark as needing enrichment since we couldn't get Spoonacular data
        )
        self._log_and_print(f"    📝 Added fallback data for creation")
        self._log_and_print(f"    DEBUG: Fallback data - category: {category}, tags: {tags}", 'debug')
    
    def calculate_recipe_nutrition(self, raw_ingredients: List[str], processed_ingredients: Dict[str, IngredientData], num_servings: int = 4) -> Dict[str, float]:
        """Calculate total recipe nutrition from processed ingredients and quantities
        
        Args:
            raw_ingredients: Original ingredient list with quantities (e.g., "2 cups flour")
            processed_ingredients: Ingredient data mapping from process_recipe_ingredients()
            num_servings: Number of servings the recipe makes
            
        Returns:
            Dict with nutrition totals per serving
        """
        print(f"🧮 Calculating recipe nutrition for {num_servings} servings...")
        
        total_calories = 0.0
        total_protein = 0.0
        total_fat = 0.0
        total_carbs = 0.0
        total_fiber = 0.0
        total_sugar = 0.0
        
        for raw_ingredient in raw_ingredients:
            # Extract quantity and clean ingredient name
            clean_name = self.clean_ingredient_name(raw_ingredient)
            quantity_info = self._extract_quantity_from_ingredient(raw_ingredient)
            
            if clean_name in processed_ingredients:
                ingredient_data = processed_ingredients[clean_name]
                
                # Convert quantity to grams for calculation (simplified conversion)
                quantity_grams = self._convert_to_grams(quantity_info['amount'], quantity_info['unit'], clean_name)
                
                # Calculate nutrition contribution (nutrition data is per 100g)
                if quantity_grams > 0:
                    multiplier = quantity_grams / 100.0
                    calories_contribution = (ingredient_data.calories or 0) * multiplier
                    protein_contribution = (ingredient_data.protein or 0) * multiplier
                    fat_contribution = (ingredient_data.fat or 0) * multiplier
                    carbs_contribution = (ingredient_data.carbohydrates or 0) * multiplier
                    sugar_contribution = (ingredient_data.sugar or 0) * multiplier
                    
                    total_calories += calories_contribution
                    total_protein += protein_contribution
                    total_fat += fat_contribution
                    total_carbs += carbs_contribution
                    total_sugar += sugar_contribution
                    
                    print(f"  {clean_name}: {calories_contribution:.1f} cal, {protein_contribution:.1f}g protein")
        
        # Calculate per serving
        per_serving = {
            'calories': round(total_calories / num_servings, 1),
            'protein': round(total_protein / num_servings, 1),
            'fat': round(total_fat / num_servings, 1),
            'carbohydrates': round(total_carbs / num_servings, 1),
            'fiber': round(total_fiber / num_servings, 1),  # Approximated for now
            'sugar': round(total_sugar / num_servings, 1)
        }
        
        print(f"📊 Recipe Nutrition (per serving):")
        print(f"   Calories: {per_serving['calories']}")
        print(f"   Protein: {per_serving['protein']}g")
        print(f"   Fat: {per_serving['fat']}g")
        print(f"   Carbohydrates: {per_serving['carbohydrates']}g")
        print(f"   Sugar: {per_serving['sugar']}g")
        
        return per_serving
    
    def _extract_quantity_from_ingredient(self, raw_ingredient: str) -> Dict[str, Any]:
        """Extract quantity and unit from raw ingredient string"""
        # Simple regex to extract numbers and common units
        import re
        
        # Match patterns like "2 cups", "1.5 lbs", "3 tablespoons"
        pattern = r'(\d+(?:\.\d+)?)\s*(cups?|cup|tablespoons?|tbsp|teaspoons?|tsp|pounds?|lbs?|ounces?|oz|cans?|slices?)'
        match = re.search(pattern, raw_ingredient.lower())
        
        if match:
            return {
                'amount': float(match.group(1)),
                'unit': match.group(2)
            }
        
        return {'amount': 1.0, 'unit': 'serving'}  # Default fallback
    
    def _convert_to_grams(self, amount: float, unit: str, ingredient_name: str) -> float:
        """Convert quantity to grams for nutrition calculation (simplified)"""
        # Simplified conversion factors - in production would need comprehensive unit conversion
        conversion_factors = {
            'cup': 240,  # ml, varies by ingredient
            'cups': 240,
            'tablespoon': 15,
            'tablespoons': 15,
            'tbsp': 15,
            'teaspoon': 5,
            'teaspoons': 5,
            'tsp': 5,
            'pound': 453.6,
            'pounds': 453.6,
            'lbs': 453.6,
            'lb': 453.6,
            'ounce': 28.35,
            'ounces': 28.35,
            'oz': 28.35,
            'can': 400,  # Average can size
            'cans': 400,
            'slice': 30,  # Average slice
            'slices': 30
        }
        
        # Ingredient-specific conversions
        if 'oil' in ingredient_name.lower():
            conversion_factors.update({'cup': 220, 'tablespoon': 14, 'teaspoon': 4.7})
        elif 'flour' in ingredient_name.lower():
            conversion_factors.update({'cup': 120})
        elif 'sugar' in ingredient_name.lower():
            conversion_factors.update({'cup': 200, 'tablespoon': 12.5})
        
        return amount * conversion_factors.get(unit.lower(), 100)  # Default 100g if unknown
    
    def calculate_recipe_nutrition_from_map(self, raw_ingredients: List[str], processed_ingredients: Dict[str, IngredientData], ingredient_id_map: Dict[str, str], num_servings: int = 4) -> Dict[str, float]:
        """Calculate total recipe nutrition using the ingredient ID map
        
        Args:
            raw_ingredients: Original ingredient list with quantities (e.g., "2 cups flour")
            processed_ingredients: Full ingredient data mapping from process_recipe_ingredients()
            ingredient_id_map: Simple ingredient name to ID mapping for verification
            num_servings: Number of servings the recipe makes
            
        Returns:
            Dict with nutrition totals per serving
        """
        print(f"🧮 Calculating recipe nutrition for {num_servings} servings using ID map...")
        
        total_calories = 0.0
        total_protein = 0.0
        total_fat = 0.0
        total_carbs = 0.0
        total_fiber = 0.0
        total_sugar = 0.0
        
        successful_ingredients = 0
        skipped_ingredients = 0
        
        for raw_ingredient in raw_ingredients:
            # Extract quantity and clean ingredient name
            clean_name = self.clean_ingredient_name(raw_ingredient)
            quantity_info = self._extract_quantity_from_ingredient(raw_ingredient)
            
            # Check if ingredient has a valid ID in our map
            if clean_name in ingredient_id_map and clean_name in processed_ingredients:
                ingredient_data = processed_ingredients[clean_name]
                
                # Convert quantity to grams for calculation (simplified conversion)
                quantity_grams = self._convert_to_grams(quantity_info['amount'], quantity_info['unit'], clean_name)
                
                # Calculate nutrition contribution (nutrition data is per 100g)
                if quantity_grams > 0:
                    multiplier = quantity_grams / 100.0
                    calories_contribution = (ingredient_data.calories or 0) * multiplier
                    protein_contribution = (ingredient_data.protein or 0) * multiplier
                    fat_contribution = (ingredient_data.fat or 0) * multiplier
                    carbs_contribution = (ingredient_data.carbohydrates or 0) * multiplier
                    sugar_contribution = (ingredient_data.sugar or 0) * multiplier
                    
                    total_calories += calories_contribution
                    total_protein += protein_contribution
                    total_fat += fat_contribution
                    total_carbs += carbs_contribution
                    total_sugar += sugar_contribution
                    
                    print(f"  ✅ {clean_name} (ID: {ingredient_id_map[clean_name]}): {calories_contribution:.1f} cal, {protein_contribution:.1f}g protein")
                    successful_ingredients += 1
                else:
                    print(f"  ⚠️  {clean_name}: Zero quantity detected")
                    skipped_ingredients += 1
            else:
                print(f"  ❌ {clean_name}: No valid ID mapping - excluding from nutrition calculation")
                skipped_ingredients += 1
        
        # Calculate per serving
        per_serving = {
            'calories': round(total_calories / num_servings, 1),
            'protein': round(total_protein / num_servings, 1),
            'fat': round(total_fat / num_servings, 1),
            'carbohydrates': round(total_carbs / num_servings, 1),
            'fiber': round(total_fiber / num_servings, 1),  # Approximated for now
            'sugar': round(total_sugar / num_servings, 1)
        }
        
        print(f"\n📊 Recipe Nutrition Calculation Results:")
        print(f"   ✅ Successful ingredients: {successful_ingredients}")
        print(f"   ❌ Skipped ingredients: {skipped_ingredients}")
        print(f"   📊 Nutrition per serving ({num_servings} servings total):")
        print(f"     Calories: {per_serving['calories']}")
        print(f"     Protein: {per_serving['protein']}g")
        print(f"     Fat: {per_serving['fat']}g")
        print(f"     Carbohydrates: {per_serving['carbohydrates']}g")
        print(f"     Sugar: {per_serving['sugar']}g")
        
        return per_serving
    
    def _create_nuanced_reference_name(self, raw_ingredient: str) -> str:
        """Create a nuanced reference name that preserves cooking context but removes quantities
        
        Args:
            raw_ingredient: Original ingredient string with quantities
            
        Returns:
            Nuanced name for recipe display (no quantities, but keeps cooking descriptors)
        """
        # Start with original string
        reference = raw_ingredient.strip()
        
        # Remove parenthetical measurements: (15 ounce) can -> can
        reference = re.sub(r'\([^)]*ounce[^)]*\)', '', reference, flags=re.IGNORECASE)
        reference = re.sub(r'\([^)]*inch[^)]*\)', '', reference, flags=re.IGNORECASE)
        reference = re.sub(r'\([^)]*\d[^)]*\)', '', reference, flags=re.IGNORECASE)
        
        # Remove leading numbers and fractions
        reference = re.sub(r'^\d*\.?\d*\s*/?-?\s*\d*\.?\d*\s*', '', reference)
        
        # Remove measurement units but keep descriptive words
        units_pattern = r'\b(?:cups?|tablespoons?|tbsp|teaspoons?|tsp|pounds?|lbs?|ounces?|oz|grams?|g|kilograms?|kg|milliliters?|ml|liters?|l|pints?|quarts?|gallons?)\b'
        reference = re.sub(units_pattern, '', reference, flags=re.IGNORECASE)
        
        # Remove size measurements but keep size descriptors
        reference = re.sub(r'\b\d+[\s-](?:inch|cm|mm)\b', '', reference, flags=re.IGNORECASE)
        
        # Keep cooking descriptors that add value: wooden, fresh, dried, etc.
        # Only remove quantity-related terms
        remove_terms = r'\b(?:pieces?|slices?|strips?|cubes?|halves?|quarters?|cans?|packages?|containers?|jars?|bottles?|bags?|boxes?)\b'
        reference = re.sub(remove_terms, '', reference, flags=re.IGNORECASE)
        
        # Clean up punctuation and whitespace
        reference = re.sub(r'[,;:\-]+', ' ', reference)
        reference = re.sub(r'\s+', ' ', reference).strip()
        
        # Remove leading articles
        reference = re.sub(r'^\b(?:the|a|an)\b\s*', '', reference, flags=re.IGNORECASE)
        
        return reference.strip()

    def format_ingredients_for_recipe(self, raw_ingredients: List[str], ingredient_id_map: Dict[str, str]) -> List[Dict[str, str]]:
        """Format ingredients for eKitchen recipe creation using the ID map
        
        Args:
            raw_ingredients: Original ingredient list with quantities
            ingredient_id_map: Simple ingredient name to ID mapping from process_recipe_ingredients()
            
        Returns:
            List of ingredient dicts formatted for eKitchen recipe creation
        """
        print("📋 Formatting ingredients for recipe creation using ID map...")
        print(f"🗺️  Available ingredient IDs: {list(ingredient_id_map.keys())}")
        
        formatted_ingredients = []
        
        for raw_ingredient in raw_ingredients:
            clean_name = self.clean_ingredient_name(raw_ingredient)
            quantity_info = self._extract_quantity_from_ingredient(raw_ingredient)
            reference_name = self._create_nuanced_reference_name(raw_ingredient)
            
            if clean_name in ingredient_id_map:
                ingredient_id = ingredient_id_map[clean_name]
                formatted_ingredient = {
                    "ingredient_id": ingredient_id,
                    "quantity": str(quantity_info['amount']),
                    "unit": quantity_info['unit'],
                    "reference_as": reference_name
                }
                formatted_ingredients.append(formatted_ingredient)
                print(f"  ✅ {clean_name}: ID {ingredient_id} → display as '{reference_name}'")
            else:
                print(f"  ❌ {clean_name}: No ID found in map - skipping from recipe")
        
        print(f"📦 Formatted {len(formatted_ingredients)} ingredients for recipe")
        return formatted_ingredients

def main():
    """Test the direct ingredient processor"""
    processor = DirectIngredientProcessor()
    
    # Load credentials from environment file
    env_file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'local.env')
    env_vars = load_env_file(env_file_path)
    
    admin_email = env_vars.get('EKITCHEN_ADMIN_EMAIL')
    admin_password = env_vars.get('EKITCHEN_ADMIN_PASSWORD')
    
    if not admin_email or not admin_password:
        print("❌ Missing eKitchen credentials in local.env file")
        print("   Please ensure EKITCHEN_ADMIN_EMAIL and EKITCHEN_ADMIN_PASSWORD are set")
        return
    
    # Authenticate
    if not processor.authenticate_ekitchen(admin_email, admin_password):
        print("❌ Authentication failed - cannot proceed")
        return
    
    # Require ingredients from command line args
    import sys
    if len(sys.argv) < 2:
        print("❌ ERROR: No ingredients provided")
        print("Usage: python3 ingredient_processor_direct.py '<JSON_INGREDIENTS_LIST>'")
        print("Example: python3 ingredient_processor_direct.py '[\"1 cup flour\", \"2 eggs\"]'")
        return
    
    # Parse ingredients from command line (JSON format)
    import json
    try:
        test_ingredients = json.loads(sys.argv[1])
        print(f"🎯 Processing {len(test_ingredients)} provided ingredients")
    except json.JSONDecodeError:
        print("❌ ERROR: Invalid JSON format for ingredients")
        print("Expected format: '[\"ingredient 1\", \"ingredient 2\"]'")
        return
    
    # Process ingredients and get both data and ID map
    processed_ingredients, ingredient_id_map, ingredients_skipped = processor.process_recipe_ingredients(test_ingredients, allow_ingredient_skipping=True)
    
    if ingredients_skipped:
        print(f"\n⏹️  Recipe processing was aborted due to ingredient skipping")
        print(f"✅ INGREDIENT PROCESSING TEST COMPLETE - Recipe was skipped as requested!")
        return
    
    print(f"\n📋 Final ingredient data mapping:")
    for ingredient_name, data in processed_ingredients.items():
        print(f"   {ingredient_name} → ID: {data.id}")
    
    print(f"\n🗺️  Clear ingredient ID map for pipeline:")
    for ingredient_name, ingredient_id in ingredient_id_map.items():
        print(f"   {ingredient_name} → {ingredient_id}")
    
    # Test formatting ingredients for recipe creation
    print(f"\n📦 Testing recipe ingredient formatting...")
    formatted_ingredients = processor.format_ingredients_for_recipe(test_ingredients, ingredient_id_map)
    
    print(f"\n📋 Formatted ingredients for recipe creation:")
    for ingredient in formatted_ingredients:
        print(f"   ID: {ingredient['ingredient_id']}, Qty: {ingredient['quantity']} {ingredient['unit']}, Name: {ingredient['reference_as']}")
    
    # Test nutrition calculation
    print(f"\n🧮 Testing nutrition calculation...")
    nutrition = processor.calculate_recipe_nutrition_from_map(test_ingredients, processed_ingredients, ingredient_id_map, num_servings=4)
    
    print(f"\n✅ PIPELINE TEST COMPLETE - All ingredient IDs properly mapped and ready for recipe creation!")

if __name__ == "__main__":
    main()