#!/usr/bin/env python3
"""
Batch Recipe Processor - Process multiple recipes autonomously
Designed for background automation and scheduled runs
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import List, Dict, Any

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'processing'))

from direct_recipe_processor import DirectRecipeProcessor, RecipeProcessingResult

class BatchRecipeProcessor:
    """Batch processor for multiple recipes"""
    
    def __init__(self, log_to_file: bool = True):
        self.processor = DirectRecipeProcessor(log_to_file=log_to_file)
        self.results = []
        self.start_time = None
    
    def process_recipes_from_json(self, recipes_json_path: str, image_output_dir: str = "./batch-generated-images") -> Dict[str, Any]:
        """
        Process recipes from a JSON file
        
        Args:
            recipes_json_path: Path to JSON file with recipe URLs
            image_output_dir: Directory to save generated images
            
        Returns:
            Dict with batch processing results
        """
        print(f"📂 Loading recipes from: {recipes_json_path}")
        
        # Load recipes from JSON
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
    
    def process_recipe_list(self, recipe_urls: List[Dict[str, str]], image_output_dir: str = "./batch-generated-images") -> Dict[str, Any]:
        """
        Process a list of recipe URLs
        
        Args:
            recipe_urls: List of dicts with 'name' and 'url' keys
            image_output_dir: Directory to save generated images
            
        Returns:
            Dict with batch processing results
        """
        self.start_time = time.time()
        self.results = []
        
        print("🚀 STARTING BATCH RECIPE PROCESSING")
        print("="*80)
        print(f"📊 Total Recipes: {len(recipe_urls)}")
        print(f"🖼️  Image Directory: {image_output_dir}")
        print(f"🕒 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        successful_count = 0
        failed_count = 0
        
        for i, recipe_info in enumerate(recipe_urls, 1):
            recipe_name = recipe_info['name']
            recipe_url = recipe_info['url']
            
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
            if i < len(recipe_urls):
                print("⏳ Pausing 5 seconds before next recipe...")
                time.sleep(5)
        
        # Generate final report
        total_time = time.time() - self.start_time
        
        print("\n" + "="*80)
        print("🎉 BATCH PROCESSING COMPLETE!")
        print("="*80)
        print(f"📊 Final Results:")
        print(f"   Total Recipes: {len(recipe_urls)}")
        print(f"   ✅ Successful: {successful_count}")
        print(f"   ❌ Failed: {failed_count}")
        print(f"   📈 Success Rate: {(successful_count / len(recipe_urls) * 100):.1f}%")
        print(f"   ⏱️  Total Time: {total_time:.1f} seconds")
        print(f"   ⏱️  Avg Time per Recipe: {(total_time / len(recipe_urls)):.1f} seconds")
        print("="*80)
        
        # Save detailed report
        self._save_batch_report(image_output_dir, total_time)
        
        return {
            "success": True,
            "total_recipes": len(recipe_urls),
            "successful_count": successful_count,
            "failed_count": failed_count,
            "success_rate": successful_count / len(recipe_urls) * 100,
            "total_time_seconds": total_time,
            "results": self.results
        }
    
    def _save_batch_report(self, output_dir: str, total_time: float):
        """Save detailed batch processing report"""
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = os.path.join(output_dir, f'batch_report_{timestamp}.json')
        
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

def main():
    """Main batch processing function"""
    if len(sys.argv) < 2:
        print("❌ ERROR: No recipes file provided")
        print("\nUsage options:")
        print("1. From JSON file:")
        print("   python3 batch_recipe_processor.py recipes.json [image_dir]")
        print("\n2. From individual URLs:")
        print("   python3 batch_recipe_processor.py url1 url2 url3... [--images=dir]")
        print("\nJSON file format:")
        print('   {"Recipe Name": {"url": "https://..."}, ...}')
        print('   or ["url1", "url2", "url3"]')
        return
    
    # Parse arguments
    image_dir = "./batch-generated-images"
    recipes_input = sys.argv[1]
    
    # Check for image directory argument
    for arg in sys.argv[2:]:
        if arg.startswith('--images='):
            image_dir = arg.split('=')[1]
        elif not arg.startswith('http') and os.path.exists(arg):
            image_dir = arg
    
    print("🔧 BATCH RECIPE PROCESSOR")
    print("="*50)
    
    # Initialize processor
    try:
        batch_processor = BatchRecipeProcessor(log_to_file=True)
        print("✅ Batch processor initialized")
    except Exception as e:
        print(f"❌ Failed to initialize batch processor: {e}")
        return
    
    # Process recipes
    if recipes_input.endswith('.json') and os.path.exists(recipes_input):
        # Process from JSON file
        print(f"📂 Processing from JSON file: {recipes_input}")
        result = batch_processor.process_recipes_from_json(recipes_input, image_dir)
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
            print("❌ No valid recipe URLs found in arguments")
            return
        
        print(f"🌐 Processing {len(recipe_urls)} URLs from arguments")
        result = batch_processor.process_recipe_list(recipe_urls, image_dir)
    
    # Print final summary
    if result.get('success', False):
        print(f"\n🎉 Batch processing completed!")
        print(f"📊 {result['successful_count']}/{result['total_recipes']} recipes processed successfully")
    else:
        print(f"\n❌ Batch processing failed: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()