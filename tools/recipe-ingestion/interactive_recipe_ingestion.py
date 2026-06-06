#!/usr/bin/env python3
"""
Interactive Recipe Ingestion System
Comprehensive entry point for all recipe ingestion modes with user-friendly interface
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# Repo root on path → use the CURRENT services pipeline, NOT the legacy
# processors. The services DirectRecipeProcessor carries the ingredient
# validation gate + catalog-wide dedup matching; the legacy one bypasses both
# (docs/CATALOG_POLLUTION_HANDOFF.md).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO_ROOT)

from services.recipe_processor import DirectRecipeProcessor
from enhanced_batch_processor import EnhancedBatchProcessor
from playwright_url_extractor import PlaywrightRecipeExtractor  # legacy discovery (via Makefile PYTHONPATH)

class InteractiveRecipeIngestion:
    """Interactive recipe ingestion system with multiple processing modes"""
    
    def __init__(self):
        print("🚀 Interactive Recipe Ingestion System")
        print("="*60)
        
        # Initialize processors
        try:
            self.recipe_processor = DirectRecipeProcessor(log_to_file=True)
            self.batch_processor = EnhancedBatchProcessor(log_to_file=True)
            self.url_extractor = PlaywrightRecipeExtractor()
            print("✅ Recipe processors and URL extractor initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize processors: {e}")
            sys.exit(1)
        
        # Store session info
        self.session_start = datetime.now()
        self.results_summary = {
            'total_recipes_processed': 0,
            'successful_recipes': 0,
            'failed_recipes': 0,
            'processing_modes_used': []
        }
    
    def show_main_menu(self):
        """Display main menu options"""
        print(f"\n{'='*60}")
        print("🍽️  RECIPE INGESTION MODES")
        print(f"{'='*60}")
        print("1. 🌍 Run All Cuisines (Process all dishes.txt files)")
        print("2. 🎯 Specific Cuisine(s) (Choose specific cuisine folders)")
        print("3. 🔗 Single Recipe URL (Process one recipe directly)")
        print("4. 🔍 Search & Scrape (Playwright-powered search scraping)")
        print("5. 🎲 Multi-Query Search (Multiple search terms from URL template)")
        print("6. 📊 View Session Summary")
        print("7. ❌ Exit")
        print(f"{'='*60}")
    
    def get_user_choice(self, prompt: str, valid_choices: List[str]) -> str:
        """Get validated user input"""
        while True:
            choice = input(f"{prompt}: ").strip().lower()
            if choice in valid_choices:
                return choice
            print(f"❌ Invalid choice. Please select from: {', '.join(valid_choices)}")
    
    def mode_run_all_cuisines(self):
        """Mode 1: Run all cuisines processing"""
        print(f"\n🌍 RUN ALL CUISINES MODE")
        print("-" * 40)
        
        # Check if run_all_cuisines.py exists
        script_path = "run_all_cuisines.py"
        if not os.path.exists(script_path):
            print(f"❌ {script_path} not found in current directory")
            return
        
        # Show available cuisines
        cuisines_dir = Path("cuisines")
        if not cuisines_dir.exists():
            print("❌ No cuisines directory found")
            return
        
        cuisines = []
        for cuisine_path in cuisines_dir.iterdir():
            if cuisine_path.is_dir():
                dish_file = cuisine_path / "dish-names.txt"
                if dish_file.exists():
                    with open(dish_file, 'r') as f:
                        dish_count = len([line for line in f if line.strip()])
                    cuisines.append({
                        'name': cuisine_path.name,
                        'dish_count': dish_count
                    })
        
        if not cuisines:
            print("❌ No valid cuisines found (no dish-names.txt files)")
            return
        
        # Display summary
        total_dishes = sum(c['dish_count'] for c in cuisines)
        estimated_time = total_dishes * 60 / 3600  # 60 seconds per recipe, convert to hours
        
        print(f"📊 Found {len(cuisines)} cuisines with {total_dishes} total dishes")
        print(f"⏰ Estimated processing time: ~{estimated_time:.1f} hours")
        print("\nCuisines to process:")
        for cuisine in cuisines:
            print(f"  • {cuisine['name'].title()}: {cuisine['dish_count']} dishes")
        
        # Options for customization
        print(f"\n📋 Processing Options:")
        print("1. Process all cuisines")
        print("2. Start from specific cuisine")
        print("3. Skip specific cuisines")
        print("4. Cancel and return to main menu")
        
        option = self.get_user_choice("Select option", ["1", "2", "3", "4"])
        
        if option == "4":
            return
        
        # Build command
        cmd = [sys.executable, script_path]
        
        if option == "2":
            print(f"\nAvailable cuisines: {', '.join([c['name'] for c in cuisines])}")
            start_cuisine = input("Enter cuisine to start from: ").strip()
            cmd.extend(["--start-with", start_cuisine])
        elif option == "3":
            print(f"\nAvailable cuisines: {', '.join([c['name'] for c in cuisines])}")
            skip_input = input("Enter cuisines to skip (comma-separated): ").strip()
            cmd.extend(["--skip", skip_input])
        
        # Confirm and execute
        print(f"\n🚀 Ready to execute: {' '.join(cmd)}")
        confirm = self.get_user_choice("Proceed? (y/n)", ["y", "yes", "n", "no"])
        
        if confirm in ["y", "yes"]:
            print(f"\n🌙 Starting overnight processing...")
            self.results_summary['processing_modes_used'].append('all_cuisines')
            
            try:
                result = subprocess.run(cmd, text=True)
                if result.returncode == 0:
                    print("✅ All cuisines processing completed successfully")
                else:
                    print(f"❌ Processing failed with return code: {result.returncode}")
            except KeyboardInterrupt:
                print(f"\n⚠️ Processing interrupted by user")
            except Exception as e:
                print(f"❌ Error running all cuisines: {e}")
    
    def mode_specific_cuisines(self):
        """Mode 2: Process specific cuisines"""
        print(f"\n🎯 SPECIFIC CUISINE(S) MODE")
        print("-" * 40)
        
        # Find available cuisines
        cuisines_dir = Path("cuisines")
        if not cuisines_dir.exists():
            print("❌ No cuisines directory found")
            return
        
        available_cuisines = []
        for cuisine_path in cuisines_dir.iterdir():
            if cuisine_path.is_dir():
                dish_file = cuisine_path / "dish-names.txt"
                if dish_file.exists():
                    with open(dish_file, 'r') as f:
                        dish_count = len([line for line in f if line.strip()])
                    available_cuisines.append({
                        'name': cuisine_path.name,
                        'path': str(dish_file),
                        'dish_count': dish_count
                    })
        
        if not available_cuisines:
            print("❌ No valid cuisines found")
            return
        
        # Display available cuisines
        print("📋 Available Cuisines:")
        for i, cuisine in enumerate(available_cuisines, 1):
            print(f"  {i:2d}. {cuisine['name'].title():15s} ({cuisine['dish_count']:2d} dishes)")
        
        # Get user selection
        print(f"\n📝 Enter cuisine numbers to process (e.g., 1,3,5 or 'all'):")
        selection = input("Selection: ").strip().lower()
        
        if selection == 'all':
            selected_cuisines = available_cuisines
        else:
            try:
                indices = [int(x.strip()) - 1 for x in selection.split(',')]
                selected_cuisines = [available_cuisines[i] for i in indices if 0 <= i < len(available_cuisines)]
            except (ValueError, IndexError):
                print("❌ Invalid selection format")
                return
        
        if not selected_cuisines:
            print("❌ No valid cuisines selected")
            return
        
        # Process each selected cuisine
        total_dishes = sum(c['dish_count'] for c in selected_cuisines)
        print(f"\n🚀 Processing {len(selected_cuisines)} cuisines ({total_dishes} total dishes)")
        
        confirm = self.get_user_choice("Proceed? (y/n)", ["y", "yes", "n", "no"])
        if confirm not in ["y", "yes"]:
            return
        
        self.results_summary['processing_modes_used'].append('specific_cuisines')
        
        for i, cuisine in enumerate(selected_cuisines, 1):
            print(f"\n{'='*60}")
            print(f"🍽️  PROCESSING CUISINE {i}/{len(selected_cuisines)}: {cuisine['name'].upper()}")
            print(f"{'='*60}")
            
            # Automatically determine image directory
            image_dir = f"./generated-recipe-images/cuisine-images/{cuisine['name']}"
            print(f"📸 Images will be saved to: {image_dir}")
            
            try:
                # Use enhanced batch processor
                result = self.batch_processor.process_from_dish_names(
                    dish_names_file=cuisine['path'],
                    cuisine_name=cuisine['name'],
                    image_output_dir=image_dir
                )
                
                if result.get('success', False):
                    successful = result.get('successful_count', 0)
                    total = result.get('total_recipes', 0)
                    print(f"✅ {cuisine['name'].title()} completed: {successful}/{total} recipes successful")
                    self.results_summary['successful_recipes'] += successful
                    self.results_summary['failed_recipes'] += (total - successful)
                    self.results_summary['total_recipes_processed'] += total
                else:
                    print(f"❌ {cuisine['name'].title()} failed: {result.get('error', 'Unknown error')}")
                    self.results_summary['failed_recipes'] += cuisine['dish_count']
                    
            except Exception as e:
                print(f"❌ Error processing {cuisine['name']}: {e}")
                self.results_summary['failed_recipes'] += cuisine['dish_count']
            
            # Brief pause between cuisines
            if i < len(selected_cuisines):
                print("😴 Pausing 5 seconds before next cuisine...")
                time.sleep(5)
        
        print(f"\n✅ Specific cuisines processing complete!")
    
    def mode_single_recipe_url(self):
        """Mode 3: Process single recipe URL"""
        print(f"\n🔗 SINGLE RECIPE URL MODE")
        print("-" * 40)
        
        url = input("Enter recipe URL: ").strip()
        if not url:
            print("❌ No URL provided")
            return
        
        if not url.startswith('http'):
            print("❌ Invalid URL format")
            return
        
        # Automatically determine image directory
        image_dir = "./generated-recipe-images/single-recipes"
        
        print(f"\n🚀 Processing single recipe from: {url}")
        print(f"📸 Images will be saved to: {image_dir}")
        
        confirm = self.get_user_choice("Proceed? (y/n)", ["y", "yes", "n", "no"])
        if confirm not in ["y", "yes"]:
            return
        
        self.results_summary['processing_modes_used'].append('single_url')
        
        try:
            # Ask if user wants interactive ingredient skipping
            enable_skipping = self.get_user_choice("Enable interactive ingredient skipping? (y/n)", ["y", "yes", "n", "no"])
            allow_skipping = enable_skipping in ["y", "yes"]
            
            if allow_skipping:
                print("🎛️  Interactive ingredient skipping enabled - you'll be prompted for each ingredient")
            
            result = self.recipe_processor.process_recipe_autonomous(url, image_dir, allow_ingredient_skipping=allow_skipping)
            
            if result.success:
                print(f"✅ Recipe processed successfully!")
                print(f"   Recipe ID: {result.recipe_id}")
                print(f"   Recipe Name: {result.recipe_name}")
                print(f"   Ingredients: {result.ingredients_processed}")
                print(f"   Image Generated: {result.image_generated}")
                print(f"   Processing Time: {result.processing_time_seconds:.1f}s")
                
                self.results_summary['successful_recipes'] += 1
            else:
                print(f"❌ Recipe processing failed: {result.error_message}")
                self.results_summary['failed_recipes'] += 1
            
            self.results_summary['total_recipes_processed'] += 1
            
        except Exception as e:
            print(f"❌ Error processing recipe: {e}")
            self.results_summary['failed_recipes'] += 1
    
    def mode_search_and_scrape(self):
        """Mode 4: Search and scrape using Playwright"""
        print(f"\n🔍 SEARCH & SCRAPE MODE")
        print("-" * 40)
        print("This mode uses Playwright to extract recipe URLs from search pages")
        
        # Get search URL
        search_url = input("Enter search results URL: ").strip()
        if not search_url:
            print("❌ No search URL provided")
            return
        
        # Get target number of recipes
        try:
            target_count = int(input("How many recipes to extract? (default: 10): ") or "10")
        except ValueError:
            print("❌ Invalid number")
            return
        
        # Automatically determine image directory based on search URL
        # Extract a search term from the URL for directory naming
        import urllib.parse as urlparse
        from urllib.parse import parse_qs
        
        try:
            parsed_url = urlparse.urlparse(search_url)
            query_params = parse_qs(parsed_url.query)
            
            # Common search parameter names
            search_term = None
            for param_name in ['q', 'query', 'search', 'term']:
                if param_name in query_params:
                    search_term = query_params[param_name][0]
                    break
            
            # Clean the search term for use in directory name
            if search_term:
                search_term = search_term.replace(' ', '-').replace('+', '-').lower()
                search_term = ''.join(c for c in search_term if c.isalnum() or c in '-_')
            else:
                # Fallback to generic name
                search_term = "general-search"
            
        except Exception:
            search_term = "general-search"
        
        image_dir = f"./generated-recipe-images/search/{search_term}"
        
        print(f"\n🚀 Search & Scrape Configuration:")
        print(f"   Search URL: {search_url}")
        print(f"   Target Recipes: {target_count}")
        print(f"   📸 Image Directory: {image_dir}")
        
        confirm = self.get_user_choice("Proceed? (y/n)", ["y", "yes", "n", "no"])
        if confirm not in ["y", "yes"]:
            return
        
        self.results_summary['processing_modes_used'].append('search_scrape')
        
        try:
            # Overfetch URLs so duplicates/scrape-failures have backups available.
            overfetch = max(target_count * 3, target_count + 5)
            print(f"🕷️  Extracting recipe URLs from search page (fetching {overfetch}, target {target_count} successes)...")

            extracted_urls = self.url_extractor.extract_recipe_urls_from_search_page(search_url, overfetch)

            if not extracted_urls:
                print("❌ No recipe URLs found on the search page")
                return

            print(f"✅ Found {len(extracted_urls)} recipe URLs")

            # Process URLs, stopping once we hit target_count successes
            recipe_list = [{"name": f"Recipe_{i+1}", "url": url} for i, url in enumerate(extracted_urls)]
            result = self.batch_processor.process_recipe_list(
                recipe_list,
                image_dir,
                target_success_count=target_count,
            )

            if result.get('success', False):
                successful = result.get('successful_count', 0)
                skipped = result.get('skipped_count', 0)
                failed = result.get('failed_count', 0)
                attempted = result.get('attempted_count', successful + skipped + failed)
                print(f"✅ Search & scrape completed: {successful} successful, {skipped} skipped, {failed} failed (attempted {attempted}/{len(extracted_urls)})")
                self.results_summary['successful_recipes'] += successful
                self.results_summary['failed_recipes'] += failed
                self.results_summary['total_recipes_processed'] += attempted
            else:
                print(f"❌ Search & scrape failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Error in search & scrape: {e}")
            print("💡 Make sure Playwright is installed: playwright install")
    
    def mode_multi_query_search(self):
        """Mode 5: Multi-query search from URL template"""
        print(f"\n🎲 MULTI-QUERY SEARCH MODE")
        print("-" * 40)
        print("Process multiple search queries using a URL template")
        
        # Get URL template
        print("Enter URL template with {query} placeholder:")
        print("Example: https://tasty.co/search?q={query}&sort=popular")
        url_template = input("URL Template: ").strip()
        
        if not url_template or "{query}" not in url_template:
            print("❌ Invalid URL template. Must contain {query} placeholder")
            return
        
        # Get search queries
        print(f"\nEnter search queries (comma-separated):")
        print("Example: chicken, beef, avocado, pasta")
        queries_input = input("Queries: ").strip()
        
        if not queries_input:
            print("❌ No queries provided")
            return
        
        queries = [q.strip() for q in queries_input.split(',') if q.strip()]
        
        # Get target recipes per query
        try:
            per_query = int(input("Recipes per query (default: 5): ") or "5")
        except ValueError:
            print("❌ Invalid number")
            return
        
        # Show configuration
        total_target = len(queries) * per_query
        print(f"\n🚀 Multi-Query Search Configuration:")
        print(f"   URL Template: {url_template}")
        print(f"   Queries: {', '.join(queries)}")
        print(f"   Per Query: {per_query} recipes")
        print(f"   Total Target: {total_target} recipes")
        print(f"   📸 Images will be organized by query in: ./generated-recipe-images/search/")
        
        confirm = self.get_user_choice("Proceed? (y/n)", ["y", "yes", "n", "no"])
        if confirm not in ["y", "yes"]:
            return
        
        self.results_summary['processing_modes_used'].append('multi_query')
        
        try:
            # Overfetch URLs from the search page so we have backups for any
            # that get skipped (duplicate titles already in eKitchen) or fail
            # to scrape. The batch processor stops once `per_query` successes
            # land, so unused backups cost nothing.
            overfetch = max(per_query * 3, per_query + 5)
            print(f"🎲 Starting multi-query URL extraction (fetching {overfetch} per query, target {per_query} successes)...")
            query_results = self.url_extractor.extract_from_multiple_searches(url_template, queries, overfetch)

            print(f"🎯 Multi-query extraction complete")
            print(f"📊 Processing recipes by query with organized image directories:")

            # Process each query's recipes separately to organize images by query
            total_successful = 0
            total_skipped = 0
            total_failed = 0
            total_attempted = 0

            for query_num, (query, urls) in enumerate(query_results.items(), 1):
                if not urls:
                    print(f"   ⚠️  Query '{query}': No URLs found")
                    continue

                print(f"\n   🔍 Processing Query {query_num}/{len(queries)}: '{query}' ({len(urls)} URLs available, target {per_query})")

                # Create query-specific recipe list and image directory
                query_recipes = []
                for j, url in enumerate(urls):
                    query_recipes.append({
                        "name": f"{query.title()}_Recipe_{j+1}",
                        "url": url
                    })

                # Clean query name for directory
                clean_query = query.replace(' ', '-').replace('+', '-').lower()
                clean_query = ''.join(c for c in clean_query if c.isalnum() or c in '-_')
                query_image_dir = f"./generated-recipe-images/search/{clean_query}"

                print(f"   📸 Images for '{query}' → {query_image_dir}")

                # Process this query's recipes, stopping once we hit per_query successes
                try:
                    result = self.batch_processor.process_recipe_list(
                        query_recipes,
                        query_image_dir,
                        target_success_count=per_query,
                    )

                    if result.get('success', False):
                        successful = result.get('successful_count', 0)
                        skipped = result.get('skipped_count', 0)
                        failed = result.get('failed_count', 0)
                        attempted = result.get('attempted_count', successful + skipped + failed)
                        total_successful += successful
                        total_skipped += skipped
                        total_failed += failed
                        total_attempted += attempted
                        print(f"   ✅ Query '{query}': {successful} successful, {skipped} skipped, {failed} failed (attempted {attempted}/{len(urls)})")
                    else:
                        total_failed += len(urls)
                        total_attempted += len(urls)
                        print(f"   ❌ Query '{query}': Processing failed")

                except Exception as e:
                    print(f"   ❌ Query '{query}': Error during processing: {e}")
                    total_failed += len(urls)
                    total_attempted += len(urls)

            # Update summary with totals
            self.results_summary['successful_recipes'] += total_successful
            self.results_summary['failed_recipes'] += total_failed
            self.results_summary['total_recipes_processed'] += total_attempted

            print(f"\n✅ Multi-query processing completed: {total_successful} successful, {total_skipped} skipped, {total_failed} failed")
            
        except Exception as e:
            print(f"❌ Error in multi-query URL extraction: {e}")
            return
    
    
    def show_session_summary(self):
        """Mode 6: Show session summary"""
        print(f"\n📊 SESSION SUMMARY")
        print("-" * 40)
        
        duration = datetime.now() - self.session_start
        
        print(f"Session Duration: {duration}")
        print(f"Processing Modes Used: {', '.join(self.results_summary['processing_modes_used']) or 'None'}")
        print(f"Total Recipes Processed: {self.results_summary['total_recipes_processed']}")
        print(f"Successful: {self.results_summary['successful_recipes']}")
        print(f"Failed: {self.results_summary['failed_recipes']}")
        
        if self.results_summary['total_recipes_processed'] > 0:
            success_rate = (self.results_summary['successful_recipes'] / self.results_summary['total_recipes_processed']) * 100
            print(f"Success Rate: {success_rate:.1f}%")
    
    def run(self):
        """Main interactive loop"""
        print(f"⏰ Session started at: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}")
        
        while True:
            try:
                self.show_main_menu()
                choice = self.get_user_choice("Select mode", ["1", "2", "3", "4", "5", "6", "7"])
                
                if choice == "1":
                    self.mode_run_all_cuisines()
                elif choice == "2":
                    self.mode_specific_cuisines()
                elif choice == "3":
                    self.mode_single_recipe_url()
                elif choice == "4":
                    self.mode_search_and_scrape()
                elif choice == "5":
                    self.mode_multi_query_search()
                elif choice == "6":
                    self.show_session_summary()
                elif choice == "7":
                    print(f"\n👋 Goodbye! Final session summary:")
                    self.show_session_summary()
                    break
                
                # Brief pause before returning to menu
                if choice != "7":
                    input(f"\n⏸️  Press Enter to return to main menu...")
                    
            except KeyboardInterrupt:
                print(f"\n\n⚠️  Session interrupted by user")
                self.show_session_summary()
                break
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
                input(f"⏸️  Press Enter to continue...")

def main():
    """Entry point"""
    try:
        ingestion_system = InteractiveRecipeIngestion()
        ingestion_system.run()
    except Exception as e:
        print(f"❌ Failed to start interactive system: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()