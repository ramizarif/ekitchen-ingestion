# Recipe Ingestion Visual Flow Diagram

## High-Level System Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Input    │    │   Processing    │    │    Output       │
│                 │    │                 │    │                 │
│ • Recipe URLs   │───▶│ AI Enhancement │───▶│ Enriched Recipe │
│ • Search Queries│    │ Data Enrichment │    │ in Database     │
│ • Cuisine Lists │    │ Image Generation│    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Detailed Process Flow

```
🌐 RECIPE URL INPUT
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INTERACTIVE ENTRY POINT                     │
│  📱 interactive_recipe_ingestion.py                           │
│                                                               │
│  User Modes:                                                  │
│  • Single URL Processing                                      │
│  • Search & Scrape (Playwright)                             │
│  • Multi-Query Discovery                                     │
│  • Batch Cuisine Processing                                  │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 RECIPE SCRAPING & EXTRACTION                   │
│  🤖 DirectRecipeProcessor.scrape_recipe_from_url()            │
│                                                               │
│  External Tool: recipe-scrapers library                      │
│  • Supports 300+ recipe websites                             │
│  • Extracts: title, ingredients, instructions, timing        │
│  • Handles complex HTML/JavaScript                           │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AI RECIPE ENHANCEMENT                        │
│  🧠 DirectRecipeProcessor.enhance_recipe_with_ai()            │
│                                                               │
│  OpenAI GPT-4o Usage #1: Recipe Categorization               │
│  ┌───────────────────────────────────────────────────────┐   │
│  │ Input: Recipe data (title, ingredients, instructions)│   │
│  │ Output: Cuisine, difficulty, meal type, dietary tags │   │
│  │ Purpose: Intelligent recipe classification           │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 INGREDIENT PROCESSING PIPELINE                 │
│  🥕 DirectIngredientProcessor.process_recipe_ingredients()     │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 1: INGREDIENT STANDARDIZATION                │
│  🔧 standardize_ingredient_with_ai()                          │
│                                                               │
│  OpenAI GPT-4o Usage #2: Ingredient Name Cleaning            │
│  ┌───────────────────────────────────────────────────────┐   │
│  │ Input: "2 cups all-purpose flour"                    │   │
│  │ Output: standardized: "flour"                        │   │
│  │         reference: "all-purpose flour"               │   │
│  │ Purpose: Clean names while preserving context        │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 2: EXISTING INGREDIENT SEARCH                │
│  🔍 search_ekitchen_ingredient()                              │
│                                                               │
│  eKitchen API Call:                                           │
│  GET /global-ingredients/search?q={ingredient_name}           │
│                                                               │
│  Purpose: Avoid duplicate ingredients in database             │
│  Result: Use existing ID or mark for creation                 │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│             STEP 3: SPOONACULAR ENRICHMENT                     │
│  🌶️ search_spoonacular_ingredient_enhanced()                  │
│                                                               │
│  Spoonacular API Calls:                                      │
│  1. Search: /food/ingredients/search                          │
│  2. Details: /food/ingredients/{id}/information               │
│                                                               │
│  Data Retrieved:                                              │
│  • Calories, protein, fat, carbs per 100g                    │
│  • Food consistency (solid/liquid)                           │
│  • Possible cooking units                                     │
│  • Ingredient metadata                                        │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 4: AI INGREDIENT CATEGORIZATION              │
│  🏷️ categorize_ingredient_with_ai()                           │
│                                                               │
│  OpenAI GPT-4o Usage #3: Ingredient Classification           │
│  ┌───────────────────────────────────────────────────────┐   │
│  │ Input: Ingredient name                                │   │
│  │ Output: proteins|dairy|vegetables|fruits|grains|     │   │
│  │         spices|condiments|beverages|other            │   │
│  │ Purpose: More accurate than keyword matching         │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                               │
│  Fallback: Keyword-based categorization if AI unavailable    │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│               STEP 5: AI COST ESTIMATION                       │
│  💰 estimate_ingredient_cost_with_ai()                        │
│                                                               │
│  OpenAI GPT-4o Usage #4: Grocery Cost Analysis               │
│  ┌───────────────────────────────────────────────────────┐   │
│  │ Input: Ingredient name + available units             │   │
│  │ Output: {                                             │   │
│  │   cost_per_unit: 0.12,                              │   │
│  │   cost_unit: "tablespoon",                          │   │
│  │   purchase_unit: "bottle",                          │   │
│  │   purchase_quantity: 32,                            │   │
│  │   min_purchase_threshold: 8                         │   │
│  │ }                                                    │   │
│  │ Purpose: Realistic grocery pricing for meal planning │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│               STEP 6: UNIT CONVERSION MAPPING                  │
│  🔄 get_unit_conversions()                                    │
│                                                               │
│  Spoonacular Conversion API:                                 │
│  /recipes/convert                                             │
│                                                               │
│  Generated Conversions:                                       │
│  • 1 cup = 16 tablespoons                                    │
│  • 1 tablespoon = 3 teaspoons                                │
│  • 1 ounce = 2 tablespoons                                   │
│                                                               │
│  Purpose: Enable recipe scaling and cost calculations         │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 7: ENHANCED INGREDIENT CREATION              │
│  🏗️ create_ekitchen_ingredient()                              │
│                                                               │
│  eKitchen API Call:                                           │
│  POST /global-ingredients                                     │
│                                                               │
│  Data Stored:                                                 │
│  • Basic info: name, category, consistency                    │
│  • Nutrition: calories, protein, fat, carbs, sugar           │
│  • Cost data: estimated_cost_value, estimated_cost_unit      │
│  • Purchase info: JSON with purchase details                 │
│  • Unit conversions: JSON with conversion factors            │
│  • Enrichment status: needs_enrichment = false               │
│                                                               │
│  Status: 🌟 ENRICHED or 🔄 BASIC (if enrichment failed)     │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    IMAGE GENERATION                            │
│  🎨 generate_recipe_image()                                   │
│                                                               │
│  OpenAI DALL-E 3 Usage #5: Recipe Image Creation             │
│  ┌───────────────────────────────────────────────────────┐   │
│  │ Input: Recipe name + description                      │   │
│  │ Prompt: "Professional food photography of {recipe}:  │   │
│  │         {description}. High-end restaurant           │   │
│  │         presentation, natural lighting, appetizing"  │   │
│  │ Output: High-quality 1024x1024 recipe image          │   │
│  │ Purpose: Professional imagery for user experience    │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                               │
│  Image Processing:                                            │
│  • Download and save generated image                          │
│  • Create multiple sizes for different uses                   │
│  • Organize in structured directory                           │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 RECIPE ASSEMBLY & STORAGE                      │
│  📋 create_ekitchen_recipe()                                  │
│                                                               │
│  eKitchen API Call:                                           │
│  POST /global-recipes                                         │
│                                                               │
│  Final Recipe Data:                                           │
│  ┌───────────────────────────────────────────────────────┐   │
│  │ • Recipe metadata (name, description, timing)        │   │
│  │ • Enriched ingredient list with:                     │   │
│  │   - Standardized names                               │   │
│  │   - Quantities and units                             │   │
│  │   - Cost estimates                                   │   │
│  │   - Nutrition data                                   │   │
│  │ • Structured cooking instructions                    │   │
│  │ • AI-generated images                                │   │
│  │ • Total nutrition per serving                        │   │
│  │ • Cost breakdown for meal planning                   │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ✅ PROCESSING COMPLETE                      │
│                                                               │
│  Recipe stored in eKitchen database with:                     │
│  • Fully enriched ingredients                                 │
│  • Professional imagery                                        │
│  • Nutrition information                                       │
│  • Cost estimates                                             │
│  • AI-enhanced categorization                                 │
│                                                               │
│  Ready for:                                                   │
│  • User recipe browsing                                       │
│  • Meal planning with costs                                   │
│  • Nutritional tracking                                       │
│  • Recipe scaling and modifications                           │
└─────────────────────────────────────────────────────────────────┘
```

