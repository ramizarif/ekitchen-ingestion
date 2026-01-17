# eKitchen Ingestion - Organized Repository Structure

## 📁 **New Organized Structure**

```
├── src/                                    # Core application code
│   ├── discovery/                          # Recipe discovery scripts
│   │   ├── discover_urls_python.py         # URL discovery
│   │   ├── discover_urls_with_web_images.py # URL + image discovery
│   │   ├── discover-urls-and-images.sh     # Shell script for discovery
│   │   ├── scrape_recipe_images.py         # Image downloading
│   │   └── recipe_discovery_and_images.py  # Combined pipeline
│   ├── processing/                         # Recipe & ingredient processing
│   │   └── ingredient_processor_direct.py  # ✅ PRODUCTION: Direct API processor
│   ├── mcp_servers/                        # MCP server implementations
│   │   ├── recipe_discovery_mcp/           # Recipe discovery MCP server
│   │   ├── spoonacular_mcp/                # Spoonacular MCP server
│   │   └── spoonacular_client/             # Spoonacular API client
│   ├── utils/                              # Shared utilities
│   │   └── tmux_utils.py                   # Agent health monitoring
│   └── tagging/                            # Tag definitions
│       ├── ingredient_tags.json
│       └── recipe_tags.json
├── config/                                 # Configuration files
│   ├── spoonacular.json                    # Spoonacular API key
│   └── discovered_search_urls.json         # Recipe site URL patterns
├── cuisines/                               # Recipe data by cuisine
│   ├── mexican/
│   │   ├── dish-names.txt                  # Source dish list
│   │   ├── recipes.json                    # Recipe URLs + metadata
│   │   └── processing-log.txt              # Agent progress log
│   ├── italian/
│   │   ├── dish-names.txt
│   │   └── recipes.json
│   ├── thai/
│   │   ├── dish-names.txt
│   │   ├── notes.txt
│   │   └── recipes.json
│   └── recipe-images/                      # Downloaded images
│       ├── mexican/
│       ├── italian/
│       └── thai/
├── scripts/                                # Utility scripts
│   ├── send-claude-message.sh              # Inter-agent communication
│   ├── schedule_with_note.sh               # Self-scheduling
│   ├── start_spoonacular_mcp.py            # Spoonacular MCP launcher
│   └── start-orchestrator.sh               # System launcher
├── docs/                                   # Documentation
│   ├── recipe-ingestion-orchestration-guide.md  # ✅ MAIN WORKFLOW GUIDE
│   ├── README.md                           # Detailed documentation
│   └── project-breakdown/                 # Historical development docs
├── CLAUDE.md                               # Agent context and guidelines
├── PROJECT_CONTEXT.md                      # Application context
├── README.md                               # Quick overview
├── claude_mcp_config.json                  # MCP server configuration
└── requirements.txt                        # Python dependencies
```

## 🎯 **Key Organizational Principles**

### **1. Logical Code Organization**
- **`src/discovery/`** - All recipe URL discovery and image downloading scripts
- **`src/processing/`** - Ingredient processing and recipe creation logic
- **`src/mcp_servers/`** - All MCP server implementations grouped together
- **`src/utils/`** - Shared utilities and helpers

### **2. Clear Separation of Concerns**
- **Configuration** - Centralized in `config/` directory
- **Data** - Recipe data and images in `cuisines/` directory  
- **Documentation** - All guides and docs in `docs/` directory
- **Scripts** - Utility and communication scripts in `scripts/`

### **3. Updated Path References**
All import statements and file references have been updated to match the new structure:

- **Ingredient Processor**: `src/processing/ingredient_processor_direct.py`
- **Discovery Scripts**: `src/discovery/discover_urls_python.py`
- **MCP Servers**: `src/mcp_servers/recipe_discovery_mcp/server.py`
- **Orchestration Guide**: `docs/recipe-ingestion-orchestration-guide.md`

### **4. MCP Configuration Updated**
`claude_mcp_config.json` has been updated to use the new module paths:
```json
"args": ["-m", "src.mcp_servers.recipe_discovery_mcp.server"]
```

## ✅ **Benefits of New Structure**

1. **Cleaner Root Directory** - Only essential files at root level
2. **Logical Grouping** - Related functionality grouped together
3. **Easier Navigation** - Clear purpose for each directory
4. **Better Imports** - Proper Python module structure
5. **Scalability** - Easy to add new components in appropriate locations

## 🚀 **Production Workflow**

The finalized production workflow uses:

1. **Discovery**: `src/discovery/` scripts to populate recipe databases
2. **Processing**: `src/processing/ingredient_processor_direct.py` for ingredient pipeline
3. **Orchestration**: `docs/recipe-ingestion-orchestration-guide.md` for agent workflow
4. **Communication**: `scripts/` for inter-agent coordination

This organized structure provides a clean, scalable foundation for autonomous recipe ingestion with clear separation of concerns and logical code organization.