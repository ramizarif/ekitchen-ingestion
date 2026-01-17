#!/usr/bin/env python3
"""
Master Script - Process All Cuisines Overnight
Runs autonomous recipe processing for all cuisines sequentially
Perfect for overnight batch processing while you sleep!
"""

import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

class AllCuisinesProcessor:
    def __init__(self):
        self.cuisines_dir = Path("cuisines")
        self.start_time = None
        self.results = {}
        
    def find_all_cuisines(self):
        """Find all cuisines that have dish-names.txt files"""
        cuisines = []
        
        if not self.cuisines_dir.exists():
            print("❌ Cuisines directory not found!")
            return []
        
        for cuisine_path in self.cuisines_dir.iterdir():
            if cuisine_path.is_dir():
                dish_file = cuisine_path / "dish-names.txt"
                if dish_file.exists():
                    # Count dishes in the file
                    with open(dish_file, 'r') as f:
                        dish_count = len([line for line in f if line.strip()])
                    
                    cuisines.append({
                        'name': cuisine_path.name,
                        'path': str(dish_file),
                        'dish_count': dish_count
                    })
        
        # Sort by name for consistent ordering
        cuisines.sort(key=lambda x: x['name'])
        return cuisines
    
    def estimate_processing_time(self, total_dishes: int) -> str:
        """Estimate total processing time based on dish count"""
        # Rough estimate: 60 seconds per recipe (discovery + processing + image generation)
        total_seconds = total_dishes * 60
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        if hours > 0:
            return f"~{hours}h {minutes}m"
        else:
            return f"~{minutes}m"
    
    def process_single_cuisine(self, cuisine_info: dict) -> dict:
        """Process a single cuisine and return results"""
        cuisine_name = cuisine_info['name']
        dish_file_path = cuisine_info['path']
        dish_count = cuisine_info['dish_count']
        
        print(f"\n{'='*80}")
        print(f"🍽️  PROCESSING CUISINE: {cuisine_name.upper()}")
        print(f"📋 Dishes: {dish_count}")
        print(f"📁 File: {dish_file_path}")
        print(f"🕒 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        
        cuisine_start_time = time.time()
        
        try:
            # Build command
            cmd = [
                sys.executable,  # Use same Python interpreter
                "enhanced_batch_processor.py",
                dish_file_path,
                f"--cuisine={cuisine_name}",
                f"--images=./cuisine-images/{cuisine_name}"
            ]
            
            print(f"🚀 Running: {' '.join(cmd)}")
            
            # Run the enhanced batch processor with live output
            print(f"📺 Live output from {cuisine_name} processing:")
            print("-" * 60)
            
            result = subprocess.run(
                cmd,
                text=True,
                timeout=dish_count * 120  # 2 minutes per dish timeout
            )
            
            processing_time = time.time() - cuisine_start_time
            
            print("-" * 60)
            
            if result.returncode == 0:
                print(f"✅ {cuisine_name.title()} completed successfully!")
                print(f"⏱️  Processing time: {processing_time:.1f} seconds")
                
                return {
                    'success': True,
                    'cuisine': cuisine_name,
                    'dish_count': dish_count,
                    'processing_time': processing_time,
                    'output': f"Completed successfully in {processing_time:.1f}s",
                    'error': None
                }
            else:
                print(f"❌ {cuisine_name.title()} failed!")
                print(f"Return code: {result.returncode}")
                
                return {
                    'success': False,
                    'cuisine': cuisine_name,
                    'dish_count': dish_count,
                    'processing_time': processing_time,
                    'output': f"Failed with return code {result.returncode}",
                    'error': f"Process failed with return code {result.returncode}"
                }
                
        except subprocess.TimeoutExpired:
            processing_time = time.time() - cuisine_start_time
            print(f"⏰ {cuisine_name.title()} timed out after {processing_time:.1f} seconds")
            
            return {
                'success': False,
                'cuisine': cuisine_name,
                'dish_count': dish_count,
                'processing_time': processing_time,
                'output': "",
                'error': f"Timeout after {processing_time:.1f} seconds"
            }
            
        except Exception as e:
            processing_time = time.time() - cuisine_start_time
            print(f"💥 {cuisine_name.title()} crashed: {e}")
            
            return {
                'success': False,
                'cuisine': cuisine_name,
                'dish_count': dish_count,
                'processing_time': processing_time,
                'output': "",
                'error': str(e)
            }
    
    def save_master_report(self):
        """Save comprehensive report of all cuisine processing"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = f"master_overnight_report_{timestamp}.json"
        
        import json
        
        total_time = time.time() - self.start_time
        successful_cuisines = [r for r in self.results.values() if r['success']]
        failed_cuisines = [r for r in self.results.values() if not r['success']]
        
        report_data = {
            "master_report": {
                "timestamp": datetime.now().isoformat(),
                "total_cuisines": len(self.results),
                "successful_cuisines": len(successful_cuisines),
                "failed_cuisines": len(failed_cuisines),
                "total_dishes_processed": sum(r['dish_count'] for r in successful_cuisines),
                "total_time_hours": total_time / 3600,
                "avg_time_per_cuisine_minutes": (total_time / len(self.results)) / 60 if self.results else 0
            },
            "individual_results": list(self.results.values())
        }
        
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n📄 Master report saved: {report_path}")
        return report_path
    
    def run_all_cuisines(self, start_with_cuisine: str = None, skip_cuisines: list = None):
        """
        Run processing for all cuisines sequentially
        
        Args:
            start_with_cuisine: Optional cuisine name to start with (skip previous ones)
            skip_cuisines: Optional list of cuisine names to skip
        """
        self.start_time = time.time()
        skip_cuisines = skip_cuisines or []
        
        # Find all cuisines
        cuisines = self.find_all_cuisines()
        
        if not cuisines:
            print("❌ No cuisines found with dish-names.txt files!")
            return
        
        # Filter cuisines if start_with_cuisine specified
        if start_with_cuisine:
            start_index = next((i for i, c in enumerate(cuisines) if c['name'] == start_with_cuisine), 0)
            cuisines = cuisines[start_index:]
            print(f"🎯 Starting from cuisine: {start_with_cuisine}")
        
        # Remove skipped cuisines
        cuisines = [c for c in cuisines if c['name'] not in skip_cuisines]
        if skip_cuisines:
            print(f"⏭️  Skipping cuisines: {', '.join(skip_cuisines)}")
        
        total_dishes = sum(c['dish_count'] for c in cuisines)
        estimated_time = self.estimate_processing_time(total_dishes)
        
        print("🌙 OVERNIGHT AUTONOMOUS RECIPE PROCESSING")
        print("="*60)
        print(f"📊 Total cuisines: {len(cuisines)}")
        print(f"📋 Total dishes: {total_dishes}")
        print(f"⏰ Estimated time: {estimated_time}")
        print(f"🕒 Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        print("\n📋 PROCESSING QUEUE:")
        for i, cuisine in enumerate(cuisines, 1):
            print(f"  {i:2d}. {cuisine['name'].title():15s} ({cuisine['dish_count']:2d} dishes)")
        
        # Confirm before starting
        print(f"\n🚀 Ready to process {len(cuisines)} cuisines overnight!")
        response = input("Continue? (y/N): ").lower().strip()
        if response != 'y':
            print("❌ Cancelled by user")
            return
        
        print(f"\n🌙 Starting overnight processing at {datetime.now().strftime('%H:%M:%S')}...")
        print("💤 Go to sleep! This will run autonomously...")
        
        # Process each cuisine
        for i, cuisine_info in enumerate(cuisines, 1):
            cuisine_name = cuisine_info['name']
            
            print(f"\n⏳ [{i}/{len(cuisines)}] Processing {cuisine_name.title()}...")
            
            # Process the cuisine
            result = self.process_single_cuisine(cuisine_info)
            self.results[cuisine_name] = result
            
            # Show progress
            successful_count = sum(1 for r in self.results.values() if r['success'])
            print(f"📊 Progress: {i}/{len(cuisines)} cuisines completed ({successful_count} successful)")
            
            # Brief pause between cuisines (let the system breathe)
            if i < len(cuisines):
                print("😴 Pausing 10 seconds before next cuisine...")
                time.sleep(10)
        
        # Final report
        total_time = time.time() - self.start_time
        successful_cuisines = [r for r in self.results.values() if r['success']]
        failed_cuisines = [r for r in self.results.values() if not r['success']]
        
        print(f"\n{'='*80}")
        print("🌅 OVERNIGHT PROCESSING COMPLETE!")
        print(f"{'='*80}")
        print(f"⏰ Total time: {total_time/3600:.1f} hours")
        print(f"✅ Successful: {len(successful_cuisines)} cuisines")
        print(f"❌ Failed: {len(failed_cuisines)} cuisines")
        print(f"📋 Total dishes processed: {sum(r['dish_count'] for r in successful_cuisines)}")
        
        if successful_cuisines:
            print(f"\n✅ SUCCESSFUL CUISINES:")
            for result in successful_cuisines:
                print(f"  • {result['cuisine'].title()} ({result['dish_count']} dishes, {result['processing_time']:.1f}s)")
        
        if failed_cuisines:
            print(f"\n❌ FAILED CUISINES:")
            for result in failed_cuisines:
                print(f"  • {result['cuisine'].title()} - {result['error']}")
        
        # Save master report
        report_path = self.save_master_report()
        
        print(f"\n🎉 Autonomous processing complete!")
        print(f"📄 Full report: {report_path}")
        print(f"💤 Time to wake up and check your recipe database!")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Process all cuisines overnight')
    parser.add_argument('--start-with', 
                       help='Start with a specific cuisine (skip previous ones)')
    parser.add_argument('--skip', 
                       help='Comma-separated list of cuisines to skip')
    parser.add_argument('--list', action='store_true',
                       help='List all available cuisines and exit')
    
    args = parser.parse_args()
    
    processor = AllCuisinesProcessor()
    
    if args.list:
        cuisines = processor.find_all_cuisines()
        print("📋 Available cuisines:")
        for cuisine in cuisines:
            print(f"  • {cuisine['name']} ({cuisine['dish_count']} dishes)")
        return
    
    skip_cuisines = args.skip.split(',') if args.skip else []
    
    processor.run_all_cuisines(
        start_with_cuisine=args.start_with,
        skip_cuisines=skip_cuisines
    )

if __name__ == "__main__":
    main()