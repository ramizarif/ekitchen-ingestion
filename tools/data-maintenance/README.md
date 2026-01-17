# 🔧 Data Maintenance Scripts

This folder contains scripts for **fixing, cleaning, and rebuilding existing data** in the database.

## 📋 Maintenance Scripts

### `comprehensive_ingredient_rebuild.py` ⭐ **PRIMARY MAINTENANCE TOOL**
- **Purpose**: Fix and enrich existing ingredients in the database
- **Use**: `python3 comprehensive_ingredient_rebuild.py`
- **Features**:
  - Finds ingredients with `needs_enrichment=true`
  - Enriches with Spoonacular nutrition data
  - Adds proper categorization via OpenAI
  - Fixes missing nutrition values
  - Updates external_id links to Spoonacular
  - Comprehensive logging and progress tracking

## 🎯 When to Use

### After Recipe Ingestion
- Run after processing recipes to enrich any ingredients that were created without full data
- Fixes ingredients that failed Spoonacular lookup during recipe processing
- Updates categories for ingredients that were created with default "other" category

### Data Quality Improvements
- Periodically run to ensure all ingredients have proper nutrition data
- Fix ingredients that may have been created with old logic
- Ensure consistent categorization across all ingredients

### API Issues Recovery
- Run after Spoonacular API outages to fill in missing data
- Fix ingredients created during periods when enrichment failed
- Update ingredients that were created as basic entries due to API limits

## 🔄 Typical Maintenance Workflow

### Regular Maintenance (Weekly/Monthly)
```bash
cd data-maintenance
python3 comprehensive_ingredient_rebuild.py
```

### Post-Processing Cleanup
```bash
# After running recipe ingestion
cd recipe-processing
python3 interactive_recipe_ingestion.py
# Process recipes...

# Then clean up any ingredients that need enrichment
cd ../data-maintenance  
python3 comprehensive_ingredient_rebuild.py
```

### Emergency Data Fixes
```bash
# When you notice ingredients missing nutrition data
cd data-maintenance
python3 comprehensive_ingredient_rebuild.py
```

## 📊 What Gets Fixed

- ✅ **Missing Nutrition**: Calories, protein, fat, carbs, sugar
- ✅ **Wrong Categories**: Updates "other" to proper categories (proteins, dairy, etc.)
- ✅ **Missing External IDs**: Links ingredients to Spoonacular database
- ✅ **Consistency**: Ensures all ingredients follow same data standards
- ✅ **Cost Estimation**: Adds estimated costs from Spoonacular

## ⚠️ Important Notes

- **Safe to run multiple times**: Script checks existing data and only updates what needs fixing
- **Non-destructive**: Only adds/updates data, doesn't delete existing information
- **Progress tracking**: Shows detailed progress and logs all changes
- **Error handling**: Continues processing even if some ingredients fail
- **Rollback safe**: Changes are incremental and logged for review

## 🔮 Future Maintenance Scripts

As the system grows, additional maintenance scripts will be added here:
- `fix_recipe_duplicates.py` - Remove duplicate recipes
- `update_ingredient_categories.py` - Bulk category updates
- `sync_spoonacular_changes.py` - Update when Spoonacular data changes
- `clean_orphaned_data.py` - Remove unused/orphaned records