# Recipe Ingestion Orchestration Guide - Cuisine-Based Approach

## Mission Objective
**Input**: Cuisine-specific agent processes all recipes from its assigned `cuisines/{cuisine}/recipes.json` file
**Output**: All recipes from the JSON file fully processed and added to the eKitchen database with complete ingredient enrichment

**CRITICAL FIRST STEP**: Always start by reading the recipes.json file to get the recipe URLs, then use those URLs with the recipe discovery MCP tool

## New Architecture Overview

### Directory Structure
```
cuisines/
├── italian/
│   ├── dish-names.txt          # Source dish names for discovery
│   ├── recipes.json            # Discovered recipe URLs and metadata
│   ├── notes.txt              # Successful image URL patterns (auto-generated)
│   └── processing-log.txt     # Agent processing progress
├── thai/
│   ├── dish-names.txt
│   ├── recipes.json
│   └── notes.txt
├── mexican/
│   ├── dish-names.txt
│   └── recipes.json
└── recipe-images/
    ├── italian/               # Downloaded recipe images
    ├── thai/
    └── mexican/
```

### Agent Assignment
- **Single Cuisine Agent**: One agent per cuisine (e.g., "Italian Cuisine Agent")
- **No Multi-Agent Orchestration**: Each agent works independently on their cuisine
- **Pre-Discovered URLs**: Agents use existing recipes.json files instead of discovery

## Core Requirements
1. **Process All Recipes**: Complete every recipe in the assigned recipes.json file
2. **Full Database Integration**: Each recipe fully processed into eKitchen with all ingredients
3. **Image Acquisition**: Download and associate recipe images using Playwright
4. **Resilient Processing**: If a recipe fails, log it and continue with the next one
5. **Complete Enrichment**: All ingredients either enriched with Spoonacular or flagged for manual enrichment

## Available MCP Tools

### Recipe Scraping
- `mcp__recipe-discovery__scrape_single_recipe` - Extract detailed recipe data from URL

### eKitchen Database
- `mcp__ekitchen__search_global_ingredients` - Search existing ingredients
- `mcp__ekitchen__create_global_ingredient` - Add new ingredient to database
- `mcp__ekitchen__create_global_recipe` - Add complete recipe to database
- `mcp__ekitchen__upload_recipe_official_image` - Upload recipe image

### Spoonacular Enrichment
- `mcp__spoonacular__search_ingredient` - Search for ingredient data
- `mcp__spoonacular__get_ingredient` - Get detailed nutrition data (per 100g)

### Database Queries
- `mcp__postgres__query` - Execute SQL for similarity searches and data validation

## Step-by-Step Processing Flow

### Phase 1: Recipe Data Extraction

#### Step 1: Load Assigned Recipes
```
Input: cuisines/{cuisine}/recipes.json

Expected Structure:
{
  "Recipe Name": {
    "url": "https://example.com/recipe/123",
    "image_path": "recipe-images/{cuisine}/recipe-name.jpg",
    "search_query": "Recipe Name recipe food photo"
  }
}

Processing Strategy:
- Load all recipes from JSON file
- Process each recipe sequentially
- Track progress in processing-log.txt
- Skip recipes that already exist in eKitchen database
```

