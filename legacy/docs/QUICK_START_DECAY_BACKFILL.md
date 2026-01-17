# Quick Start: Decay Rate and Shelf Life Backfill

## TL;DR - What We Built

✅ **Backfill Script**: Assigns decay rates and shelf life to ~500 existing ingredients
✅ **New Ingestion Logic**: All future ingredients automatically get these fields
✅ **AI-Powered**: Smart categorization for vegetables, fruits, and beverages

## What You Need to Do

### 1. Test on Development Database (10 minutes)

```bash
# Step 1: Preview what will change (dry-run, no actual updates)
python3 data-maintenance/backfill_decay_and_shelf_life.py --dry-run --limit 10

# Step 2: Review the preview JSON file
cat data-maintenance/decay_backfill_preview_*.json | jq

# Step 3: Test on small batch (5 ingredients)
python3 data-maintenance/backfill_decay_and_shelf_life.py --live --limit 5

# Step 4: Verify in your database
psql $DATABASE_URL -c "SELECT name, category, default_decay_rate, typical_shelf_life_days FROM global_ingredients WHERE default_decay_rate IS NOT NULL LIMIT 10;"
```

### 2. Run Full Backfill on Production (20-30 minutes)

```bash
# Step 1: Preview full backfill (recommended)
python3 data-maintenance/backfill_decay_and_shelf_life.py --dry-run

# Review the stats in the output

# Step 2: Run the full backfill
python3 data-maintenance/backfill_decay_and_shelf_life.py --live

# This will:
# - Process all ~500 ingredients
# - Use AI for vegetables, fruits, and beverages
# - Save a detailed preview JSON file
# - Take approximately 20-30 minutes (due to AI API calls)

# Step 3: Verify completion
psql $DATABASE_URL -c "
SELECT
    default_decay_rate,
    COUNT(*) as count
FROM global_ingredients
GROUP BY default_decay_rate
ORDER BY count DESC;
"
```

### 3. Future Ingredient Creation (Already Working!)

No action needed! All future ingredients will automatically get decay rates when created through:

- Single recipe processing
- Batch recipe processing
- Cuisine processing
- Search & scrape
- Multi-query search

## How It Works

### Category Mapping Rules

| Category   | Decay Rate   | Shelf Life | How Determined |
|------------|--------------|------------|----------------|
| proteins   | fast         | 5 days     | Direct mapping |
| dairy      | medium       | 10 days    | Direct mapping |
| grains     | pantry       | 365 days   | Direct mapping |
| condiments | pantry       | 180 days   | Direct mapping |
| spices     | pantry       | 730 days   | Direct mapping |
| other      | medium       | 30 days    | Default fallback |
| vegetables | fast or slow | 7 or 21    | **AI decides**: leafy→fast, root→slow |
| fruits     | fast or slow | 7 or 21    | **AI decides**: berries→fast, citrus→slow |
| beverages  | pantry/medium| 180 or 14  | **AI decides**: bottled→pantry, fresh→medium |

### Examples of AI Decision Making

**Vegetables**:
- 🥬 Lettuce → fast (7 days) - leafy vegetable
- 🥔 Potato → slow (21 days) - root vegetable

**Fruits**:
- 🍓 Strawberries → fast (7 days) - soft fruit
- 🍎 Apple → slow (21 days) - hard fruit

**Beverages**:
- 🥤 Soda → pantry (180 days) - shelf-stable
- 🥛 Fresh Milk → medium (14 days) - refrigerated

## Files Changed

### New Files Created

1. **`data-maintenance/backfill_decay_and_shelf_life.py`**
   - Main backfill script
   - ~680 lines of code
   - Handles AI decisions and error recovery

2. **`docs/decay-rate-shelf-life-implementation.md`**
   - Complete documentation
   - Testing instructions
   - Deployment guide

3. **`tests/test_decay_rate_assignment.py`**
   - Logic verification tests
   - Sample ingredient examples

4. **`QUICK_START_DECAY_BACKFILL.md`** (this file)
   - Quick reference guide

### Modified Files

1. **`src/processing/ingredient_processor_direct.py`**
   - Added `default_decay_rate` and `typical_shelf_life_days` to `IngredientData` dataclass
   - Added `determine_decay_rate_and_shelf_life()` method
   - Added `_determine_decay_rate_with_ai()` method
   - Integrated into ingredient creation flow

## Troubleshooting

### Issue: "Authentication failed"

**Solution**: Check your `local.env` file has correct credentials:
```bash
EKITCHEN_ADMIN_EMAIL=your-admin-email
EKITCHEN_ADMIN_PASSWORD=your-admin-password
EKITCHEN_BASE_URL=https://ekitchen-production.up.railway.app
```

### Issue: "OpenAI API key not found"

**Solution**: Add to `local.env`:
```bash
OPENAI_API_KEY=your-openai-api-key
```

### Issue: "No ingredients need updating"

This means:
- Either all ingredients already have decay rates set, OR
- The script couldn't fetch ingredients from the API

**Solution**: Check your database connection and API authentication.

### Issue: Rate limiting / slow performance

The script includes rate limiting (0.5-1 second between API calls) to avoid overwhelming:
- OpenAI API (for AI decisions)
- eKitchen API (for updates)

For ~500 ingredients with ~150 requiring AI decisions, expect **20-30 minutes** total runtime.

## Verification Queries

After backfill, run these to verify:

```sql
-- Check decay rate distribution
SELECT default_decay_rate, COUNT(*) as count
FROM global_ingredients
GROUP BY default_decay_rate
ORDER BY count DESC;

-- Expected output:
-- pantry  | ~250 (grains, condiments, spices, beverages)
-- fast    | ~100 (proteins, some vegetables/fruits)
-- medium  | ~100 (dairy, some beverages)
-- slow    | ~50  (root vegetables, hard fruits)

-- Check ingredients by category
SELECT
    category,
    default_decay_rate,
    COUNT(*) as count,
    AVG(typical_shelf_life_days) as avg_shelf_life
FROM global_ingredients
WHERE default_decay_rate IS NOT NULL
GROUP BY category, default_decay_rate
ORDER BY category, default_decay_rate;

-- Find any ingredients still missing decay rates
SELECT COUNT(*) as missing_count
FROM global_ingredients
WHERE default_decay_rate IS NULL OR typical_shelf_life_days IS NULL;
-- Should be 0 after successful backfill
```

## Next Steps

After completing the backfill:

1. ✅ Verify all ingredients have decay rates (run verification queries above)
2. ✅ Test new ingredient creation to ensure it works
3. ✅ Monitor backend logs for any errors
4. ✅ Move to BACKEND-1 (user_ingredients table with hybrid model)

## Questions?

See full documentation: [`docs/decay-rate-shelf-life-implementation.md`](docs/decay-rate-shelf-life-implementation.md)

## Summary

You now have:
- ✅ Backfill script ready to run
- ✅ Updated ingestion pipeline
- ✅ AI-powered categorization
- ✅ Complete documentation
- ✅ Test suite

**Ready to execute the backfill whenever you are!** 🚀
