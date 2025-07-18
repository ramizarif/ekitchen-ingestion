# MCP-Powered Recipe Ingestion System Implementation Plan

## Executive Summary

Replace your complex multi-queue pipeline with **4 custom MCP servers** + **2 existing servers** that work through natural language conversations. Total implementation time: **2-3 weeks** vs. 4-6 weeks for the original pipeline.

## Core Architecture

```
You ←→ Claude Desktop ←→ Multiple MCP Servers ←→ eKitchen Database
```

**The Power**: Instead of building complex queue systems, you have conversations like:
- *"Find 100 chicken pasta recipes and enrich them with Spoonacular data"*
- *"Tag all untagged ingredients using our existing tag system"*
- *"Generate ingredient similarity mappings for recipe recommendations"*

## Required MCP Servers

### 1. eKitchen Database MCP Server
**File**: `mcp-servers/ekitchen-db/server.py`

**Core Functions**:
```python
@mcp.tool()
async def process_and_insert_recipes(raw_recipes_json: str) -> dict:
    """AI parses raw recipe data and intelligently inserts into database"""
    # AI handles:
    # - Format standardization from any source
    # - Ingredient extraction with quantities/units
    # - Recipe deduplication against existing data
    # - Mapping to eKitchen schema
    # - Bulk database insertion
    
@mcp.tool()
async def get_ingredients_needing_enrichment() -> list:
    """Get ingredients marked as needing Spoonacular enrichment"""

@mcp.tool()
async def update_ingredient_enrichment(ingredient_id: str, spoonacular_data: dict) -> bool:
    """Update ingredient with Spoonacular nutritional data"""

@mcp.tool()
async def get_tag_system() -> dict:
    """Get all available tags and categories for AI-powered tagging"""

@mcp.tool()
async def assign_ingredient_tags(ingredient_id: str, tag_suggestions: list) -> bool:
    """AI analyzes ingredient and assigns appropriate tags"""

@mcp.tool()
async def assign_recipe_cuisine_tags(recipe_id: str, recipe_data: dict) -> bool:
    """AI analyzes recipe and assigns cuisine/dietary tags"""

@mcp.tool()
async def generate_ingredient_similarities(batch_size: int = 100) -> dict:
    """AI analyzes ingredients and creates similarity mappings"""
```

### 2. Recipe Discovery MCP Server
**File**: `mcp-servers/recipe-discovery/server.py`

**Core Functions**:
```python
@mcp.tool()
async def discover_recipes(keyword: str, target_count: int) -> str:
    """Search multiple sites and return large JSON with raw recipe data"""
    # Multi-site search across:
    # - AllRecipes, Food Network, BBC Good Food
    # - Serious Eats, Food52, Bon Appétit
    # Returns massive JSON (can be 50MB+) with all raw data

@mcp.tool()
async def scrape_recipe_urls(urls: list) -> str:
    """Scrape specific URLs and return raw recipe data"""
    # Uses recipe-scrapers library
    # Handles site-specific extraction
    # Returns raw JSON for AI processing
```

### 3. Spoonacular Integration MCP Server
**File**: `mcp-servers/spoonacular/server.py`

**Core Functions**:
```python
@mcp.tool()
async def enrich_ingredients_batch(ingredient_list: list) -> dict:
    """Batch enrich multiple ingredients with Spoonacular data"""
    # Rate-limited API calls
    # Intelligent name matching
    # Nutritional data retrieval
    # Returns structured enrichment data

@mcp.tool()
async def search_ingredient_alternatives(ingredient_name: str) -> list:
    """Find alternative names for failed ingredient searches"""
    # Helps with ingredients that don't match initially
```

### 5. Existing PostgreSQL MCP Server
**Install**: `npm install -g @modelcontextprotocol/server-postgres`
- Direct SQL queries for complex operations
- Data validation and integrity checks

### 6. Existing Firecrawl MCP Server (Optional)
**Install**: `npm install -g @mendableai/firecrawl-mcp-server`
- Advanced web scraping for problematic sites
- Fallback when recipe-scrapers fails

## Implementation Timeline

### Week 1: Core Foundation (3 MCP Servers)
**Days 1-3**: eKitchen Database MCP Server
```python
# Priority functions for AI-powered processing
- process_and_insert_recipes()
- get_ingredients_needing_enrichment()
- update_ingredient_enrichment()
```

**Days 4-5**: Recipe Discovery MCP Server
```python
# Start with 2-3 major sites
- AllRecipes integration
- Food Network integration  
- Return raw JSON for AI processing
```

**Days 6-7**: Spoonacular MCP Server + Initial Testing
```python
# Rate-limited batch processing
- enrich_ingredients_batch()
- search_ingredient_alternatives()
```

### Week 2: Complete Integration & Enhancement
**Days 1-3**: Advanced Recipe Discovery
```python
# Add more sites and robust error handling
- BBC Good Food
- Serious Eats
- Handle site failures gracefully
```

**Days 4-5**: AI-Powered Tagging & Enhancement
```python
# Leverage AI through eKitchen DB MCP
- assign_ingredient_tags()
- assign_recipe_cuisine_tags()
- generate_ingredient_similarities()
```

**Days 6-7**: End-to-End Testing & Optimization
- Test complete workflows with large datasets
- Optimize for token efficiency
- Performance tuning

## Sample Conversation Workflows

