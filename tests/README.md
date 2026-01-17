# 🧪 Test Scripts

This folder contains test scripts for validating functionality and debugging issues.

## 📋 Test Scripts

### `test_spoonacular_simple.py`
- **Purpose**: Test Spoonacular API connectivity and basic functionality
- **Use**: `python3 test_spoonacular_simple.py`
- **Tests**: API key validation, ingredient search, nutrition data retrieval

### `test_ingredient_409_fix.py`
- **Purpose**: Test ingredient search/create logic to prevent HTTP 409 conflicts
- **Use**: `python3 test_ingredient_409_fix.py`
- **Tests**: Common ingredients (salt, pepper, etc.) for duplicate creation issues

### `test_spoonacular_enrichment.py`
- **Purpose**: Test the 2-step enrichment process (Spoonacular + OpenAI)
- **Use**: `python3 test_spoonacular_enrichment.py`
- **Tests**: New ingredient creation with full enrichment pipeline

### `test_interactive.py`
- **Purpose**: Test components of the interactive recipe ingestion system
- **Use**: `python3 test_interactive.py`
- **Tests**: Various interactive system components

## 🎯 When to Run Tests

### Before Recipe Processing
- Run Spoonacular tests to ensure API is working
- Verify no 409 conflicts will occur

### After Code Changes
- Run enrichment tests to verify new logic works
- Test ingredient creation pipeline

### Debugging Issues
- Use specific tests to isolate problems
- Validate API connectivity and data quality

## 🔄 Quick Test Commands

```bash
# Test all core functionality
cd tests
python3 test_spoonacular_simple.py
python3 test_ingredient_409_fix.py 
python3 test_spoonacular_enrichment.py

# Quick API connectivity check
python3 test_spoonacular_simple.py
```