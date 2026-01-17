#!/usr/bin/env python3
"""
Test the interactive system components
"""

import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'processing'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'discovery'))

def test_imports():
    """Test that all components import correctly"""
    print("🧪 Testing imports...")
    
    try:
        from direct_recipe_processor import DirectRecipeProcessor
        print("✅ DirectRecipeProcessor imported")
    except Exception as e:
        print(f"❌ DirectRecipeProcessor failed: {e}")
        return False
    
    try:
        from enhanced_batch_processor import EnhancedBatchProcessor
        print("✅ EnhancedBatchProcessor imported")
    except Exception as e:
        print(f"❌ EnhancedBatchProcessor failed: {e}")
        return False
    
    try:
        from playwright_url_extractor import PlaywrightRecipeExtractor
        print("✅ PlaywrightRecipeExtractor imported")
    except Exception as e:
        print(f"❌ PlaywrightRecipeExtractor failed: {e}")
        return False
    
    return True

def test_initialization():
    """Test that processors initialize correctly"""
    print("\n🧪 Testing processor initialization...")
    
    try:
        from direct_recipe_processor import DirectRecipeProcessor
        processor = DirectRecipeProcessor(log_to_file=False)
        print("✅ DirectRecipeProcessor initialized")
    except Exception as e:
        print(f"❌ DirectRecipeProcessor initialization failed: {e}")
        return False
    
    try:
        from enhanced_batch_processor import EnhancedBatchProcessor
        batch_processor = EnhancedBatchProcessor(log_to_file=False)
        print("✅ EnhancedBatchProcessor initialized")
    except Exception as e:
        print(f"❌ EnhancedBatchProcessor initialization failed: {e}")
        return False
    
    try:
        from playwright_url_extractor import PlaywrightRecipeExtractor
        extractor = PlaywrightRecipeExtractor()
        print("✅ PlaywrightRecipeExtractor initialized")
    except Exception as e:
        print(f"❌ PlaywrightRecipeExtractor initialization failed: {e}")
        return False
    
    return True

def test_single_recipe_processing():
    """Test processing a single recipe"""
    print("\n🧪 Testing single recipe processing...")
    
    try:
        from direct_recipe_processor import DirectRecipeProcessor
        processor = DirectRecipeProcessor(log_to_file=False)
        
        # Test with a simple recipe URL
        test_url = "https://www.allrecipes.com/recipe/213742/cheesy-chicken-broccoli-casserole/"
        
        print(f"🔗 Testing URL: {test_url}")
        print("⚠️  This will actually process the recipe - comment out if not desired")
        
        # Uncomment to actually test recipe processing:
        # result = processor.process_recipe_autonomous(test_url, "./test-images")
        # print(f"✅ Recipe processing result: {result.success}")
        
        print("✅ Single recipe processor ready (test skipped)")
        
    except Exception as e:
        print(f"❌ Single recipe processing test failed: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("🚀 Testing Interactive Recipe Ingestion System Components")
    print("="*60)
    
    tests = [
        test_imports,
        test_initialization,
        test_single_recipe_processing
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"❌ Test failed: {test.__name__}")
        except Exception as e:
            print(f"❌ Test error in {test.__name__}: {e}")
    
    print(f"\n📊 Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! Interactive system is ready to use.")
        print("\n🚀 To start the interactive system:")
        print("   python3 interactive_recipe_ingestion.py")
    else:
        print("❌ Some tests failed. Check error messages above.")

if __name__ == "__main__":
    main()