# Decay Rate and Shelf Life Implementation

## Overview

This document describes the implementation of default decay rate and typical shelf life tracking for ingredients, which enables the hybrid confidence decay system in the eKitchen app.

## BACKEND-2 Migration

The backend team has added two new columns to the `global_ingredients` table:

```sql
ALTER TABLE global_ingredients
ADD COLUMN default_decay_rate VARCHAR(20) CHECK (default_decay_rate IN ('fast', 'medium', 'slow', 'pantry'));

ALTER TABLE global_ingredients
ADD COLUMN typical_shelf_life_days INTEGER CHECK (typical_shelf_life_days > 0);

CREATE INDEX idx_global_ingredients_decay ON global_ingredients(default_decay_rate);
```

These columns map to the confidence decay system:
- `default_decay_rate`: Maps to confidence decay speed (fast/medium/slow/pantry)
- `typical_shelf_life_days`: Expected shelf life in days

## Implementation Components

### 1. Backfill Script for Existing Ingredients

**File**: `data-maintenance/backfill_decay_and_shelf_life.py`

This script assigns decay rates and shelf life to all existing global ingredients based on their category field.

#### Mapping Rules

| Category    | Decay Rate    | Shelf Life (days) | Notes                                |
|-------------|---------------|-------------------|--------------------------------------|
| proteins    | fast          | 5                 | Direct mapping                       |
| dairy       | medium        | 10                | Direct mapping                       |
| vegetables  | fast or slow  | 7 or 21           | AI decides: leafy→fast, root→slow    |
| fruits      | fast or slow  | 7 or 21           | AI decides: berries→fast, citrus→slow|
| grains      | pantry        | 365               | Direct mapping                       |
| condiments  | pantry        | 180               | Direct mapping                       |
| spices      | pantry        | 730               | Direct mapping                       |
| beverages   | pantry/medium | 180 or 14         | AI decides: bottled→pantry, fresh→medium |
| other       | medium        | 30                | Default fallback                     |

#### AI Decision Logic

For ambiguous categories (vegetables, fruits, beverages), the script uses OpenAI GPT-4o to intelligently categorize:

**Vegetables**:
- LEAFY/SOFT (fast, 7 days): lettuce, spinach, herbs, tomatoes, cucumbers, peppers
- ROOT/HARD (slow, 21 days): potatoes, carrots, onions, garlic, beets, turnips

**Fruits**:
- SOFT/BERRY (fast, 7 days): berries, grapes, bananas, peaches, plums
- CITRUS/HARD (slow, 21 days): oranges, lemons, apples, pears, melons

**Beverages**:
- SHELF-STABLE (pantry, 180 days): bottled water, soda, wine, shelf-stable milk
- FRESH (medium, 14 days): fresh milk, fresh juice, smoothies

#### Usage

```bash
# Preview changes without making updates (recommended first)
python data-maintenance/backfill_decay_and_shelf_life.py --dry-run

# Preview first 10 ingredients only
python data-maintenance/backfill_decay_and_shelf_life.py --dry-run --limit 10

# Actually update all ingredients
python data-maintenance/backfill_decay_and_shelf_life.py --live

# Update with limit
python data-maintenance/backfill_decay_and_shelf_life.py --live --limit 50
```

#### Output

The script generates:
- Console output with progress and results
- JSON preview file: `data-maintenance/decay_backfill_preview_{timestamp}.json`

Preview file includes:
- Summary statistics
- Detailed data for each processed ingredient
- AI decision tracking

### 2. Updated Ingredient Creation Logic

**File**: `src/processing/ingredient_processor_direct.py`

The ingredient processor now automatically sets decay rate and shelf life for all newly created ingredients.

#### Changes Made

1. **Updated IngredientData dataclass** (lines 81-82):
```python
default_decay_rate: Optional[str] = None  # fast, medium, slow, pantry
typical_shelf_life_days: Optional[int] = None
```

2. **Added decay rate determination method** (lines 805-928):
```python
def determine_decay_rate_and_shelf_life(self, ingredient_name: str, category: str) -> tuple[str, int]:
    """Determine decay rate and typical shelf life based on category and AI analysis."""
    # ... implementation
```

3. **Added AI-powered decay determination** (lines 849-928):
```python
def _determine_decay_rate_with_ai(self, ingredient_name: str, category: str) -> tuple[str, int]:
    """Use AI to determine decay rate for ambiguous categories"""
    # ... implementation
```

4. **Integrated into ingredient creation** (lines 552-560):
```python
# Step 2.5: Determine decay rate and shelf life based on category
if not ingredient_data.default_decay_rate or not ingredient_data.typical_shelf_life_days:
    decay_rate, shelf_life = self.determine_decay_rate_and_shelf_life(
        ingredient_data.name,
        ingredient_data.category
    )
    ingredient_data.default_decay_rate = decay_rate
    ingredient_data.typical_shelf_life_days = shelf_life
```