#### Step 2: Scrape Recipe Details AND Process Ingredients (Enhanced Single-Step Workflow)
```
🔥 NEW ENHANCED WORKFLOW: Use the single-step recipe scraping + ingredient processing tool

IMPORTANT: Extract the recipe URL from the recipes.json file and use it with the ENHANCED recipe discovery MCP that includes ingredient processing

Step-by-step process:
1. Load cuisines/{cuisine}/recipes.json 
2. For each recipe entry, extract the "url" field
3. Use that URL with the ENHANCED recipe scraping tool with ingredient processing enabled

Enhanced Example:
If recipes.json contains:
"Massaman Curry": {
  "url": "https://www.allrecipes.com/recipe/142055/chicken-massaman-curry/"
}

Then call:
Tool: mcp__recipe-discovery__scrape_single_recipe
Parameters:
- url: "https://www.allrecipes.com/recipe/142055/chicken-massaman-curry/"
- process_ingredients: true
- ekitchen_email: "ekitchen_tester_admin_user@example.com"
- ekitchen_password: "{find password in local.env}"

🎯 Enhanced Output Structure:
{
  "success": true,
  "recipe": {
    "title": "Massaman Curry",
    "description": "Rich and creamy Thai curry...",
    "ingredients": ["2 cups coconut milk", "1 lb chicken", "..."],
    "instructions": "Heat oil in pan...",
    "total_time": 45,
    "prep_time": 15,
    "cook_time": 30,
    "yields": "4 servings",
    "image_url": "https://...",
    "author": "Chef Name",
    "cuisine": "Thai",
    "category": "Dinner"
  },
  "ingredient_processing": {
    "processed": true,
    "success": true,
    "total_ingredients": 12,
    "processed_count": 11,
    "success_rate": "91.7%",
    "ingredient_id_map": {                    // 🔑 KEY: Clear ingredient name → ID mapping
      "coconut milk": "d25tul6f1bnhkfr9vb2g",
      "chicken": "d25tvkuf1bnhkfr9vbg0",
      "red curry paste": "d25u3vef1bnhkfr9vch0"
    },
    "formatted_ingredients": [               // 🔑 KEY: Ready for recipe creation
      {
        "ingredient_id": "d25tul6f1bnhkfr9vb2g",
        "quantity": "2",
        "unit": "cups", 
        "reference_as": "coconut milk"
      },
      {
        "ingredient_id": "d25tvkuf1bnhkfr9vbg0",
        "quantity": "1",
        "unit": "lb",
        "reference_as": "chicken"
      }
    ],
    "nutrition_per_serving": {
      "calories": 485.0,
      "protein": 32.1,
      "fat": 28.7,
      "carbohydrates": 15.3,
      "fiber": 0.0,
      "sugar": 8.2
    },
    "ready_for_recipe_creation": true
  }
}

🔑 CRITICAL USAGE INSTRUCTIONS:

1. **Check Processing Success**:
   ```
   if result["ingredient_processing"]["processed"] and result["ingredient_processing"]["success"]:
       // Ingredients were successfully processed - proceed to recipe creation
       ingredient_id_map = result["ingredient_processing"]["ingredient_id_map"]
       formatted_ingredients = result["ingredient_processing"]["formatted_ingredients"]
       nutrition_data = result["ingredient_processing"]["nutrition_per_serving"]
   else:
       // Ingredient processing failed - log error and skip to next recipe
       log_error("Ingredient processing failed for " + recipe_url)
       continue_to_next_recipe()
   ```

2. **Use the Formatted Ingredients Directly**:
   ```
   🚫 DON'T manually process ingredients anymore - they're already done!
   ✅ DO use result["ingredient_processing"]["formatted_ingredients"] directly in recipe creation
   
   This array already contains:
   - Valid ingredient IDs from eKitchen database
   - Proper quantities and units extracted from recipe
   - Correct reference names for display
   ```

3. **Skip Phase 3 Entirely**:
   ```
   ❌ OLD WORKFLOW: 
   Phase 2: Scrape → Phase 3: Process Ingredients → Phase 4: Create Recipe
   
   ✅ NEW WORKFLOW:
   Phase 2: Scrape + Process Ingredients → Phase 4: Create Recipe
   
   The ingredient processing is already complete! Jump directly to recipe creation.
   ```

4. **Use Included Nutrition Data**:
   ```
   Nutrition values are pre-calculated per serving:
   - calories, protein, fat, carbohydrates, fiber, sugar
   - Ready to use directly in mcp__ekitchen__create_global_recipe
   ```

Error Handling:
- If scraping FAILS: Log error in processing-log.txt, continue to next recipe
- If ingredient processing FAILS: Check result["ingredient_processing"]["error"] for details
- If scraping SUCCEEDS but ingredients FAIL: Log warning, decide whether to continue with basic recipe or skip
- If both SUCCEED: Continue directly to Phase 4 (Recipe Creation) - Skip Phase 3!
```

### Phase 2: Image Acquisition and Generation

#### Step 3A: Download Reference Image
```
Use the existing image scraping functionality to get a reference image:

Process:
1. Check if image already exists at recipe.image_path
2. If not exists or invalid:
   - Use Playwright to extract image URLs from recipe.url
   - Score images by quality and relevance
   - Try downloading images in order until one succeeds
   - Log successful image URL pattern to notes.txt

Image Quality Scoring:
- Higher score for larger dimensions (1200px+)
- Higher score for recipe-related keywords in URL
- Higher score for 'hero', 'featured', 'main' indicators
- Lower score for 'thumb', 'small', 'mini' indicators
- Prefer .jpg/.jpeg over .png

Fallback Strategy:
- Try images in score order (highest first)
- If image download fails (404, not an image, too small), try next
- Continue until successful download or all images exhausted
```

