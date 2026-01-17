# 🍽️ Recipe Processing Scripts

This folder contains all scripts for **normal recipe ingestion workflow** - from discovery to database creation.

## 📋 Main Scripts

### `interactive_recipe_ingestion.py` ⭐ **PRIMARY ENTRY POINT**
- **Purpose**: Main interactive system with 5 processing modes
- **Use**: `python3 interactive_recipe_ingestion.py`
- **Features**: 
  - All cuisines processing
  - Specific cuisine selection
  - Single recipe URL processing
  - Search & scrape from URLs
  - Multi-query discovery
  - Automatic image directory organization

### `enhanced_batch_processor.py`
- **Purpose**: High-performance batch processor with OpenAI standardization
- **Use**: `python3 enhanced_batch_processor.py discovered_urls.json`
- **Features**:
  - OpenAI ingredient parsing (NO regex fallback)
  - 2-step enrichment (Spoonacular + OpenAI categorization)
  - DALL-E image generation
  - Comprehensive error handling

### `run_all_cuisines.py`
- **Purpose**: Process all cuisine dish files automatically
- **Use**: `python3 run_all_cuisines.py`
- **Features**:
  - Processes all `cuisines/*/dish-names.txt` files
  - Uses enhanced batch processor
  - Automatic progress tracking

### `simplified_recipe_discovery.py`
- **Purpose**: URL discovery from dish names using Playwright
- **Use**: `python3 simplified_recipe_discovery.py --cuisine thai`
- **Features**:
  - Multi-site recipe URL discovery
  - Playwright-powered search extraction
  - Clean JSON output for batch processor

### `batch_recipe_processor.py` (Legacy)
- **Purpose**: Original batch processor (pre-OpenAI)
- **Status**: Superseded by `enhanced_batch_processor.py`
- **Note**: Kept for reference/fallback

### `demo_single_recipe.py`
- **Purpose**: Simple single-recipe processing demo
- **Use**: `python3 demo_single_recipe.py "recipe_url"`
- **Features**: Quick testing of single recipe processing

## 🔄 Typical Workflows

### Workflow 1: Interactive Processing (Recommended)
```bash
python3 interactive_recipe_ingestion.py
# Select mode based on your needs
```

### Workflow 2: Full Cuisine Processing
```bash
python3 run_all_cuisines.py
# Processes all cuisine files automatically
```

### Workflow 3: Custom Discovery + Processing
```bash
# Step 1: Discover URLs
python3 simplified_recipe_discovery.py --cuisine italian --max-dishes 10

# Step 2: Process discovered recipes
python3 enhanced_batch_processor.py italian_discovered_recipes_*.json
```

## 📁 Key Features

- ✅ **OpenAI Integration**: AI-powered ingredient standardization and recipe analysis
- ✅ **2-Step Enrichment**: Spoonacular nutrition + OpenAI categorization
- ✅ **DALL-E Images**: Automatic hero image generation
- ✅ **No 409 Conflicts**: Proper search-before-create logic
- ✅ **Error Recovery**: Comprehensive error handling and logging
- ✅ **Progress Tracking**: Session summaries and progress monitoring

## 🎯 When to Use Each Script

- **New recipes from scratch**: `interactive_recipe_ingestion.py`
- **Bulk processing all cuisines**: `run_all_cuisines.py`
- **URL discovery only**: `simplified_recipe_discovery.py`
- **Testing single recipes**: `demo_single_recipe.py`
- **Batch processing existing URLs**: `enhanced_batch_processor.py`