# 🚀 Interactive Recipe Ingestion - Usage Examples

## Quick Start

```bash
# Activate environment and run
source venv/bin/activate
python3 interactive_recipe_ingestion.py
```

## Mode Examples

### 1. 🌍 Run All Cuisines
**Use Case:** Process all your cuisine dish files overnight

```
Select mode: 1

📊 Found 12 cuisines with 284 total dishes
⏰ Estimated processing time: ~4.7 hours

Cuisines to process:
  • American: 25 dishes
  • Chinese: 28 dishes  
  • Italian: 18 dishes
  • Thai: 10 dishes
  ...

📋 Processing Options:
1. Process all cuisines
2. Start from specific cuisine
3. Skip specific cuisines

Selection: 1  # Process everything
```

### 2. 🎯 Specific Cuisines
**Use Case:** Test specific cuisines or process favorites

```
Select mode: 2

📋 Available Cuisines:
   1. American         (25 dishes)
   2. Chinese          (28 dishes)
   3. French           (26 dishes)
   4. Italian          (18 dishes)
   5. Thai             (10 dishes)

📝 Enter cuisine numbers: 1,4,5  # American, Italian, Thai
🚀 Processing 3 cuisines (53 total dishes)
```

### 3. 🔗 Single Recipe URL
**Use Case:** Test a specific recipe or add one-off recipes

```
Select mode: 3

Enter recipe URL: https://www.allrecipes.com/recipe/213742/cheesy-chicken-broccoli-casserole/
📸 Images will be saved to: ./generated-recipe-images/single-recipes

✅ Recipe processed successfully!
   Recipe ID: d2k09mo5vf6c73cbrh60
   Recipe Name: Cheesy Chicken Broccoli Casserole
   Ingredients: 12
   Image Generated: True
   Processing Time: 45.2s
```

### 4. 🔍 Search & Scrape
**Use Case:** Discover recipes from search result pages

```
Select mode: 4

Enter search results URL: https://tasty.co/search?q=pasta&sort=popular
How many recipes to extract? 15
📸 Image Directory: ./generated-recipe-images/search/pasta

🕷️ Extracting recipe URLs from search page...
✅ Found 15 recipe URLs
🚀 Processing 15 recipes...
✅ Search & scrape completed: 13/15 recipes successful
```

### 5. 🎲 Multi-Query Search
**Use Case:** Bulk discovery from multiple search terms

```
Select mode: 5

URL Template: https://tasty.co/search?q={query}&sort=popular
Queries: chicken, beef, pasta, dessert, soup
Recipes per query: 8
📸 Images will be organized by query in: ./generated-recipe-images/search/

🎯 Multi-query extraction complete
📊 Processing recipes by query with organized image directories:
   🔍 Processing Query 1/5: 'chicken' (8 recipes)
   📸 Images for 'chicken' → ./generated-recipe-images/search/chicken
✅ Multi-query processing completed: 37/40 recipes successful
```

## Advanced Examples

### Tasty.co Bulk Discovery
```bash
# Template for Tasty with sorting
https://tasty.co/search?q={query}&sort=popular

# Queries for comprehensive coverage
chicken, beef, pork, fish, pasta, rice, soup, salad, dessert, breakfast
```

### AllRecipes Discovery
```bash
# Template for AllRecipes
https://www.allrecipes.com/search/?q={query}

# Health-focused queries
keto, paleo, vegan, gluten-free, low-carb, mediterranean
```

### Food Network Discovery
```bash
# Template for Food Network
https://www.foodnetwork.com/search/{query}-

# Cuisine-focused queries  
italian, mexican, chinese, indian, thai, french, japanese
```

## Session Management

### View Progress
```
Select mode: 6

📊 SESSION SUMMARY
Session Duration: 0:45:23
Processing Modes Used: specific_cuisines, single_url, multi_query
Total Recipes Processed: 67
Successful: 62
Failed: 5
Success Rate: 92.5%
```

### Error Recovery
When recipes fail, the system:
- ✅ Continues processing remaining recipes
- ✅ Logs detailed error information
- ✅ Shows clear failure reasons
- ✅ Maintains session statistics

## Tips & Best Practices

### URL Templates
```bash
# Good templates (with sort/filter)
https://site.com/search?q={query}&sort=popular
https://site.com/search?query={query}&category=dinner

# Avoid templates without query placeholder
https://site.com/recipes  # ❌ No {query}
```

### Query Selection
```bash
# Specific ingredients
chicken breast, salmon, ground beef, tofu

# Cooking methods  
grilled, baked, fried, roasted, braised

# Meal types
breakfast, lunch, dinner, snack, dessert

# Dietary restrictions
vegan, keto, gluten-free, dairy-free
```

### Automatic Image Organization
```bash
# Images are automatically organized by processing mode
./generated-recipe-images/single-recipes/        # Mode 3: Single recipes
./generated-recipe-images/cuisine-images/italian/ # Mode 1&2: Cuisine processing  
./generated-recipe-images/search/chicken/        # Mode 4&5: Search queries
./generated-recipe-images/search/pasta/          # Each query gets its own folder
```

**Benefits:**
- No user input required for image directories
- Consistent organization across all processing modes
- Easy to find images by search term or cuisine
- Prevents accidentally overwriting previous batches

## Troubleshooting

### OpenAI Issues
```
❌ OpenAI API key not found - recipe processing will fail without it
```
**Solution:** Add `OPENAI_API_KEY=your_key` to `local.env`

### Playwright Issues
```
❌ Playwright not installed
```
**Solution:** `pip install playwright && playwright install chromium`

### No URLs Found
```
❌ No recipe URLs found on the search page
```
**Solutions:**
- Try different search terms
- Check if site structure changed
- Use more specific queries
- Try different sort parameters

### Authentication Failures
```
❌ eKitchen authentication failed
```
**Solution:** Check `EKITCHEN_ADMIN_EMAIL` and `EKITCHEN_ADMIN_PASSWORD` in `local.env`

## Performance Expectations

### Single Recipe: ~30-60 seconds
- Recipe scraping: 5-10s
- OpenAI parsing: 10-15s  
- Database operations: 5-10s
- Image generation: 15-20s

### Batch Processing: ~60s per recipe
- URL extraction: 2-5s per URL
- Recipe processing: 45-60s each
- Brief pauses between recipes

### Large Batches (50+ recipes): 45-90 minutes
- Multi-threading for URL extraction
- Sequential recipe processing
- Progress tracking and recovery

## Integration with Existing Workflows

### Use with run_all_cuisines.py
The interactive system **includes** and **enhances** your existing workflow:
- Mode 1 = Enhanced version of `run_all_cuisines.py`
- Additional modes for single recipes and discovery
- Same OpenAI-powered ingredient processing
- Better error handling and user feedback

### Custom Scripts
You can also import components directly:
```python
from src.processing.direct_recipe_processor import DirectRecipeProcessor
from src.discovery.playwright_url_extractor import PlaywrightRecipeExtractor

# Process single recipe
processor = DirectRecipeProcessor()
result = processor.process_recipe_autonomous(url, image_dir)

# Extract URLs from search page
extractor = PlaywrightRecipeExtractor()
urls = extractor.extract_recipe_urls_from_search_page(search_url, 10)
```