#### Step 3B: Generate Professional Food Photography with DALL-E
```
Create a high-quality, professional food photography image using DALL-E MCP:

Tool: mcp__dalle-mcp__generate_image
Parameters:
- model: "dall-e-3"
- quality: "hd"
- size: "1024x1024"
- style: "natural"
- n: 1
- saveDir: {extract_directory_from_recipe.image_path}
- fileName: {extract_filename_without_extension_from_recipe.image_path}
- prompt: {ai_generated_homey_food_prompt}

**Important**: Use the exact image path structure from recipes.json:
- Extract directory and filename from recipe.image_path
- Preserve the original image file extension (could be .jpg, .png, .jpeg, etc.)
- DALL-E will save with its default format, ensure the path matches

**AI Prompt Generation Instructions**:
Analyze the downloaded reference image and create a detailed, homey food photography prompt. The AI should:

1. **Examine the Reference Image**: Look at the composition, lighting, styling, and overall feel of the scraped image
2. **Describe What You See**: Note the plating style, background, garnishes, colors, and mood
3. **Create a Homey Prompt**: Generate a warm, cozy, home-kitchen feel (NOT restaurant professional)

**Homey Style Guidelines**:
- **Atmosphere**: "Cozy home kitchen", "warm family meal", "comfort food at home"
- **Lighting**: "Soft kitchen window light", "warm home lighting", "natural daylight"
- **Background**: "Home kitchen counter", "family dining table", "cozy kitchen setting"
- **Styling**: "Home-cooked presentation", "family-style plating", "rustic home cooking"
- **Mood**: "Inviting", "comforting", "homemade with love", "cozy meal time"

**Prompt Construction Process**:
1. Start with the recipe title and describe it as a homey, comforting dish
2. Describe the visual style based on what you observe in the reference image
3. Mention homey elements like "served in a cozy kitchen", "family-style presentation"
4. Include warm, inviting language about lighting and atmosphere
5. Add specific details about garnishes, colors, and composition that match the reference
6. End with quality markers but keep the homey feel: "warm, inviting photography"

Example Dynamic Prompt Creation:
"Based on the reference image, create a prompt like: '[Recipe Title], a comforting homemade dish served in a cozy family kitchen. Warm, natural lighting from a kitchen window creates an inviting atmosphere. The dish is presented on [describe plates/bowls from reference], garnished with [specific garnishes observed]. The background shows a lived-in home kitchen with [describe background elements]. Soft, warm tones and a homey, welcoming feel. High quality but intimate home cooking photography, not commercial or restaurant-style.'"

Generated Image Path: {recipe.image_path} (preserving original extension from recipes.json)
```

### Phase 3: Automated Ingredient Processing Pipeline

🚨 **IMPORTANT**: This phase is **OPTIONAL** when using the enhanced `scrape_single_recipe` tool with `process_ingredients=true`.

**When to use this phase:**
- ✅ When using basic `scrape_single_recipe` without ingredient processing  
- ✅ When ingredient processing failed in the enhanced tool and you want to retry manually
- ❌ **Skip this entirely** when using enhanced `scrape_single_recipe` with successful ingredient processing

#### Step 4: Manual Ingredient Processing (Only if Enhanced Tool Not Used)
```
⚠️  LEGACY WORKFLOW: Only use if not using the enhanced scrape_single_recipe tool

If you used the enhanced scrape_single_recipe with process_ingredients=true and it succeeded,
SKIP this entire phase and go directly to Phase 4: Recipe Database Creation.

The enhanced tool already provides:
- ✅ ingredient_id_map: Clear ingredient name → ID mapping  
- ✅ formatted_ingredients: Ready for recipe creation
- ✅ nutrition_per_serving: Pre-calculated nutrition data
- ✅ All ingredients processed and validated

LEGACY Manual Processing (only if enhanced tool failed):

Script: src/processing/ingredient_processor_direct.py
Function: process_recipe_ingredients() (returns tuple)

Code Implementation:
```python
from ingredient_processor_direct import DirectIngredientProcessor

