#!/usr/bin/env python3
"""
Backfill Default Decay Rate and Typical Shelf Life for Existing Ingredients

This script assigns default_decay_rate and typical_shelf_life_days to all existing
global ingredients based on their category field following the BACKEND-2 migration.

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

Usage:
    python backfill_decay_and_shelf_life.py --dry-run   # Preview changes
    python backfill_decay_and_shelf_life.py --live      # Actually update ingredients
    python backfill_decay_and_shelf_life.py --limit 10  # Process only 10 ingredients
"""

import sys
import os
import argparse
import json
import time
import requests
from typing import Dict, List, Any, Optional, Tuple
from openai import OpenAI

# Add the processing directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'processing'))
from ingredient_processor_direct import DirectIngredientProcessor


class DecayRateBackfiller:
    """Backfill default_decay_rate and typical_shelf_life_days for existing ingredients"""

    # Category-based decay rate mappings
    CATEGORY_DECAY_MAP = {
        'proteins': ('fast', 5),
        'dairy': ('medium', 10),
        'vegetables': ('needs_ai', None),  # AI decides: leafy→fast/7, root→slow/21
        'fruits': ('needs_ai', None),      # AI decides: berries→fast/7, citrus→slow/21
        'grains': ('pantry', 365),
        'condiments': ('pantry', 180),
        'spices': ('pantry', 730),
        'beverages': ('needs_ai', None),   # AI decides: bottled→pantry/180, fresh→medium/14
        'other': ('medium', 30)            # Default fallback
    }

    def __init__(self):
        print("🔧 Initializing decay rate backfiller...")

        # Initialize processor for authentication and configuration
        self.processor = DirectIngredientProcessor(log_to_file=False)

        # Initialize OpenAI for smart categorization
        try:
            openai_api_key = self.processor.env_config.get('OPENAI_API_KEY', '')
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY not found in environment configuration")

            self.openai_client = OpenAI(api_key=openai_api_key)
            print("✅ OpenAI client initialized for AI-powered categorization")
        except Exception as e:
            print(f"❌ Failed to initialize OpenAI: {e}")
            raise

        # Statistics tracking
        self.stats = {
            'ingredients_processed': 0,
            'ingredients_skipped': 0,
            'ai_decisions_made': 0,
            'ai_fallback_used': 0,
            'category_based_updates': 0,
            'errors': []
        }

        # Preview data tracking
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

    def get_all_ingredients(self, limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all global ingredients from eKitchen API"""
        try:
            url = f"{self.processor.ekitchen_base_url}/global-ingredients/"
            params = {
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

                print(f"✅ Retrieved {len(ingredients)} ingredients (offset: {offset})")
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

    def determine_decay_rate_with_ai(
        self,
        ingredient_name: str,
        category: str
    ) -> Tuple[str, int]:
        """
        Use AI to determine decay rate for ambiguous categories like vegetables, fruits, beverages.

        Returns:
            Tuple of (decay_rate, shelf_life_days)
        """
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
                    # Invalid response, use default
                    print(f"   ⚠️ AI returned unexpected value '{decay_rate}' for {category}, using medium/14")
                    decay_rate = 'medium'
                    shelf_life = 14

            elif category == 'beverages':
                if decay_rate == 'pantry':
                    shelf_life = 180
                elif decay_rate == 'medium':
                    shelf_life = 14
                else:
                    # Invalid response, use default
                    print(f"   ⚠️ AI returned unexpected value '{decay_rate}' for beverages, using pantry/180")
                    decay_rate = 'pantry'
                    shelf_life = 180

            print(f"   🤖 AI determined: '{ingredient_name}' ({category}) → {decay_rate}, {shelf_life} days")
            self.stats['ai_decisions_made'] += 1
            return (decay_rate, shelf_life)

        except Exception as e:
            print(f"   ❌ AI decision failed for '{ingredient_name}': {e}")
            # Fallback to medium/14 days
            return ('medium', 14)

    def determine_decay_rate_and_shelf_life(
        self,
        ingredient_name: str,
        category: str
    ) -> Tuple[str, int]:
        """
        Determine decay rate and shelf life based on category.

        Returns:
            Tuple of (decay_rate, shelf_life_days)
        """
        if category not in self.CATEGORY_DECAY_MAP:
            print(f"   ⚠️ Unknown category '{category}', using default: medium/30 days")
            return ('medium', 30)

        decay_rate, shelf_life = self.CATEGORY_DECAY_MAP[category]

        # Check if AI decision is needed
        if decay_rate == 'needs_ai':
            return self.determine_decay_rate_with_ai(ingredient_name, category)
        else:
            print(f"   📊 Category-based: '{ingredient_name}' ({category}) → {decay_rate}, {shelf_life} days")
            self.stats['category_based_updates'] += 1
            return (decay_rate, shelf_life)

    def update_ingredient(
        self,
        ingredient_id: str,
        update_data: Dict[str, Any],
        dry_run: bool = True
    ) -> bool:
        """Update an ingredient with decay rate and shelf life"""
        if dry_run:
            print(f"   🧪 DRY RUN: Would update ingredient {ingredient_id}")
            print(f"      {json.dumps(update_data, indent=6)}")
            return True

        try:
            url = f"{self.processor.ekitchen_base_url}/global-ingredients/{ingredient_id}"
            headers = {
                'Authorization': f'Bearer {self.processor.access_token}',
                'Content-Type': 'application/json'
            }

            # Add update_mask with the fields we're updating
            update_mask = 'DefaultDecayRate,TypicalShelfLifeDays'
            params = {'update_mask': update_mask}

            response = requests.patch(url, json=update_data, headers=headers, params=params, timeout=30)

            if response.status_code in [200, 204]:
                print(f"   ✅ Successfully updated ingredient {ingredient_id}")
                return True
            else:
                print(f"   ❌ Failed to update ingredient {ingredient_id}: {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"      Error details: {error_detail}")
                except:
                    print(f"      Error response: {response.text}")
                return False

        except Exception as e:
            print(f"   ❌ Error updating ingredient {ingredient_id}: {e}")
            return False

    def process_single_ingredient(
        self,
        ingredient: Dict[str, Any],
        dry_run: bool = True
    ) -> bool:
        """Process a single ingredient: determine and set decay rate and shelf life"""
        ingredient_id = ingredient.get('id')
        ingredient_name = ingredient.get('name', 'Unknown')
        category = ingredient.get('category', 'other')

        # Skip test ingredients
        if ingredient_name.lower().startswith('test'):
            print(f"\n⏭️  Skipping test ingredient: {ingredient_name}")
            self.stats['ingredients_skipped'] += 1
            return False

        # Check if already has decay rate set
        existing_decay_rate = ingredient.get('default_decay_rate')
        existing_shelf_life = ingredient.get('typical_shelf_life_days')

        print(f"\n{'='*60}")
        print(f"🥕 Processing: {ingredient_name}")
        print(f"   ID: {ingredient_id}")
        print(f"   Category: {category}")
        print(f"   Current Decay Rate: {existing_decay_rate or 'Not Set'}")
        print(f"   Current Shelf Life: {existing_shelf_life or 'Not Set'} days")

        if not ingredient_id or not ingredient_name:
            print("   ⚠️ Missing ingredient ID or name - skipping")
            self.stats['ingredients_skipped'] += 1
            return False

        # Skip if already has values set (unless we're in force mode - future enhancement)
        if existing_decay_rate and existing_shelf_life:
            print("   ✅ Already has decay rate and shelf life - skipping")
            self.stats['ingredients_skipped'] += 1
            return False

        try:
            # Determine decay rate and shelf life
            decay_rate, shelf_life = self.determine_decay_rate_and_shelf_life(
                ingredient_name,
                category
            )

            # Prepare update data
            update_data = {
                "id": ingredient_id,
                "default_decay_rate": decay_rate,
                "typical_shelf_life_days": shelf_life
            }

            # Track preview data
            preview_entry = {
                "ingredient_id": ingredient_id,
                "ingredient_name": ingredient_name,
                "category": category,
                "decay_rate": decay_rate,
                "shelf_life_days": shelf_life,
                "previous_decay_rate": existing_decay_rate,
                "previous_shelf_life": existing_shelf_life
            }
            self.preview_data.append(preview_entry)

            # Update the ingredient
            success = self.update_ingredient(ingredient_id, update_data, dry_run)

            if success:
                self.stats['ingredients_processed'] += 1
                print(f"   ✅ Successfully processed: {ingredient_name}")
                return True
            else:
                print(f"   ❌ Failed to process: {ingredient_name}")
                self.stats['ingredients_skipped'] += 1
                return False

        except Exception as e:
            error_msg = f"Error processing ingredient {ingredient_name}: {e}"
            print(f"   ❌ {error_msg}")
            self.stats['errors'].append(error_msg)
            self.stats['ingredients_skipped'] += 1
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
            print(f"💾 Preview data saved to: {filename}")
        except Exception as e:
            print(f"❌ Failed to save preview data: {e}")

    def backfill_all_ingredients(
        self,
        limit: Optional[int] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Main method: backfill decay rate and shelf life for all ingredients

        Args:
            limit: Maximum number of ingredients to process (None for all)
            dry_run: Preview changes without making them
        """
        print(f"🚀 Starting decay rate and shelf life backfill...")
        print(f"📋 Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        if limit:
            print(f"📊 Limit: {limit} ingredients")

        start_time = time.time()

        # Authenticate
        if not self.authenticate():
            return {"success": False, "error": "Authentication failed"}

        try:
            # Get all ingredients (with pagination if needed)
            print(f"\n{'='*60}")
            print("📋 STEP 1: Retrieving all ingredients")

            all_ingredients = []
            offset = 0
            batch_size = 500  # Fetch in batches of 500

            while True:
                batch = self.get_all_ingredients(limit=batch_size, offset=offset)
                if not batch:
                    break

                all_ingredients.extend(batch)
                offset += batch_size

                # Apply limit if specified
                if limit and len(all_ingredients) >= limit:
                    all_ingredients = all_ingredients[:limit]
                    break

                # If we got fewer than batch_size, we've reached the end
                if len(batch) < batch_size:
                    break

                # Brief pause between batches
                time.sleep(0.5)

            if not all_ingredients:
                return {"success": True, "message": "No ingredients found"}

            print(f"✅ Found {len(all_ingredients)} total ingredients")

            # Process each ingredient
            print(f"\n{'='*60}")
            print("🔄 STEP 2: Processing ingredients")

            for i, ingredient in enumerate(all_ingredients, 1):
                print(f"\n--- Processing {i}/{len(all_ingredients)} ---")
                self.process_single_ingredient(ingredient, dry_run)

                # Rate limiting for live updates
                if not dry_run:
                    time.sleep(0.5)

            # Final summary
            duration = time.time() - start_time
            print(f"\n{'='*60}")
            print("📊 BACKFILL COMPLETE!")
            print(f"⏱️  Duration: {duration:.1f} seconds")
            print(f"✅ Ingredients processed: {self.stats['ingredients_processed']}")
            print(f"⏭️  Ingredients skipped: {self.stats['ingredients_skipped']}")
            print(f"🤖 AI decisions made: {self.stats['ai_decisions_made']}")
            print(f"📊 Category-based updates: {self.stats['category_based_updates']}")
            print(f"❌ Errors: {len(self.stats['errors'])}")

            if self.stats['errors']:
                print("\n🚨 ERRORS:")
                for error in self.stats['errors']:
                    print(f"   - {error}")

            # Save preview data
            if self.preview_data:
                preview_file = f"data-maintenance/decay_backfill_preview_{int(time.time())}.json"
                self.save_preview_data(preview_file)

            return {
                "success": True,
                "stats": self.stats,
                "duration": duration
            }

        except Exception as e:
            error_msg = f"Fatal error during backfill: {e}"
            print(f"💥 {error_msg}")
            return {"success": False, "error": error_msg}


def main():
    parser = argparse.ArgumentParser(description='Backfill Decay Rate and Shelf Life for Global Ingredients')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Preview changes without making them (default)')
    parser.add_argument('--live', action='store_true',
                       help='Actually perform the backfill')
    parser.add_argument('--limit', type=int,
                       help='Maximum number of ingredients to process (default: all)')

    args = parser.parse_args()

    # Default to dry run unless --live is specified
    dry_run = not args.live

    backfiller = DecayRateBackfiller()
    result = backfiller.backfill_all_ingredients(limit=args.limit, dry_run=dry_run)

    if result['success']:
        print(f"\n🎉 Backfill {'simulated' if dry_run else 'completed'} successfully!")
    else:
        print(f"\n💥 Backfill failed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
