#!/usr/bin/env python3
"""
Retroactive Purchase Unit Conversion Fix Script

This script identifies existing ingredients in the database that have purchase units
but missing or incomplete unit conversions, and fixes them by:

1. Querying eKitchen database for ingredients with purchase_info but incomplete conversions
2. Adding purchase units to possible_units if missing
3. Generating AI-powered purchase unit conversions 
4. Updating ingredients with enhanced conversion mappings

Usage:
    python3 fix_purchase_unit_conversions.py --dry-run  # Preview changes
    python3 fix_purchase_unit_conversions.py --apply    # Apply changes
"""

import json
import requests
import sys
import os
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Add the src directory to the path to import the processor
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'processing'))
from ingredient_processor_direct import DirectIngredientProcessor, load_env_file
from unit_conversion_validator import UnitConversionValidator

@dataclass
class IngredientFixCandidate:
    """Data structure for ingredients that need purchase unit conversion fixes"""
    id: str
    name: str
    estimated_cost_unit: Optional[str]
    purchase_info: Optional[Dict[str, Any]]
    unit_conversions: Optional[Dict[str, float]]
    possible_units: List[str]
    needs_fix: str  # Reason why it needs fixing
    
class PurchaseUnitConversionFixer:
    def __init__(self, log_to_file: bool = True):
        # Initialize the base processor with all the enhanced methods
        self.processor = DirectIngredientProcessor(log_to_file=log_to_file)

        # Setup dedicated logging for this fix script
        self.logger = self._setup_fix_logging(log_to_file)
        self.log_to_file = log_to_file

        # Initialize the conversion validator
        self.conversion_validator = UnitConversionValidator(self.logger)
        
        # Track statistics
        self.stats = {
            'total_ingredients': 0,
            'candidates_found': 0,
            'successfully_fixed': 0,
            'already_correct': 0,
            'failed_fixes': 0,
            'skipped': 0
        }
    
    def _setup_fix_logging(self, log_to_file: bool) -> logging.Logger:
        """Setup dedicated logging for the fix script"""
        logger = logging.getLogger('purchase_unit_fixer')
        logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        if log_to_file:
            # Create logs directory if it doesn't exist
            log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            # Create timestamped log file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = os.path.join(log_dir, f'purchase_unit_fix_{timestamp}.log')
            
            # File handler with detailed formatting
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            print(f"📝 Fix script logging enabled: {log_file}")
        
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
    
    def authenticate(self) -> bool:
        """Authenticate with eKitchen API"""
        # Load credentials from environment file
        env_file_path = os.path.join(os.path.dirname(__file__), '..', 'local.env')
        env_vars = load_env_file(env_file_path)
        
        admin_email = env_vars.get('EKITCHEN_ADMIN_EMAIL')
        admin_password = env_vars.get('EKITCHEN_ADMIN_PASSWORD')
        
        if not admin_email or not admin_password:
            self._log_and_print("❌ Missing eKitchen credentials in local.env file", 'error')
            return False
        
        return self.processor.authenticate_ekitchen(admin_email, admin_password)
    
    def get_all_ingredients(self) -> List[Dict[str, Any]]:
        """Fetch all ingredients from eKitchen database"""
        if not self.processor.access_token:
            self._log_and_print("❌ Not authenticated with eKitchen", 'error')
            return []
        
        self._log_and_print("🔍 Fetching all ingredients from eKitchen database...")
        
        all_ingredients = []
        offset = 0
        limit = 50
        
        while True:
            try:
                url = f"{self.processor.ekitchen_base_url}/global-ingredients?limit={limit}&offset={offset}"
                
                headers = {
                    'Authorization': f'Bearer {self.processor.access_token}',
                    'Content-Type': 'application/json'
                }
                
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    # API returns list directly or wrapped in object
                    ingredients = data if isinstance(data, list) else data.get('ingredients', [])
                    
                    if not ingredients:
                        break  # No more ingredients
                    
                    all_ingredients.extend(ingredients)
                    self._log_and_print(f"   📥 Fetched {len(ingredients)} ingredients (total: {len(all_ingredients)})")
                    
                    if len(ingredients) < limit:
                        break  # Last page
                    
                    offset += limit
                    
                else:
                    self._log_and_print(f"❌ Failed to fetch ingredients: {response.status_code}", 'error')
                    break
                    
            except Exception as e:
                self._log_and_print(f"❌ Error fetching ingredients: {e}", 'error')
                break
        
        self._log_and_print(f"✅ Total ingredients fetched: {len(all_ingredients)}")
        return all_ingredients
    
    def analyze_ingredient_for_fix(self, ingredient: Dict[str, Any]) -> Optional[IngredientFixCandidate]:
        """Analyze an ingredient to determine if it needs purchase unit conversion fixes"""
        ingredient_id = ingredient.get('id')
        ingredient_name = ingredient.get('name', 'Unknown')
        estimated_cost_unit = ingredient.get('estimated_cost_unit')
        purchase_info_str = ingredient.get('purchase_info', '{}')
        unit_conversions_str = ingredient.get('unit_conversions', '{}')
        possible_units = ingredient.get('possible_units', [])
        
        # Parse JSON fields
        try:
            purchase_info = json.loads(purchase_info_str) if purchase_info_str else {}
        except json.JSONDecodeError:
            purchase_info = {}
        
        try:
            unit_conversions = json.loads(unit_conversions_str) if unit_conversions_str else {}
        except json.JSONDecodeError:
            unit_conversions = {}
        
        # Skip ingredients without purchase info
        if not purchase_info or not purchase_info.get('purchase_unit'):
            return None
        
        purchase_unit = purchase_info.get('purchase_unit')
        purchase_quantity = purchase_info.get('purchase_quantity')
        
        # Check what needs fixing
        needs_fix_reasons = []
        
        # Check 1: Purchase unit missing from possible_units
        if purchase_unit not in possible_units:
            needs_fix_reasons.append(f"purchase_unit '{purchase_unit}' not in possible_units")
        
        # Check 2: Purchase unit missing from unit_conversions
        if purchase_unit not in unit_conversions:
            needs_fix_reasons.append(f"purchase_unit '{purchase_unit}' not in unit_conversions")
        
        # Check 3: Invalid conversion value (zero, negative, or likely inverted)
        elif purchase_unit in unit_conversions:
            conversion_value = unit_conversions[purchase_unit]
            if conversion_value <= 0:
                needs_fix_reasons.append(f"invalid conversion value for '{purchase_unit}': {conversion_value}")
            else:
                # Check if it's likely inverted using the validator
                is_valid, error_msg, _ = self.conversion_validator.validate_conversion(
                    purchase_unit, conversion_value, estimated_cost_unit or "oz", ingredient_name
                )
                if not is_valid:
                    needs_fix_reasons.append(f"likely inverted conversion for '{purchase_unit}': {conversion_value} (should be > 1.0)")
        
        # Check 4: Missing cost unit in conversions
        if estimated_cost_unit and estimated_cost_unit not in unit_conversions:
            needs_fix_reasons.append(f"cost_unit '{estimated_cost_unit}' not in unit_conversions")
        
        if needs_fix_reasons:
            return IngredientFixCandidate(
                id=ingredient_id,
                name=ingredient_name,
                estimated_cost_unit=estimated_cost_unit,
                purchase_info=purchase_info,
                unit_conversions=unit_conversions,
                possible_units=possible_units,
                needs_fix="; ".join(needs_fix_reasons)
            )
        
        return None
    
    def fix_ingredient_conversions(self, candidate: IngredientFixCandidate, dry_run: bool = True) -> bool:
        """Fix the purchase unit conversions for a single ingredient"""
        self._log_and_print(f"\n🔧 {'[DRY RUN] ' if dry_run else ''}Fixing: {candidate.name} (ID: {candidate.id})")
        self._log_and_print(f"   Issues: {candidate.needs_fix}")
        
        purchase_unit = candidate.purchase_info.get('purchase_unit')
        purchase_quantity = candidate.purchase_info.get('purchase_quantity', 1.0)
        cost_unit = candidate.estimated_cost_unit
        
        if not cost_unit:
            self._log_and_print(f"   ❌ No cost unit defined, cannot fix conversions", 'warning')
            return False
        
        # Step 1: Fix possible_units by adding purchase_unit
        updated_possible_units = candidate.possible_units.copy()
        if purchase_unit not in updated_possible_units:
            updated_possible_units.append(purchase_unit)
            self._log_and_print(f"   ➕ Adding '{purchase_unit}' to possible_units")
        
        # Step 2: Generate purchase unit conversion (skip Spoonacular for efficiency)
        try:
            # Start with existing conversions
            enhanced_conversions = candidate.unit_conversions.copy()
            
            # Always include cost unit identity conversion
            enhanced_conversions[cost_unit] = 1.0
            
            # Add purchase unit conversion using AI estimation (no Spoonacular needed)
            if purchase_unit not in enhanced_conversions or enhanced_conversions[purchase_unit] < 1.0:
                # Generate new conversion or fix inverted one
                purchase_conversion = self.processor.estimate_purchase_unit_conversion(
                    candidate.name, purchase_unit, cost_unit, purchase_quantity
                )
                if purchase_conversion and purchase_conversion > 0:
                    # Validate the conversion
                    is_valid, error_msg, suggested_value = self.conversion_validator.validate_conversion(
                        purchase_unit, purchase_conversion, cost_unit, candidate.name
                    )

                    if not is_valid:
                        self._log_and_print(f"   ⚠️ {error_msg}", 'warning')
                        enhanced_conversions[purchase_unit] = suggested_value
                        self._log_and_print(f"   ✅ Fixed conversion: 1 {purchase_unit} = {suggested_value} {cost_unit}")
                    else:
                        enhanced_conversions[purchase_unit] = purchase_conversion
                        self._log_and_print(f"   ✅ AI generated conversion: 1 {purchase_unit} = {purchase_conversion} {cost_unit}")
                else:
                    self._log_and_print(f"   ❌ Failed to generate purchase unit conversion", 'error')
                    return False
            else:
                # Validate existing conversion
                existing_value = enhanced_conversions[purchase_unit]
                is_valid, error_msg, suggested_value = self.conversion_validator.validate_conversion(
                    purchase_unit, existing_value, cost_unit, candidate.name
                )

                if not is_valid:
                    self._log_and_print(f"   ⚠️ Existing conversion is inverted: {existing_value}")
                    enhanced_conversions[purchase_unit] = suggested_value
                    self._log_and_print(f"   ✅ Fixed to: 1 {purchase_unit} = {suggested_value} {cost_unit}")
                else:
                    self._log_and_print(f"   ✅ Purchase unit conversion already correct: {existing_value}")
            
        except Exception as e:
            self._log_and_print(f"   ❌ Error generating conversions: {e}", 'error')
            return False
        
        # Step 3: Update ingredient in database (if not dry run)
        if not dry_run:
            success = self.update_ingredient_in_database(
                candidate.id,
                updated_possible_units,
                enhanced_conversions
            )
            if success:
                self._log_and_print(f"   ✅ Successfully updated ingredient in database")
                return True
            else:
                self._log_and_print(f"   ❌ Failed to update ingredient in database", 'error')
                return False
        else:
            self._log_and_print(f"   ✅ [DRY RUN] Would update with {len(enhanced_conversions)} conversions")
            return True
    
    def update_ingredient_in_database(self, ingredient_id: str, possible_units: List[str], unit_conversions: Dict[str, float]) -> bool:
        """Update ingredient in eKitchen database with fixed conversions"""
        if not self.processor.access_token:
            return False
        
        try:
            update_data = {
                "id": ingredient_id,
                "possible_units": possible_units,
                "unit_conversions": json.dumps(unit_conversions)
            }
            
            data = json.dumps(update_data).encode('utf-8')
            url = f"{self.processor.ekitchen_base_url}/global-ingredients/{ingredient_id}"
            
            headers = {
                'Authorization': f'Bearer {self.processor.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.patch(url, data=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return True
            else:
                self._log_and_print(f"   ❌ Update failed: {response.status_code} - {response.text}", 'error')
                return False
                
        except Exception as e:
            self._log_and_print(f"   ❌ Error updating ingredient: {e}", 'error')
            return False
    
    def run_fix(self, dry_run: bool = True, max_fixes: int = None):
        """Run the complete purchase unit conversion fix process"""
        self._log_and_print("🚀 Starting Purchase Unit Conversion Fix Script")
        self._log_and_print("=" * 70)
        self._log_and_print(f"Mode: {'DRY RUN (preview only)' if dry_run else 'APPLY CHANGES'}")
        if max_fixes:
            self._log_and_print(f"Limit: {max_fixes} fixes maximum")
        self._log_and_print("=" * 70)
        
        # Step 1: Authenticate
        if not self.authenticate():
            self._log_and_print("❌ Authentication failed - cannot proceed", 'error')
            return
        
        # Step 2: Fetch all ingredients
        all_ingredients = self.get_all_ingredients()
        if not all_ingredients:
            self._log_and_print("❌ No ingredients found - cannot proceed", 'error')
            return
        
        self.stats['total_ingredients'] = len(all_ingredients)
        
        # Step 3: Analyze ingredients to find fix candidates
        self._log_and_print(f"\n🔍 Analyzing {len(all_ingredients)} ingredients for conversion issues...")
        
        candidates = []
        for ingredient in all_ingredients:
            candidate = self.analyze_ingredient_for_fix(ingredient)
            if candidate:
                candidates.append(candidate)
        
        self.stats['candidates_found'] = len(candidates)
        
        if not candidates:
            self._log_and_print("✅ No ingredients found that need purchase unit conversion fixes!")
            self.print_final_summary()
            return
        
        self._log_and_print(f"📋 Found {len(candidates)} ingredients needing fixes:")
        for i, candidate in enumerate(candidates[:10]):  # Show first 10
            self._log_and_print(f"   {i+1}. {candidate.name} - {candidate.needs_fix}")
        if len(candidates) > 10:
            self._log_and_print(f"   ... and {len(candidates) - 10} more")
        
        # Step 4: Apply fixes
        if max_fixes:
            candidates = candidates[:max_fixes]
            self._log_and_print(f"\n🎯 Processing first {len(candidates)} candidates (limit applied)")
        
        self._log_and_print(f"\n{'🔧 Applying fixes...' if not dry_run else '👀 Previewing fixes...'}")
        
        for i, candidate in enumerate(candidates):
            self._log_and_print(f"\n--- {i+1}/{len(candidates)} ---")
            
            try:
                success = self.fix_ingredient_conversions(candidate, dry_run=dry_run)
                if success:
                    self.stats['successfully_fixed'] += 1
                else:
                    self.stats['failed_fixes'] += 1
            except Exception as e:
                self._log_and_print(f"❌ Unexpected error fixing {candidate.name}: {e}", 'error')
                self.stats['failed_fixes'] += 1
        
        # Step 5: Print summary
        self.print_final_summary()
    
    def print_final_summary(self):
        """Print final statistics summary"""
        self._log_and_print("\n" + "=" * 70)
        self._log_and_print("📊 PURCHASE UNIT CONVERSION FIX SUMMARY")
        self._log_and_print("=" * 70)
        self._log_and_print(f"Total ingredients analyzed: {self.stats['total_ingredients']}")
        self._log_and_print(f"Candidates needing fixes: {self.stats['candidates_found']}")
        self._log_and_print(f"Successfully fixed: {self.stats['successfully_fixed']}")
        self._log_and_print(f"Failed fixes: {self.stats['failed_fixes']}")
        
        if self.stats['successfully_fixed'] > 0:
            self._log_and_print(f"\n✅ {self.stats['successfully_fixed']} ingredients now have proper purchase unit conversions!")
            self._log_and_print("   Users can now use purchase units in recipes and shopping lists")
        
        if self.stats['failed_fixes'] > 0:
            self._log_and_print(f"\n⚠️  {self.stats['failed_fixes']} ingredients failed to fix - check logs for details")
        
        success_rate = (self.stats['successfully_fixed'] / self.stats['candidates_found'] * 100) if self.stats['candidates_found'] > 0 else 0
        self._log_and_print(f"\n📈 Success rate: {success_rate:.1f}%")
        self._log_and_print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description='Fix purchase unit conversions for existing ingredients')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying them')
    parser.add_argument('--apply', action='store_true', help='Apply the fixes to the database')
    parser.add_argument('--limit', type=int, help='Maximum number of ingredients to fix')
    parser.add_argument('--no-logs', action='store_true', help='Disable file logging')
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.apply:
        print("❌ Error: Must specify either --dry-run or --apply")
        print("Usage:")
        print("  python3 fix_purchase_unit_conversions.py --dry-run     # Preview changes")
        print("  python3 fix_purchase_unit_conversions.py --apply       # Apply changes")
        return
    
    if args.dry_run and args.apply:
        print("❌ Error: Cannot specify both --dry-run and --apply")
        return
    
    # Initialize the fixer
    fixer = PurchaseUnitConversionFixer(log_to_file=not args.no_logs)
    
    # Run the fix process
    fixer.run_fix(
        dry_run=args.dry_run,
        max_fixes=args.limit
    )

if __name__ == "__main__":
    main()