# Initialize processor (loads credentials from local.env automatically)
processor = DirectIngredientProcessor()

# Process ingredients and get BOTH data and clear ID mapping
processed_ingredients, ingredient_id_map = processor.process_recipe_ingredients(
    raw_ingredients=recipe_data['ingredients']
)

# Verify all ingredients have valid IDs before proceeding
if len(ingredient_id_map) < len([i for i in recipe_data['ingredients'] if len(processor.clean_ingredient_name(i)) > 2]):
    print(f"❌ Warning: Only {len(ingredient_id_map)} ingredients have valid IDs")
    print(f"🗺️  Available IDs: {list(ingredient_id_map.keys())}")

# Calculate recipe nutrition using ID map verification
nutrition_data = processor.calculate_recipe_nutrition_from_map(
    raw_ingredients=recipe_data['ingredients'],
    processed_ingredients=processed_ingredients,
    ingredient_id_map=ingredient_id_map,
    num_servings=recipe_data['yields']
)

# Format ingredients using the clear ID map
formatted_ingredients = processor.format_ingredients_for_recipe(
    raw_ingredients=recipe_data['ingredients'],
    ingredient_id_map=ingredient_id_map
)

# Verify formatted ingredients before recipe creation
if len(formatted_ingredients) == 0:
    print("❌ CRITICAL: No valid ingredients for recipe creation - aborting")
    return False

print(f"✅ Recipe ready with {len(formatted_ingredients)} valid ingredient mappings")
```

What the Manual Script Does:
1. **Authenticates with eKitchen** production database using credentials from local.env
2. **Cleans ingredient names** (removes quantities like "1 cup", "3 tbsp")
3. **Searches existing ingredients** in eKitchen database via direct API calls
4. **Enriches missing ingredients** with Spoonacular API (direct calls with full nutrition data)
5. **Creates new ingredients** in eKitchen production database (direct API calls)
6. **Handles failed enrichment** by creating basic ingredients with "Needs Review" tags
7. **Returns complete mapping** with all eKitchen IDs and nutrition data for recipe creation

🔥 **RECOMMENDATION**: Always try the enhanced `scrape_single_recipe` tool first - only fall back to manual processing if it fails.
```

### Phase 4: Recipe Database Creation

#### Step 5: Use Enhanced Tool Output OR Build Recipe Data Manually

🔥 **ENHANCED WORKFLOW** (Recommended):
```
If you used the enhanced scrape_single_recipe with process_ingredients=true:

✅ **Data Already Ready - No Additional Processing Needed!**

The enhanced tool output already contains everything you need:

```python
# Extract the ready-to-use data from enhanced tool response
recipe_data = result["recipe"]
ingredient_processing = result["ingredient_processing"]

# 🔑 KEY: Everything is already processed and ready!
formatted_ingredients = ingredient_processing["formatted_ingredients"]    # Ready for recipe creation
nutrition_data = ingredient_processing["nutrition_per_serving"]          # Ready for recipe creation
ingredient_id_map = ingredient_processing["ingredient_id_map"]           # For verification/debugging

# ✅ Verify processing was successful
if not ingredient_processing["processed"] or not ingredient_processing["success"]:
    print(f"❌ ABORT: Ingredient processing failed - {ingredient_processing.get('error', 'Unknown error')}")
    return False

# ✅ Verify we have ingredients for recipe creation
if len(formatted_ingredients) == 0:
    print("❌ ABORT: No valid ingredients - recipe creation will fail")
    return False

print(f"✅ Recipe ready with {len(formatted_ingredients)} validated ingredients")
print(f"📊 Nutrition calculated: {nutrition_data['calories']} cal, {nutrition_data['protein']}g protein")

# 🎯 Ready to create recipe with guaranteed valid data!
```

**Benefits of Enhanced Tool Output:**
- ✅ **Pre-validated ingredients**: All ingredient IDs guaranteed to exist in eKitchen
- ✅ **Pre-calculated nutrition**: Accurate per-serving nutrition from Spoonacular data
- ✅ **Pre-formatted arrays**: Ready for direct use in recipe creation API
- ✅ **Error-free guarantee**: Eliminates "ingredient doesn't exist" errors completely

🔥 **LEGACY MANUAL WORKFLOW** (Only if enhanced tool not used):

1. Build Recipe Ingredients Array Using ID Map:
```python
# ONLY needed if you didn't use the enhanced scrape_single_recipe tool
# The enhanced tool already provides formatted_ingredients - use those instead!

