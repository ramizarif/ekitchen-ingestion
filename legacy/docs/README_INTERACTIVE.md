# 🚀 Interactive Recipe Ingestion System

A comprehensive, user-friendly interface for processing recipes from multiple sources with AI-powered ingredient parsing.

## 🌟 Features

### **5 Processing Modes**

1. **🌍 Run All Cuisines** - Process all `dishes.txt` files automatically
2. **🎯 Specific Cuisines** - Choose which cuisines to process 
3. **🔗 Single Recipe URL** - Process one recipe directly from URL
4. **🔍 Search & Scrape** - Extract recipes from search result pages using Playwright
5. **🎲 Multi-Query Search** - Process multiple search terms from URL templates

### **Key Capabilities**
- ✅ **OpenAI-Powered** ingredient parsing (no more regex failures!)
- ✅ **Playwright Integration** for intelligent URL extraction
- ✅ **DALL-E Image Generation** for recipe hero images
- ✅ **Comprehensive Logging** and session tracking
- ✅ **Error Handling** with clear failure modes
- ✅ **Progress Tracking** and success rate monitoring

## 🛠️ Setup

### Quick Start
```bash
# Run the setup script
./setup_interactive.sh

# Start the interactive system
python3 interactive_recipe_ingestion.py
```

### Manual Setup
```bash
# Install requirements
pip3 install -r requirements-interactive.txt

# Install Playwright browsers
playwright install chromium

# Create local.env with your API keys
# See Configuration section below
```

## ⚙️ Configuration

Create a `local.env` file with:
```env
OPENAI_API_KEY=your_openai_api_key
EKITCHEN_BASE_URL=your_ekitchen_instance_url
EKITCHEN_ADMIN_EMAIL=your_admin_email
EKITCHEN_ADMIN_PASSWORD=your_admin_password
```

## 🎮 Usage Examples

### Mode 1: Run All Cuisines
```
Processes all cuisine folders with dishes.txt files
Options:
- Process all at once
- Start from specific cuisine
- Skip certain cuisines
```

### Mode 2: Specific Cuisines
```
Interactive selection of which cuisines to process:
1. Italian (18 dishes)
2. Thai (10 dishes) 
3. Mexican (25 dishes)

Selection: 1,3  # Process Italian and Mexican
```

### Mode 3: Single Recipe URL
```
Enter recipe URL: https://www.allrecipes.com/recipe/23439/perfect-prime-rib/
📸 Images will be saved to: ./generated-recipe-images/single-recipes
✅ Recipe processed successfully!
   Recipe ID: d2k09mo5vf6c73cbrh60
   Recipe Name: Perfect Prime Rib
   Ingredients: 8
   Image Generated: True
```

### Mode 4: Search & Scrape
```
Enter search results URL: https://tasty.co/search?q=chicken
How many recipes to extract? 10
📸 Image Directory: ./generated-recipe-images/search/chicken
🕷️ Extracting recipe URLs from search page...
✅ Found 10 recipe URLs
🚀 Processing 10 recipes...
```

### Mode 5: Multi-Query Search
```
URL Template: https://tasty.co/search?q={query}&sort=popular
Queries: chicken, beef, avocado, pasta
Recipes per query: 5
📸 Images will be organized by query in: ./generated-recipe-images/search/

🎯 Multi-query extraction complete
📊 Processing recipes by query with organized image directories:
   🔍 Processing Query 1/4: 'chicken' (5 recipes)
   📸 Images for 'chicken' → ./generated-recipe-images/search/chicken
   ✅ Query 'chicken': 5/5 recipes successful
✅ Multi-query processing completed: 18/20 recipes successful
```

## 📊 Session Tracking

The system tracks:
- Total recipes processed
- Success/failure rates  
- Processing modes used
- Session duration
- Detailed error reporting

## 🎭 Playwright Integration

**Smart URL Extraction:**
- Uses heuristics to identify recipe URLs
- Filters out navigation, social media, and ad links
- Supports both MCP smart extraction and fallback methods
- Respects rate limits with built-in delays

**Supported Sites:**
- AllRecipes
- Tasty.co
- Food Network  
- BBC Good Food
- And many more...

## 🤖 AI-Powered Processing

**OpenAI Integration:**
- GPT-4o for ingredient standardization
- Intelligent parsing of quantities, units, and references
- No regex fallbacks - fails cleanly if AI unavailable
- Proper `reference_as` field population for recipe steps

**Example AI Processing:**
```
Input:  "2 cups all-purpose flour, sifted"
Output: standardized_name: "flour"
        reference_as: "all-purpose flour"
```

## 📁 Directory Structure

```
├── interactive_recipe_ingestion.py    # Main interactive script
├── src/
│   ├── processing/                     # Core processing logic
│   └── discovery/                      # Playwright URL extraction
├── cuisines/                          # Cuisine dish files
│   ├── italian/dish-names.txt
│   ├── thai/dish-names.txt
│   └── mexican/dish-names.txt
└── generated-recipe-images/           # Auto-organized image directories
    ├── single-recipes/                # Mode 3: Single recipe images
    ├── cuisine-images/                # Mode 1&2: Cuisine processing
    │   ├── italian/
    │   ├── thai/
    │   └── mexican/
    └── search/                        # Mode 4&5: Search-based processing
        ├── chicken/
        ├── pasta/
        └── general-search/
```

## ❌ Error Handling

**OpenAI Requirements:**
- System fails cleanly if OpenAI API unavailable
- No degraded regex fallback to ensure data quality
- Clear error messages guide troubleshooting

**Playwright Issues:**
- Automatic browser installation check
- Fallback extraction methods
- Timeout handling for slow pages

## 🔍 Troubleshooting

**OpenAI Failures:**
```
❌ OpenAI API key not found - recipe processing will fail without it
```
→ Add `OPENAI_API_KEY` to `local.env`

**Playwright Issues:**
```
❌ Playwright not installed. Run: pip install playwright && playwright install
```
→ Run the setup script or install manually

**No URLs Found:**
```
❌ No recipe URLs found on the search page
```
→ Try different search terms or check if site structure changed

## 🚀 Advanced Usage

**Custom URL Templates:**
```
https://site.com/search?q={query}&category=dinner
https://site.com/recipes?search={query}&sort=rating
https://site.com/find/{query}
```

**Batch Processing:**
- Automatically handles rate limiting
- Saves progress between recipes
- Comprehensive session summaries
- Error recovery and continuation

## 📈 Performance

**Typical Processing Times:**
- Single recipe: 30-60 seconds
- 10 recipes: 8-12 minutes  
- Full cuisine (20 recipes): 15-25 minutes
- Multi-query (50 recipes): 45-60 minutes

**Factors Affecting Speed:**
- OpenAI API response time
- Recipe complexity (ingredient count)
- Image generation time
- Website response speed