## API Usage Summary

### OpenAI API Calls (Per Recipe)
```
┌─────────────────────────────────────────────────────────┐
│ Call #1: Recipe Categorization (GPT-4o)                │
│ ├─ Input: Recipe title + ingredient list               │
│ ├─ Tokens: ~100 output                                 │
│ └─ Purpose: Cuisine, difficulty, meal type             │
│                                                         │
│ Call #2-N: Ingredient Standardization (GPT-4o)        │
│ ├─ Input: Raw ingredient text per ingredient           │
│ ├─ Tokens: ~100 output per ingredient                  │
│ └─ Purpose: Clean names + reference formats            │
│                                                         │
│ Call #2-N: Ingredient Categorization (GPT-4o)         │
│ ├─ Input: Ingredient name per new ingredient           │
│ ├─ Tokens: ~20 output per ingredient                   │
│ └─ Purpose: Food category classification               │
│                                                         │
│ Call #2-N: Cost Estimation (GPT-4o)                   │
│ ├─ Input: Ingredient name + units per new ingredient   │
│ ├─ Tokens: ~150 output per ingredient                  │
│ └─ Purpose: Grocery cost + purchase info               │
│                                                         │
│ Call #Final: Image Generation (DALL-E 3)              │
│ ├─ Input: Recipe name + description                    │
│ ├─ Output: 1024x1024 HD image                         │
│ └─ Purpose: Professional recipe photography            │
└─────────────────────────────────────────────────────────┘

Total OpenAI calls per recipe: 1 + (3 × new_ingredients) + 1
```

### External API Flow
```
Recipe URL → recipe-scrapers → Raw Recipe Data
                                     │
                                     ▼
Raw Ingredients → OpenAI → Standardized Names
                                     │
                                     ▼
Standardized Names → eKitchen API → Check Existing
                                     │
                                     ▼
New Ingredients → Spoonacular API → Nutrition Data
                                     │
                                     ▼
Ingredient Names → OpenAI → Categories + Costs
                                     │
                                     ▼
All Data → eKitchen API → Stored Ingredients
                                     │
                                     ▼
Recipe Description → OpenAI DALL-E → Generated Image
                                     │
                                     ▼
Complete Recipe Data → eKitchen API → Stored Recipe
```

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────┐
│                  ERROR SCENARIOS                        │
│                                                         │
│  🌐 Scraping Fails                                     │
│  ├─ Fallback: Manual parsing                           │
│  └─ User notification + skip option                    │
│                                                         │
│  🧠 OpenAI Unavailable                                 │
│  ├─ Recipe categorization: Use defaults                │
│  ├─ Ingredient standardization: ABORT (required)       │
│  ├─ Ingredient categorization: Keyword fallback        │
│  ├─ Cost estimation: Skip, set needs_enrichment=true   │
│  └─ Image generation: Use source image/placeholder     │
│                                                         │
│  🌶️ Spoonacular Unavailable                            │
│  ├─ Skip nutrition data                                 │
│  ├─ Set needs_enrichment=true                          │
│  └─ Create basic ingredient entry                      │
│                                                         │
│  🏪 eKitchen API Fails                                 │
│  ├─ Retry with exponential backoff                     │
│  ├─ Log error for manual intervention                  │
│  └─ Abort processing if critical operations fail       │
└─────────────────────────────────────────────────────────┘
```

This visual flow shows how the system processes recipes from start to finish, highlighting where each external API and AI service is used, and why each step is necessary for creating fully enriched recipe data.