formatted_ingredients = processor.format_ingredients_for_recipe(
    raw_ingredients=recipe_data['ingredients'],
    ingredient_id_map=ingredient_id_map  # From manual processing in Step 4
)

# CRITICAL: Verify all ingredients have valid IDs before recipe creation
print(f"✅ Recipe ingredients ready: {len(formatted_ingredients)} ingredients with valid IDs")
if len(formatted_ingredients) == 0:
    print("❌ ABORT: No valid ingredients - recipe creation will fail")
    return False
```

2. Calculate Recipe Nutrition (ONLY needed if enhanced tool not used):

**Objective**: Calculate accurate per-serving nutrition values using the ingredient nutrition data from Spoonacular and the actual quantities specified in the recipe.

**Process**:
- For each ingredient in the recipe, extract the quantity (e.g., "2 cups", "3 tablespoons")
- Convert quantities to grams using standard conversion factors:
  - 1 cup = 240g, 1 tbsp = 15g, 1 tsp = 5g, 1 lb = 453g, 1 oz = 28g
- Scale the nutrition data (which is per 100g from Spoonacular) to the actual grams used
- Sum up all ingredients to get total recipe nutrition
- Divide by number of servings for per-serving values

**Key Conversion Factors**:
- Cups to grams: 1 cup = 240g (for liquids/approximate for solids)
- Tablespoons: 1 tbsp = 15g
- Teaspoons: 1 tsp = 5g  
- Pounds: 1 lb = 453.592g
- Ounces: 1 oz = 28.35g

**Handle Fractions**: Convert fractions like "1/2 cup" or "1 1/2 cups" to decimal values

**Output**: Calculate per-serving values for:
- calories_per_serving (rounded to whole number)
- protein_per_serving (rounded to 1 decimal)
- fat_per_serving (rounded to 1 decimal)
- carbohydrates_per_serving (rounded to 1 decimal)
- sugar_per_serving (rounded to 1 decimal)
- fiber_per_serving (set to 0 for now)

3. Rewrite Recipe Instructions for Fun, Light, Cozy Brand Identity:

**Objective**: Transform the scraped recipe instructions to match eKitchen's warm, friendly, and cozy brand identity.

**Brand Guidelines**:
- **Warm & Encouraging**: Use friendly, supportive language that makes cooking feel approachable
- **Cozy Language**: Replace technical terms with warmer alternatives:
  - "combine" → "lovingly mix together"
  - "cook" → "let it simmer with love"
  - "bake" → "pop into your cozy oven"  
  - "place" → "nestle"
  - "pour" → "drizzle"
  - "serve" → "dish up this deliciousness"
- **Add Encouragement**: Include helpful tips and encouraging phrases
- **Sensory Details**: Mention smells, textures, and visual cues ("Your kitchen will smell amazing!")
- **Joyful Tone**: Make cooking feel like a delightful experience, not a chore

**Transformation Examples**:
- Original: "Combine chicken broth and taco seasoning in a bowl."
- Rewritten: "Lovingly mix together the chicken broth and taco seasoning in a bowl. Watch as all the flavors come together beautifully."

- Original: "Cook on Low for 6 to 8 hours."
- Rewritten: "Let it simmer with love on Low for 6 to 8 hours. Your kitchen will smell absolutely amazing as this cooks!"

**Structure**: Convert the rewritten instructions into a steps array format with position numbers for the eKitchen database.

4. Determine Recipe Difficulty:
   If not provided in scraped data, calculate based on:
   
   Easy (1-2 difficulty):
   - ≤5 ingredients
   - ≤30 minutes total time OR slow cooker/one-pot recipes
   - Simple techniques (mix, combine, bake, slow cook)
   - No advanced techniques required
   
   Medium (3-4 difficulty):
   - 6-12 ingredients
   - 30-90 minutes total time
   - Some technique required (sautéing, layering, timing)
   - Multiple cooking steps or equipment
   
   Hard (5 difficulty):
   - >12 ingredients
   - >90 minutes total time
   - Advanced techniques (tempering, reducing, complex timing)
   - Multiple components or specialized equipment
   
   Examples:
   - Slow cooker chicken tacos (3 ingredients, 370min slow cook) = "Easy"
   - Homemade pasta with sauce (8 ingredients, 60min, pasta making) = "Medium"  
   - Beef wellington (15+ ingredients, 3+ hours, pastry work) = "Hard"
```

