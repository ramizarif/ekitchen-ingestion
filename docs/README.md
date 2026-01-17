# eKitchen Recipe Ingestion System

## Overview
Autonomous recipe ingestion system for eKitchen using cuisine-specific agents with direct API integration, DALL-E image generation, and comprehensive ingredient processing.

## 🚀 **Finalized Workflow**

### **Phase 1: Recipe Discovery & Setup**
Use these scripts to populate cuisine recipe databases:

1. **URL Discovery**: `discover_urls_python.py` - Discover recipe URLs for cuisines
2. **Image Download**: `scrape_recipe_images.py` - Download recipe images 
3. **Combined Flow**: `recipe_discovery_and_images.py` - Complete URL + image pipeline

### **Phase 2: Recipe Ingestion**
Follow `recipe-ingestion-orchestration-guide.md` for complete autonomous ingestion:

1. **Scrape Recipe**: Using `mcp__recipe-discovery__scrape_single_recipe`
2. **Generate Images**: DALL-E 3 HD with homey, cozy brand identity
3. **Process Ingredients**: `ingredient_processor_direct.py` (direct API calls)
4. **Calculate Nutrition**: Based on Spoonacular data and quantities
5. **Rewrite Instructions**: Warm, cozy brand voice transformation
6. **Create Recipe**: Complete eKitchen database entry with nutrition

## 📁 **Key Files**

### **Production Scripts**
- `src/processing/ingredient_processor_direct.py` - Direct API ingredient processing (NO MCP dependencies)
- `docs/recipe-ingestion-orchestration-guide.md` - Complete agent workflow guide

### **Discovery Scripts** 
- `src/discovery/discover_urls_python.py` - Recipe URL discovery
- `src/discovery/scrape_recipe_images.py` - Recipe image downloading
- `src/discovery/recipe_discovery_and_images.py` - Combined discovery pipeline

### **Configuration**
- `config/spoonacular.json` - Spoonacular API key
- `config/discovered_search_urls.json` - Recipe site URL patterns
- `claude_mcp_config.json` - MCP server configuration

### **Data Structure**
```
cuisines/
├── mexican/
│   ├── dish-names.txt           # Source dish list
│   ├── recipes.json             # Recipe URLs + metadata
│   └── processing-log.txt       # Agent progress log
└── recipe-images/
    └── mexican/                 # Downloaded recipe images
        ├── tacos.jpg
        └── enchiladas.jpg
```

## 🎯 **Agent Workflow**

1. **Cuisine Assignment**: Each agent processes one cuisine (e.g., "Mexican Agent")
2. **Recipe Processing**: Sequential processing of all recipes in `cuisines/{cuisine}/recipes.json`
3. **Complete Pipeline**: Scraping → DALL-E generation → Ingredient processing → Recipe creation
4. **Progress Tracking**: Real-time logging and error resilience

## 🛠 **Core Technologies**

- **Direct API Calls**: eKitchen production database + Spoonacular API
- **DALL-E 3 HD**: Professional food photography generation
- **MCP Integration**: Recipe discovery and eKitchen database operations
- **Autonomous Processing**: Self-contained ingredient pipeline

## 📊 **Success Metrics**

- **100% Direct API Success**: No MCP dependencies for ingredient processing
- **Homey Brand Identity**: DALL-E images with cozy, family-kitchen feel
- **Complete Nutrition**: Accurate per-serving calculations from Spoonacular
- **Warm Instructions**: Brand-aligned recipe step rewriting
- **Production Ready**: Full integration with eKitchen production database

## 🚦 **Getting Started**

1. **Setup**: Ensure MCP servers are configured (`claude_mcp_config.json`)
2. **Discovery**: Run URL discovery scripts to populate `cuisines/{cuisine}/recipes.json`
3. **Agent Launch**: Follow orchestration guide for autonomous recipe ingestion
4. **Monitor**: Track progress via `cuisines/{cuisine}/processing-log.txt`

The system is designed for autonomous 24/7 operation with comprehensive error handling and brand consistency.

## 📁 **Repository Structure**

```
├── cuisines/                           # Recipe data by cuisine
│   ├── mexican/recipes.json            # Recipe URLs + metadata
│   ├── italian/recipes.json            # Recipe URLs + metadata
│   └── recipe-images/                  # Downloaded images
├── src/
│   ├── processing/
│   │   └── ingredient_processor_direct.py  # ✅ PRODUCTION: Direct API processor
│   ├── discovery/
│   │   ├── discover_urls_python.py         # Recipe URL discovery
│   │   ├── scrape_recipe_images.py         # Image downloading
│   │   └── recipe_discovery_and_images.py  # Combined discovery
│   └── mcp_servers/
│       ├── recipe_discovery_mcp/           # Recipe discovery MCP server
│       └── spoonacular_mcp/                # Spoonacular MCP server
├── docs/
│   └── recipe-ingestion-orchestration-guide.md  # ✅ MAIN WORKFLOW GUIDE
├── config/
│   ├── spoonacular.json                # Spoonacular API key
│   └── discovered_search_urls.json     # Site URL patterns
├── scripts/                            # Communication & utilities
└── docs/project-breakdown/             # Historical development docs
```

## 🎨 **Key Features**

### **Homey Brand Identity**
- DALL-E 3 generates cozy, family-kitchen style food photography
- Instructions rewritten with warm, encouraging language
- "Restaurant professional" → "Homemade with love" transformation

### **Production-Ready Processing**
- Direct API authentication with eKitchen production database
- Real Spoonacular API integration with nutrition calculations
- Error resilience with fallback ingredient creation

### **Autonomous Agent Operation**
- Cuisine-specific agents work independently on their assigned recipes
- Complete pipeline from recipe discovery to database creation
- Real-time progress tracking and error logging

---

**Built for autonomous 24/7 recipe ingestion with brand consistency and production reliability.**