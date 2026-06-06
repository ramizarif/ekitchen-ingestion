#!/usr/bin/env python3
"""
Enhanced Batch Recipe Processor - Process recipes from dish names or URLs
Handles recipe discovery and autonomous processing
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

# Repo root on path → use the CURRENT services pipeline, NOT the legacy
# processors (the legacy ones bypass the ingredient validation gate and
# catalog-wide dedup matching — docs/CATALOG_POLLUTION_HANDOFF.md).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.recipe_processor import DirectRecipeProcessor, RecipeProcessingResult

class EnhancedBatchProcessor:
    """Enhanced batch processor with recipe discovery capabilities"""
    
    def __init__(self, log_to_file: bool = True):
        self.processor = DirectRecipeProcessor(log_to_file=log_to_file)
        self.results = []
        self.start_time = None
        self.cuisine_name = None
        self.input_file_path = None
    
    def process_from_dish_names(self, dish_names_file: str, cuisine_name: str = "unknown", 
                               image_output_dir: str = "./batch-generated-images",
                               max_recipes_per_dish: int = 1) -> Dict[str, Any]:
        """
        Process recipes starting from a dish names text file
        
        Args:
            dish_names_file: Path to .txt file with dish names (one per line)
            cuisine_name: Name of cuisine for better search results
            image_output_dir: Directory to save generated images
            max_recipes_per_dish: Maximum recipes to find per dish name
            
        Returns:
            Dict with batch processing results
        """
        # Store cuisine and file info for report saving
        self.cuisine_name = cuisine_name
        self.input_file_path = dish_names_file
        
        print(f"📂 Loading dish names from: {dish_names_file}")
        
        # Load existing recipes.json to check for already processed recipes
        self.recipes_json_path = os.path.join(os.path.dirname(dish_names_file), 'recipes.json')
        self.existing_recipes = self._load_existing_recipes()
        
        # Load dish names
        try:
            with open(dish_names_file, 'r') as f:
                dish_names = [line.strip() for line in f.readlines() if line.strip()]
        except Exception as e:
            print(f"❌ Failed to load dish names: {e}")
            return {"success": False, "error": str(e)}
        
        print(f"📋 Found {len(dish_names)} dish names to discover recipes for")
        print(f"🍽️  Cuisine: {cuisine_name}")
        
        # Phase 1: Recipe Discovery
        print("\n🔍 PHASE 1: RECIPE DISCOVERY")
        print("="*60)
        
        discovered_recipes = []
        
        for i, dish_name in enumerate(dish_names, 1):
            print(f"\n🔎 Checking recipe for: {dish_name} ({i}/{len(dish_names)})")
            
            # Check if this dish was already scraped
            if self._is_dish_already_scraped(dish_name):
                print(f"⏭️  Skipping {dish_name} - already scraped")
                continue
            
            # Check if URL already exists in recipes.json
            existing_url = self._get_existing_recipe_url(dish_name)
            if existing_url:
                print(f"📋 Using existing URL for {dish_name}")
                recipe_urls = [existing_url]
            else:
                print(f"🔍 Discovering new URL for {dish_name}")
                try:
                    # Use recipe discovery to find URLs
                    recipe_urls = self._discover_recipe_urls(dish_name, cuisine_name, max_recipes_per_dish)
                except Exception as e:
                    print(f"❌ Discovery failed for {dish_name}: {e}")
                    continue
            
            if recipe_urls:
                for j, url in enumerate(recipe_urls):
                    discovered_recipes.append({
                        'name': f"{dish_name} (Recipe {j+1})" if len(recipe_urls) > 1 else dish_name,
                        'url': url,
                        'dish_name': dish_name,
                        'cuisine': cuisine_name
                    })
                print(f"✅ Using {len(recipe_urls)} recipe(s) for {dish_name}")
            else:
                print(f"❌ No recipes found for {dish_name}")
            
            # Brief pause between discoveries
            if i < len(dish_names):
                time.sleep(2)
        
        print(f"\n📊 Discovery complete: {len(discovered_recipes)} total recipes found")
        
        # Save discovered recipes to JSON for reference
        self._save_discovered_recipes(discovered_recipes, cuisine_name, image_output_dir)
        
        # Phase 2: Recipe Processing
        if not discovered_recipes:
            print("❌ No recipes discovered - skipping processing phase")
            return {"success": False, "error": "No recipes discovered"}
        
        print(f"\n🚀 PHASE 2: RECIPE PROCESSING")
        print("="*60)
        
        return self.process_recipe_list(discovered_recipes, image_output_dir)
    
    def _discover_recipe_urls(self, dish_name: str, cuisine_name: str, max_results: int = 1) -> List[str]:
        """
        Discover recipe URLs for a dish name using simplified discovery
        
        Args:
            dish_name: Name of the dish to search for
            cuisine_name: Cuisine type for better search results  
            max_results: Maximum number of URLs to return
            
        Returns:
            List of recipe URLs
        """
        try:
            # Import simplified discovery
            sys.path.append('.')
            from simplified_recipe_discovery import SimplifiedRecipeDiscovery
            
            # Create discovery instance
            discovery = SimplifiedRecipeDiscovery()
            
            # Find recipe URL
            recipe_url = discovery.find_recipe_url(dish_name)
            
            if recipe_url:
                return [recipe_url]
            else:
                return []
            
        except Exception as e:
            print(f"❌ Discovery failed: {e}")
            return []
    
    def _save_discovered_recipes(self, discovered_recipes: List[Dict[str, str]], 
                                cuisine_name: str, output_dir: str):
        """Save discovered recipes to JSON file for reference"""
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_path = os.path.join(output_dir, f'discovered_{cuisine_name}_recipes_{timestamp}.json')
        
        # Group by dish name for cleaner JSON structure
        recipes_by_dish = {}
        for recipe in discovered_recipes:
            dish_name = recipe['dish_name']
            if dish_name not in recipes_by_dish:
                recipes_by_dish[dish_name] = []
            recipes_by_dish[dish_name].append({
                'url': recipe['url'],
                'name': recipe['name']
            })
        
        discovery_data = {
            "discovery_info": {
                "cuisine": cuisine_name,
                "timestamp": datetime.now().isoformat(),
                "total_dishes": len(recipes_by_dish),
                "total_recipes": len(discovered_recipes)
            },
            "recipes": recipes_by_dish
        }
        
        with open(json_path, 'w') as f:
            json.dump(discovery_data, f, indent=2)
        
        print(f"💾 Discovered recipes saved: {json_path}")
    
    def process_recipes_from_json(self, recipes_json_path: str, image_output_dir: str = "./batch-generated-images") -> Dict[str, Any]:
        """Process recipes from existing JSON file (same as original batch processor)"""
        print(f"📂 Loading recipes from: {recipes_json_path}")
        
        try:
            with open(recipes_json_path, 'r') as f:
                recipes_data = json.load(f)
        except Exception as e:
            print(f"❌ Failed to load recipes JSON: {e}")
            return {"success": False, "error": str(e)}
        
        # Extract URLs based on JSON structure
        recipe_urls = []
        if isinstance(recipes_data, dict):
            # Handle structure: {"Recipe Name": {"url": "...", ...}, ...}
            for recipe_name, recipe_info in recipes_data.items():
                if isinstance(recipe_info, dict) and 'url' in recipe_info:
                    recipe_urls.append({
                        'name': recipe_name,
                        'url': recipe_info['url']
                    })
                elif isinstance(recipe_info, str):
                    # Handle structure: {"Recipe Name": "url", ...}
                    recipe_urls.append({
                        'name': recipe_name,
                        'url': recipe_info
                    })
        elif isinstance(recipes_data, list):
            # Handle structure: ["url1", "url2", ...]
            for i, url in enumerate(recipes_data):
                recipe_urls.append({
                    'name': f"Recipe_{i+1}",
                    'url': url
                })
        
        print(f"📋 Found {len(recipe_urls)} recipes to process")
        return self.process_recipe_list(recipe_urls, image_output_dir)
    
    def process_recipe_list(self, recipe_urls: List[Dict[str, str]], image_output_dir: str = "./batch-generated-images", target_success_count: Optional[int] = None) -> Dict[str, Any]:
        """Process a list of recipe URLs.

        If target_success_count is set, iteration stops as soon as that many recipes
        have been successfully created. Skipped duplicates do not count as failures
        and do not consume one of the target slots — they're just bypassed.
        """
        self.start_time = time.time()
        self.results = []

        print("🚀 STARTING BATCH RECIPE PROCESSING")
        print("="*80)
        print(f"📊 Total Recipes Available: {len(recipe_urls)}")
        if target_success_count:
            print(f"🎯 Target Successes: {target_success_count} (will stop iterating once reached)")
        print(f"🖼️  Image Directory: {image_output_dir}")
        print(f"🕒 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        successful_count = 0
        failed_count = 0
        skipped_count = 0
        attempted = 0

        for i, recipe_info in enumerate(recipe_urls, 1):
            if target_success_count is not None and successful_count >= target_success_count:
                print(f"\n🎯 Target reached ({successful_count}/{target_success_count}) — stopping early")
                break

            recipe_name = recipe_info['name']
            recipe_url = recipe_info['url']
            attempted += 1

            print(f"\n🔄 PROCESSING RECIPE {i}/{len(recipe_urls)}")
            print(f"📋 Name: {recipe_name}")
            print(f"🌐 URL: {recipe_url}")
            print("-" * 60)

            # Process individual recipe
            try:
                result = self.processor.process_recipe_autonomous(recipe_url, image_output_dir)

                # Add recipe info to result
                result.recipe_name = result.recipe_name or recipe_name
                self.results.append({
                    'index': i,
                    'input_name': recipe_name,
                    'input_url': recipe_url,
                    'result': result
                })

                if result.success:
                    successful_count += 1
                    print(f"✅ Recipe {i} completed successfully: {result.recipe_name}")

                    # Mark this dish as scraped immediately
                    if hasattr(self, 'existing_recipes') and hasattr(self, 'recipes_json_path'):
                        self._mark_dish_as_scraped(recipe_name, recipe_url, result)
                elif getattr(result, 'skipped', False):
                    skipped_count += 1
                    print(f"⏭️  Recipe {i} skipped: {result.error_message}")
                else:
                    failed_count += 1
                    print(f"❌ Recipe {i} failed: {result.error_message}")

            except Exception as e:
                failed_count += 1
                print(f"❌ Recipe {i} failed with exception: {e}")
                self.results.append({
                    'index': i,
                    'input_name': recipe_name,
                    'input_url': recipe_url,
                    'result': RecipeProcessingResult(
                        success=False,
                        error_message=f"Exception: {e}"
                    )
                })

            # Brief pause between recipes to avoid overwhelming APIs
            still_have_more = (target_success_count is None or successful_count < target_success_count) and i < len(recipe_urls)
            if still_have_more:
                print("⏳ Pausing 5 seconds before next recipe...")
                time.sleep(5)
        
        # Generate final report
        total_time = time.time() - self.start_time
        
        print("\n" + "="*80)
        print("🎉 BATCH PROCESSING COMPLETE!")
        print("="*80)
        print(f"📊 Final Results:")
        print(f"   URLs Available: {len(recipe_urls)}")
        print(f"   URLs Attempted: {attempted}")
        print(f"   ✅ Successful: {successful_count}")
        print(f"   ⏭️  Skipped (duplicates): {skipped_count}")
        print(f"   ❌ Failed: {failed_count}")
        denom = max(attempted, 1)
        print(f"   📈 Success Rate (of attempted): {(successful_count / denom * 100):.1f}%")
        print(f"   ⏱️  Total Time: {total_time:.1f} seconds")
        if attempted > 0:
            print(f"   ⏱️  Avg Time per Attempt: {(total_time / attempted):.1f} seconds")
        print("="*80)

        # Save detailed report
        self._save_batch_report(image_output_dir, total_time)

        return {
            "success": True,
            "total_recipes": len(recipe_urls),
            "attempted_count": attempted,
            "successful_count": successful_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "success_rate": (successful_count / denom * 100),
            "total_time_seconds": total_time,
            "results": self.results
        }
    
    def _save_batch_report(self, output_dir: str, total_time: float):
        """Save detailed batch processing report to cuisine directory"""
        
        # Determine where to save the report
        if self.input_file_path and self.input_file_path.startswith('cuisines/'):
            # Extract cuisine directory from input path (e.g., cuisines/thai/dish-names.txt -> cuisines/thai/)
            cuisine_dir = os.path.dirname(self.input_file_path)
            report_dir = cuisine_dir
            print(f"📁 Saving report to cuisine directory: {report_dir}")
        else:
            # Fallback to output directory
            report_dir = output_dir
            print(f"📁 Saving report to output directory: {report_dir}")
        
        os.makedirs(report_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        cuisine_suffix = f"_{self.cuisine_name}" if self.cuisine_name and self.cuisine_name != "unknown" else ""
        report_path = os.path.join(report_dir, f'batch_report{cuisine_suffix}_{timestamp}.json')
        
        report_data = {
            "batch_info": {
                "timestamp": datetime.now().isoformat(),
                "total_recipes": len(self.results),
                "total_time_seconds": total_time,
                "successful_count": sum(1 for r in self.results if r['result'].success),
                "failed_count": sum(1 for r in self.results if not r['result'].success)
            },
            "individual_results": []
        }
        
        for result_info in self.results:
            result = result_info['result']
            report_data["individual_results"].append({
                "index": result_info['index'],
                "input_name": result_info['input_name'],
                "input_url": result_info['input_url'],
                "success": result.success,
                "recipe_id": result.recipe_id,
                "recipe_name": result.recipe_name,
                "ingredients_processed": result.ingredients_processed,
                "image_generated": result.image_generated,
                "processing_time_seconds": result.processing_time_seconds,
                "error_message": result.error_message
            })
        
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"📄 Detailed report saved: {report_path}")
    
    def _load_existing_recipes(self) -> Dict[str, Any]:
        """Load existing recipes.json to check for already processed recipes"""
        if not os.path.exists(self.recipes_json_path):
            print(f"📋 No existing recipes.json found at {self.recipes_json_path}")
            return {}
        
        try:
            with open(self.recipes_json_path, 'r') as f:
                existing_recipes = json.load(f)
            print(f"📋 Loaded {len(existing_recipes)} existing recipes from {self.recipes_json_path}")
            return existing_recipes
        except Exception as e:
            print(f"⚠️  Failed to load existing recipes.json: {e}")
            return {}
    
    def _is_dish_already_scraped(self, dish_name: str) -> bool:
        """Check if a dish has already been scraped (has 'scraped': true flag)"""
        if dish_name in self.existing_recipes:
            recipe_info = self.existing_recipes[dish_name]
            if isinstance(recipe_info, dict) and recipe_info.get('scraped', False):
                return True
        return False
    
    def _get_existing_recipe_url(self, dish_name: str) -> Optional[str]:
        """Get existing recipe URL from recipes.json if it exists"""
        if dish_name in self.existing_recipes:
            recipe_info = self.existing_recipes[dish_name]
            if isinstance(recipe_info, dict) and 'url' in recipe_info:
                return recipe_info['url']
        return None
    
    def _mark_dish_as_scraped(self, dish_name: str, recipe_url: str, recipe_result):
        """Mark a dish as scraped in recipes.json immediately after successful processing"""
        if not hasattr(self, 'existing_recipes'):
            self.existing_recipes = {}
        
        # Update the recipes data structure
        if dish_name not in self.existing_recipes:
            self.existing_recipes[dish_name] = {}
        
        # Update with scraped status and processing info
        self.existing_recipes[dish_name].update({
            'url': recipe_url,
            'scraped': True,
            'recipe_id': getattr(recipe_result, 'recipe_id', None),
            'recipe_name': getattr(recipe_result, 'recipe_name', None),
            'scraped_timestamp': datetime.now().isoformat(),
            'image_generated': getattr(recipe_result, 'image_generated', False),
            'ingredients_processed': getattr(recipe_result, 'ingredients_processed', 0)
        })
        
        # Save immediately to prevent loss on restart
        self._save_recipes_json()
        print(f"✅ Marked {dish_name} as scraped in recipes.json")
    
    def _save_recipes_json(self):
        """Save the current recipes data to recipes.json"""
        try:
            os.makedirs(os.path.dirname(self.recipes_json_path), exist_ok=True)
            with open(self.recipes_json_path, 'w') as f:
                json.dump(self.existing_recipes, f, indent=2)
        except Exception as e:
            print(f"⚠️  Failed to save recipes.json: {e}")

def main():
    """Main enhanced batch processing function"""
    if len(sys.argv) < 2:
        print("❌ ERROR: No input provided")
        print("\nUsage options:")
        print("1. From dish names text file:")
        print("   python3 enhanced_batch_processor.py cuisines/thai/dish-names.txt [--cuisine=thai] [--images=dir] [--max-per-dish=1]")
        print("\n2. From JSON file:")
        print("   python3 enhanced_batch_processor.py recipes.json [--images=dir]")
        print("\n3. From individual URLs:")
        print("   python3 enhanced_batch_processor.py url1 url2 url3... [--images=dir]")
        print("\nExamples:")
        print("   python3 enhanced_batch_processor.py cuisines/thai/dish-names.txt --cuisine=thai")
        print("   python3 enhanced_batch_processor.py cuisines/mexican/dish-names.txt --cuisine=mexican --images=./mexican-images")
        return
    
    # Parse arguments
    input_file = sys.argv[1]
    cuisine_name = "unknown"
    image_dir = "./batch-generated-images"
    max_per_dish = 1
    
    # Parse optional arguments
    for arg in sys.argv[2:]:
        if arg.startswith('--cuisine='):
            cuisine_name = arg.split('=')[1]
        elif arg.startswith('--images='):
            image_dir = arg.split('=')[1]
        elif arg.startswith('--max-per-dish='):
            max_per_dish = int(arg.split('=')[1])
        elif not arg.startswith('http') and not arg.startswith('--') and os.path.exists(arg):
            image_dir = arg
    
    print("🔧 ENHANCED BATCH RECIPE PROCESSOR")
    print("="*50)
    
    # Initialize processor
    try:
        batch_processor = EnhancedBatchProcessor(log_to_file=True)
        print("✅ Enhanced batch processor initialized")
    except Exception as e:
        print(f"❌ Failed to initialize processor: {e}")
        return
    
    # Determine processing mode
    if input_file.endswith('.txt') and os.path.exists(input_file):
        # Process from dish names text file
        print(f"📂 Processing from dish names file: {input_file}")
        print(f"🍽️  Cuisine: {cuisine_name}")
        print(f"🔢 Max recipes per dish: {max_per_dish}")
        result = batch_processor.process_from_dish_names(input_file, cuisine_name, image_dir, max_per_dish)
        
    elif input_file.endswith('.json') and os.path.exists(input_file):
        # Process from JSON file
        print(f"📂 Processing from JSON file: {input_file}")
        result = batch_processor.process_recipes_from_json(input_file, image_dir)
        
    else:
        # Process from URL arguments
        recipe_urls = []
        for i, arg in enumerate(sys.argv[1:]):
            if arg.startswith('http') and not arg.startswith('--'):
                recipe_urls.append({
                    'name': f'Recipe_{i+1}',
                    'url': arg
                })
        
        if not recipe_urls:
            print("❌ No valid input found - check file path or URLs")
            return
        
        print(f"🌐 Processing {len(recipe_urls)} URLs from arguments")
        result = batch_processor.process_recipe_list(recipe_urls, image_dir)
    
    # Print final summary
    if result.get('success', False):
        print(f"\n🎉 Enhanced batch processing completed!")
        print(f"📊 {result['successful_count']}/{result['total_recipes']} recipes processed successfully")
    else:
        print(f"\n❌ Batch processing failed: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()