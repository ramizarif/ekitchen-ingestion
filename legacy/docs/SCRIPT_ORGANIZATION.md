# 📁 Script Organization Guide

This document explains how all recipe processing scripts are organized for clarity and efficiency.

## 🗂️ Folder Structure

```
ekitchen-ingestion/
├── 📁 recipe-processing/          # Normal recipe ingestion workflow
│   ├── interactive_recipe_ingestion.py    ⭐ Main entry point
│   ├── enhanced_batch_processor.py        # OpenAI-powered batch processing  
│   ├── run_all_cuisines.py               # Process all cuisine files
│   ├── simplified_recipe_discovery.py     # URL discovery with Playwright
│   ├── batch_recipe_processor.py          # Legacy batch processor
│   ├── demo_single_recipe.py             # Single recipe testing
│   └── README.md                          # Detailed usage guide
│
├── 📁 data-maintenance/           # Fix/rebuild existing data
│   ├── comprehensive_ingredient_rebuild.py ⭐ Main maintenance tool
│   └── README.md                          # Maintenance procedures
│
├── 📁 tests/                     # Testing and validation
│   ├── test_spoonacular_simple.py        # API connectivity tests
│   ├── test_ingredient_409_fix.py        # Conflict prevention tests
│   ├── test_spoonacular_enrichment.py    # Enrichment pipeline tests
│   ├── test_interactive.py               # Interactive system tests
│   └── README.md                          # Testing procedures
│
├── 📁 src/                       # Core processing modules
│   ├── processing/               # Main processing classes
│   └── discovery/               # URL discovery tools
│
└── 📁 cuisines/                  # Recipe data files
    ├── italian/
    ├── thai/
    └── ...
```

## 🎯 What Goes Where

### 📁 recipe-processing/
**Purpose**: Scripts you run to ingest NEW recipes from start to finish

**Use when**:
- Processing new recipes from URLs
- Bulk ingesting cuisine collections  
- Discovering recipe URLs from search pages
- Testing single recipe processing
- Running complete ingestion workflows

### 📁 data-maintenance/
**Purpose**: Scripts you run to fix/improve EXISTING data in the database

**Use when**:
- Ingredients are missing nutrition data
- Categories need to be updated
- Spoonacular links are missing
- Data quality needs improvement
- Recovery from API outages

### 📁 tests/
**Purpose**: Scripts to validate functionality and debug issues

**Use when**:
- Testing API connectivity
- Debugging processing issues
- Validating new code changes
- Checking for common problems

## 🚀 Quick Start Workflows

### New Recipe Processing
```bash
cd recipe-processing
python3 interactive_recipe_ingestion.py
```

### Data Cleanup/Maintenance  
```bash
cd data-maintenance
python3 comprehensive_ingredient_rebuild.py
```

### System Health Check
```bash
cd tests
python3 test_spoonacular_simple.py
python3 test_ingredient_409_fix.py
```

## 🔄 Typical Usage Pattern

1. **Process new recipes** using `recipe-processing/` scripts
2. **Fix any data issues** using `data-maintenance/` scripts  
3. **Validate everything works** using `tests/` scripts
4. **Repeat** as needed

## 📋 Key Benefits

- ✅ **Clear separation**: Know immediately what each script does
- ✅ **Easy maintenance**: Find the right tool for the job quickly
- ✅ **Better organization**: Related scripts grouped together
- ✅ **Documentation**: Each folder has detailed README
- ✅ **Scalable**: Easy to add new scripts in the right place

## 🆕 Adding New Scripts

### New recipe processing feature?
→ Add to `recipe-processing/`

### New data fixing tool?  
→ Add to `data-maintenance/`

### New test or validation?
→ Add to `tests/`

This organization makes it clear what each script does and when to use it!