#### Step 6: Upload Generated DALL-E Image to eKitchen
```
Tool: mcp__ekitchen__upload_recipe_official_image
Parameters:
- recipe_id: {recipe_id_from_step_7}
- file_path: {generated_dalle_image_path}
- image_type: "hero"

**Important Notes**:
- Use the DALL-E generated image path (from Step 3B) not the scraped image
- This step happens AFTER recipe creation in Step 7
- The generated image should have the homey, cozy feel matching eKitchen's brand
- File path should match the exact location where DALL-E saved the image

**Process**:
1. Recipe is created first (Step 7) and returns a recipe_id
2. Use that recipe_id to upload the DALL-E generated hero image
3. The image becomes the official recipe image in the eKitchen database
```

#### Step 7: Add Complete Recipe to eKitchen Database

🔥 **ENHANCED WORKFLOW** (Using enhanced tool output):
```
Tool: mcp__ekitchen__create_global_recipe

Using Enhanced Tool Data:
```python
# Extract data from enhanced scrape_single_recipe response
recipe_data = result["recipe"]
ingredient_processing = result["ingredient_processing"]

# Create recipe with pre-processed data
create_recipe_params = {
    "name": recipe_data["title"],
    "description": recipe_data["description"], 
    "steps": rewritten_cozy_steps_array,     # Rewrite instructions for cozy brand (still needed)
    "prep_time_minutes": recipe_data["prep_time"],
    "cook_time_minutes": recipe_data["cook_time"], 
    "total_time_minutes": recipe_data["total_time"],
    "num_servings": int(recipe_data["yields"].replace(" servings", "")),  # Extract number
    "cuisine": cuisine_name,  # e.g., "Thai", "Italian"
    "inspired_by_url": recipe_data["url"],
    
    # 🔑 CRITICAL: Use pre-calculated nutrition from enhanced tool
    "calories": ingredient_processing["nutrition_per_serving"]["calories"],
    "protein": ingredient_processing["nutrition_per_serving"]["protein"], 
    "fat": ingredient_processing["nutrition_per_serving"]["fat"],
    "carbohydrates": ingredient_processing["nutrition_per_serving"]["carbohydrates"],
    "fiber": ingredient_processing["nutrition_per_serving"]["fiber"],
    "sugar": ingredient_processing["nutrition_per_serving"]["sugar"],
    
    # 🔑 CRITICAL: Use pre-formatted ingredients with guaranteed valid IDs
    "ingredients": ingredient_processing["formatted_ingredients"],
    
    "difficulty": determined_difficulty_level,  # Still need to calculate
    "tag_names": [relevant_tags]  # Still need to determine
}
```

**✅ GUARANTEED SUCCESS**: The enhanced tool provides:
- ✅ **Valid ingredient IDs**: All IDs verified to exist in eKitchen database
- ✅ **Accurate nutrition**: Calculated from real Spoonacular data + recipe quantities  
- ✅ **Proper formatting**: ingredients array ready for API consumption
- ✅ **Error prevention**: Zero "ingredient doesn't exist" errors

🔥 **LEGACY WORKFLOW** (Only if enhanced tool not used):

Tool: mcp__ekitchen__create_global_recipe
Parameters:
- name: {recipe.title}
- description: {recipe.description}
- steps: {rewritten_cozy_steps_array}     # From Step 5 instruction rewriting
- prep_time_minutes: {recipe.prep_time}
- cook_time_minutes: {recipe.cook_time}
- total_time_minutes: {recipe.total_time}
- num_servings: {recipe.yields}
- cuisine: {cuisine_name}
- inspired_by_url: {recipe.url}
- calories: {nutrition_data['calories']}    # From manual processing
- protein: {nutrition_data['protein']}    # From manual processing
- fat: {nutrition_data['fat']}            # From manual processing
- carbohydrates: {nutrition_data['carbohydrates']}  # From manual processing
- fiber: {nutrition_data['fiber']}        # From manual processing  
- sugar: {nutrition_data['sugar']}        # From manual processing
- ingredients: {formatted_ingredients}    # From manual processor.format_ingredients_for_recipe()
- difficulty: {determined_difficulty_level}
- tag_names: [relevant tags]

**Steps Format Requirements** (Both workflows):
```json
[
  {"position": 1, "template": "Get everything ready and set up your cozy cooking space!"},
  {"position": 2, "template": "Heat the oil in a large pan over medium heat. Add onions and cook until softened."},
  {"position": 3, "template": "Add spices and cook for 1 minute until fragrant."}
]
```

Key format requirements:
- Each step MUST have "position" (number) and "template" (string) fields
- Use plain ingredient names in templates (no special formatting needed)
- Position numbers start at 1 and increment sequentially
- The API automatically handles ingredient reference mapping

**Final Verification** (Both workflows):
```python
# Always verify before calling create_global_recipe
if len(formatted_ingredients) == 0:
    print("❌ CRITICAL: No valid ingredients - aborting recipe creation")
    return False

