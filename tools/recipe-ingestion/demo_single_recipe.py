#!/usr/bin/env python3
"""
Demo: Process a single recipe to test the OpenAI ingredient parsing
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'processing'))

from direct_recipe_processor import DirectRecipeProcessor

def demo_single_recipe():
    """Demo processing a single recipe with OpenAI parsing"""
    print("🧪 DEMO: Single Recipe Processing with OpenAI")
    print("="*60)
    
    # Initialize processor
    try:
        processor = DirectRecipeProcessor(log_to_file=True)
        print("✅ Processor initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize processor: {e}")
        return
    
    # Test recipe URL
    test_url = "https://www.allrecipes.com/recipe/213742/cheesy-chicken-broccoli-casserole/"
    image_dir = "./demo-images"
    
    print(f"\n🔗 Processing recipe: {test_url}")
    print(f"🖼️  Images will be saved to: {image_dir}")
    
    # Create image directory
    os.makedirs(image_dir, exist_ok=True)
    
    start_time = datetime.now()
    
    try:
        print(f"\n🚀 Starting recipe processing...")
        result = processor.process_recipe_autonomous(test_url, image_dir)
        
        end_time = datetime.now()
        processing_time = end_time - start_time
        
        print(f"\n📊 PROCESSING RESULTS")
        print("-" * 40)
        print(f"Success: {result.success}")
        print(f"Processing Time: {processing_time.total_seconds():.1f} seconds")
        
        if result.success:
            print(f"✅ Recipe processed successfully!")
            print(f"   Recipe ID: {result.recipe_id}")
            print(f"   Recipe Name: {result.recipe_name}")
            print(f"   Ingredients Processed: {result.ingredients_processed}")
            print(f"   Image Generated: {result.image_generated}")
            print(f"\n🎉 Demo completed successfully!")
            print(f"📸 Check {image_dir} for generated images")
        else:
            print(f"❌ Recipe processing failed")
            print(f"   Error: {result.error_message}")
            
    except Exception as e:
        print(f"❌ Demo failed with exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("⚠️  This will process a real recipe and create database entries")
    response = input("Continue? (y/N): ").strip().lower()
    
    if response in ['y', 'yes']:
        demo_single_recipe()
    else:
        print("Demo cancelled")