### Complete Recipe Ingestion Pipeline
```
You: "Find 100 Mediterranean chicken recipes and fully process them into my database."

Claude: "I'll discover, process, and enrich Mediterranean chicken recipes for you.

[Uses recipe-discovery MCP]
Searching multiple sites for Mediterranean chicken recipes...
Found 127 recipes from AllRecipes, Food Network, BBC Good Food, and Serious Eats.

[Uses ekitchen-db MCP with AI processing]
Processing raw recipe data with AI standardization...
- Standardized 127 recipes to eKitchen schema
- Extracted 89 unique ingredients with quantities/units  
- Deduplicated against existing recipes (12 were duplicates)
- Inserted 115 new recipes into global_recipes table
- Identified 34 new ingredients needing enrichment
- Assigned Mediterranean cuisine tags automatically

[Uses spoonacular MCP for enrichment]
Enriching 34 new ingredients with nutritional data...
- Successfully enriched 32/34 ingredients
- 2 ingredients need alternative name research ('preserved lemons', 'harissa paste')

[Uses ekitchen-db MCP for intelligent tagging]
AI analyzing ingredients for tag assignment...
- Tagged ingredients: 8 proteins, 12 vegetables, 6 spices, 4 dairy, 4 pantry staples
- Assigned storage location tags (refrigerated, pantry, spice rack)
- Applied dietary restriction tags (gluten-free, dairy-free options identified)

Complete! Added 115 Mediterranean chicken recipes with full ingredient enrichment and intelligent tagging."
```

### Ingredient Analysis & Similarity Mapping
```
You: "Analyze all my ingredients and create similarity mappings for better recipe recommendations."

Claude: [Uses ekitchen-db MCP for comprehensive analysis]
Analyzing 1,247 ingredients in your database...

AI-powered similarity analysis complete:
- Generated 3,421 ingredient relationships
- High similarity pairs: chicken breast ↔ chicken thigh (0.89)
- Substitution recommendations: olive oil ↔ avocado oil (0.72)  
- Dietary alternatives: butter ↔ coconut oil (0.65, vegan)
- Regional variations: cilantro ↔ coriander leaves (0.95)

Inserted similarity mappings into ingredient_similarities table.
Your recipe recommendation system can now suggest recipes based on ingredient substitutions and alternatives."
```

### Error Handling & Edge Cases
```
You: "Some of my ingredient enrichments failed. Can you research alternatives and retry?"

Claude: [Uses ekitchen-db MCP to identify failed ingredients]
Found 8 ingredients that failed Spoonacular enrichment:
- 'sumac berries', 'black lime', 'preserved lemons', 'harissa paste', 'za'atar', 'pomegranate molasses', 'rose harissa', 'dukkah'

[Uses spoonacular MCP with alternative names]
Researching alternative names...
- 'sumac berries' → 'ground sumac' ✓ Found match
- 'black lime' → 'dried lime' ✓ Found match  
- 'preserved lemons' → 'salt-preserved lemons' ✓ Found match
- 'harissa paste' → 'harissa' ✓ Found match

Successfully enriched 6/8 ingredients. 2 remaining ('rose harissa', 'dukkah') are specialty items not in Spoonacular database - marked for manual research."
```

## Key Advantages Over Original Pipeline

### Simplicity
- **No queue systems** to build or maintain
- **No separate AI processing service** 
- **AI handles all format standardization** naturally in conversation context
- **Single operation workflows** instead of multi-step pipelines

### Intelligence
- **AI makes contextual decisions** about data quality and formatting
- **Smart deduplication** against existing database content
- **Intelligent error recovery** and alternative name suggestions
- **Natural language progress reporting** with detailed explanations

### Token Efficiency  
- **Large JSON processing** (50MB+ recipe data in single operation)
- **Batch operations** reduce MCP round-trips
- **AI processes everything in context** without external tool calls

### Cost Efficiency
- **Pay only for AI usage** during active ingestion
- **No infrastructure overhead** for queue systems
- **Efficient batch processing** through intelligent AI orchestration

## File Structure
```
mcp-servers/
├── ekitchen-db/
│   ├── server.py          # AI-powered database operations
│   ├── requirements.txt
│   └── config.py
├── recipe-discovery/
│   ├── server.py          # Multi-site recipe scraping
│   ├── scrapers.py        # Site-specific extraction logic  
│   └── requirements.txt
├── spoonacular/
│   ├── server.py          # Batch ingredient enrichment
│   ├── api_client.py      # Rate-limited API wrapper
│   └── requirements.txt
└── claude-desktop-config.json
```

## Configuration
```json
{
  "mcpServers": {
    "ekitchen-db": {
      "command": "python",
      "args": ["mcp-servers/ekitchen-db/server.py"],
      "env": {
        "DATABASE_URL": "postgresql://...",
        "OPENAI_API_KEY": "your_key"
      }
    },
    "recipe-discovery": {
      "command": "python", 
      "args": ["mcp-servers/recipe-discovery/server.py"]
    },
    "spoonacular": {
      "command": "python",
      "args": ["mcp-servers/spoonacular/server.py"],
      "env": {
        "SPOONACULAR_API_KEY": "your_key"
      }
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://..."]
    }
  }
}
```

## Success Metrics

**Week 1**: Complete pipeline operational
- Can discover and process 100+ recipes in single conversation
- AI standardization working across all major recipe sites
- Ingredient enrichment with Spoonacular integration functional

**Week 2**: Production ready with intelligence
- Advanced multi-site discovery with error handling
- AI-powered ingredient and recipe tagging operational  
- Similarity mapping generation working
- Ready for bulk data ingestion (1000+ recipes)

## Cost Estimate
- **Development time**: 2 weeks vs. 4-6 weeks for complex pipeline
- **AI usage**: ~$5-15 per 1000 recipes processed (batch efficiency)
- **Infrastructure**: $0 (runs locally)
- **Total monthly cost**: $15-25 for moderate usage

This simplified MCP approach gives you **all the power** of your original complex pipeline through natural conversations, with **75% less development time** and **zero operational overhead**.