print(f"✅ Creating recipe with {len(formatted_ingredients)} verified ingredients")
# Recipe creation guaranteed to succeed with enhanced tool output
```

Record the returned recipe_id → Continue to Step 6 (image upload)
```

## Processing Strategy

### Single Cuisine Agent Workflow
```
1. Agent starts with assigned cuisine (e.g., "italian")
2. Load cuisines/italian/recipes.json
3. Process each recipe sequentially:
   a. Scrape recipe details from URL
   b. Download/verify recipe image
   c. Process all ingredients (search → enrich → create → relate)
   d. Calculate recipe nutrition
   e. Create recipe record in eKitchen
   f. Upload recipe image
   g. Log success/failure
4. Continue until all recipes processed
5. Generate final completion report
```

### Error Handling and Resilience
- **Recipe scraping fails**: Log error, continue to next recipe
- **Image download fails**: Log warning, continue with recipe (image optional)
- **Ingredient enrichment fails**: Add with basic data, flag for manual enrichment
- **Database insertion fails**: Log error with full context, continue to next recipe
- **Similarity search fails**: Continue without relationships (not critical)

### Progress Tracking
- **Processing Log**: Create `cuisines/{cuisine}/processing-log.txt`
- **Image Pattern Log**: Maintain `cuisines/{cuisine}/notes.txt` for successful image URLs
- **Real-time Updates**: Log every major step completion
- **Final Report**: Summary with success/failure counts

## Agent Instructions Template

```markdown
You are the {Cuisine} Cuisine Processing Agent.

Mission: Process all recipes from cuisines/{cuisine}/recipes.json into the eKitchen database.

Your recipes.json file contains {count} recipes to process.

For each recipe:
1. Scrape details from the URL using mcp__recipe-discovery__scrape_single_recipe
2. Download/verify recipe image exists
3. Process all ingredients through the enrichment pipeline
4. Create complete recipe record in eKitchen database
5. Upload recipe image to eKitchen
6. Log progress

Tools Available:
- Recipe scraping: mcp__recipe-discovery__scrape_single_recipe  
- Ingredient search: mcp__ekitchen__search_global_ingredients
- Ingredient creation: mcp__ekitchen__create_global_ingredient
- Spoonacular search: mcp__spoonacular__search_ingredient
- Spoonacular details: mcp__spoonacular__get_ingredient
- Recipe creation: mcp__ekitchen__create_global_recipe
- Image upload: mcp__ekitchen__upload_recipe_official_image
- Database queries: mcp__postgres__query

Log all progress to: cuisines/{cuisine}/processing-log.txt
Track image patterns in: cuisines/{cuisine}/notes.txt

Begin processing when ready.
```

## Data Flow Summary

```
cuisines/{cuisine}/recipes.json
          ↓
Recipe URL → Scrape Recipe Details → Process Ingredients → Create Recipe
          ↓                              ↓                      ↓
Download Image → Enrich with Spoonacular → Upload Image → Complete
          ↓                              ↓                      ↓
Save to recipe-images/ → Create Relationships → Log Success → Next Recipe
```

## Success Metrics
- **Completion Rate**: 95%+ of recipes successfully processed
- **Enrichment Rate**: 80%+ of ingredients enriched with nutrition data
- **Image Success**: 90%+ of recipes have associated images
- **Database Integrity**: All ingredients and recipes properly linked
- **Processing Efficiency**: <5% recipes abandoned due to unrecoverable errors