5. **Added fields to API payload** (lines 581-584):
```python
# Add decay rate and shelf life if set
if ingredient_data.default_decay_rate:
    create_data["default_decay_rate"] = ingredient_data.default_decay_rate
if ingredient_data.typical_shelf_life_days:
    create_data["typical_shelf_life_days"] = ingredient_data.typical_shelf_life_days
```

#### Workflow

When a new ingredient is created:

1. **Category determination** (via AI or fallback)
2. **Decay rate assignment**:
   - Simple categories → Direct mapping
   - Complex categories (vegetables, fruits, beverages) → AI analysis
3. **Fields added to ingredient** before creation
4. **Sent to backend** as part of ingredient creation payload

### 3. Integration with Existing Systems

#### Recipe Processing Pipeline

All recipe ingestion modes now automatically set decay rates:
- **Single recipe URL** (`interactive_recipe_ingestion.py` mode 3)
- **Batch cuisine processing** (`interactive_recipe_ingestion.py` mode 2)
- **All cuisines** (`interactive_recipe_ingestion.py` mode 1)
- **Search & scrape** (`interactive_recipe_ingestion.py` mode 4)
- **Multi-query search** (`interactive_recipe_ingestion.py` mode 5)

#### Data Maintenance Scripts

The enrichment script also supports these fields:
- `data-maintenance/ingredient_enrichment_script.py`

## Testing

### Test Backfill Script (Development Database)

```bash
# Step 1: Dry run to preview changes
python data-maintenance/backfill_decay_and_shelf_life.py --dry-run --limit 20

# Step 2: Review the preview JSON file
cat data-maintenance/decay_backfill_preview_*.json

# Step 3: Run on small batch for testing
python data-maintenance/backfill_decay_and_shelf_life.py --live --limit 10

# Step 4: Verify in database
# Use your database client to check the updated ingredients
```

### Test New Ingredient Creation

```bash
# Use the interactive ingestion system to create a new ingredient
python recipe-processing/interactive_recipe_ingestion.py

# Choose mode 3 (Single Recipe URL)
# Process a recipe with new ingredients
# Verify the decay_rate and shelf_life_days are set in the database
```

### Validation Queries

```sql
-- Check decay rate distribution
SELECT default_decay_rate, COUNT(*) as count
FROM global_ingredients
GROUP BY default_decay_rate
ORDER BY count DESC;

-- Check ingredients with decay rates set
SELECT
    category,
    default_decay_rate,
    COUNT(*) as count,
    AVG(typical_shelf_life_days) as avg_shelf_life
FROM global_ingredients
WHERE default_decay_rate IS NOT NULL
GROUP BY category, default_decay_rate
ORDER BY category, default_decay_rate;

-- Check ingredients still missing decay rates
SELECT COUNT(*) as missing_count
FROM global_ingredients
WHERE default_decay_rate IS NULL OR typical_shelf_life_days IS NULL;
```

## Production Deployment

### Step 1: Backfill Existing Ingredients

```bash
# On your local machine with production database access via Railway

# 1. Preview full backfill (will show what would change)
python data-maintenance/backfill_decay_and_shelf_life.py --dry-run

# 2. Review the preview JSON to ensure correctness

# 3. Run the full backfill (WARNING: This updates production data)
python data-maintenance/backfill_decay_and_shelf_life.py --live

# 4. Verify completion
# Check the final statistics in console output
# Run validation queries above to verify data
```

### Step 2: Deploy Updated Code

The updated ingredient processor is already in your codebase. No additional deployment needed - all future ingredient creation will automatically include decay rates.

### Step 3: Monitor

After backfill:
- Check backend logs for any errors
- Verify new ingredients have decay rates set
- Monitor confidence decay calculations in the app

## Rollback Plan

If issues are discovered:

```sql
-- Rollback decay rates (set to NULL)
UPDATE global_ingredients
SET default_decay_rate = NULL,
    typical_shelf_life_days = NULL
WHERE default_decay_rate IS NOT NULL;

-- Or rollback specific category
UPDATE global_ingredients
SET default_decay_rate = NULL,
    typical_shelf_life_days = NULL
WHERE category = 'vegetables';
```

## Future Enhancements

1. **Manual Override Support**: Allow users to override default decay rates for specific ingredients in their pantry
2. **Learning System**: Track actual decay patterns and adjust defaults over time
3. **Seasonal Variations**: Adjust shelf life based on season/temperature
4. **Purchase Date Tracking**: Use actual purchase dates when available
5. **Storage Method Adjustments**: Different decay rates for frozen vs. refrigerated vs. pantry

## References

- Backend PR: BACKEND-2
- Related Backend Issue: BACKEND-1 (user_ingredients table with hybrid model)
- Confidence Decay Documentation: [Link to confidence decay docs]

## Questions or Issues

If you encounter problems:
1. Check logs in `logs/ingredient_processor_*.log`
2. Review preview JSON files in `data-maintenance/`
3. Run dry-run mode first to preview changes
4. Contact backend team if database constraints fail
