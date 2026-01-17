# Purchase Unit Conversion Fix Script

This script fixes existing ingredients in the database that have purchase units but are missing proper unit conversions.

## The Problem

Existing ingredients in the database may have:
- Purchase units like "can", "bottle", "jar" defined in `purchase_info`
- But missing those purchase units from `possible_units`
- Or missing conversion factors from purchase units to recipe units
- This makes purchase units unusable in recipes and shopping lists

## The Solution

The script:
1. 🔍 **Analyzes** all ingredients to find conversion gaps
2. ➕ **Adds** purchase units to `possible_units` if missing  
3. 🤖 **Generates** AI-powered conversion factors for purchase units
4. 💾 **Updates** ingredients with complete conversion mappings

## Usage

### Preview Changes (Safe)
```bash
python3 fix_purchase_unit_conversions.py --dry-run
```

### Apply Changes (Database Updates)
```bash
python3 fix_purchase_unit_conversions.py --apply
```

### Limit Number of Fixes
```bash
python3 fix_purchase_unit_conversions.py --dry-run --limit 10
```

### Disable File Logging
```bash
python3 fix_purchase_unit_conversions.py --dry-run --no-logs
```

## What Gets Fixed

### Example: Honey Ingredient

**Before Fix:**
```json
{
  "name": "honey",
  "estimated_cost_unit": "tablespoon",
  "purchase_info": {
    "purchase_unit": "bottle",
    "purchase_quantity": 32
  },
  "possible_units": ["cup", "tablespoon", "teaspoon"],
  "unit_conversions": {
    "cup": 16.0,
    "tablespoon": 1.0,
    "teaspoon": 0.33
  }
}
```

**Issues Detected:**
- ❌ Purchase unit "bottle" not in `possible_units`  
- ❌ Purchase unit "bottle" not in `unit_conversions`

**After Fix:**
```json
{
  "name": "honey", 
  "estimated_cost_unit": "tablespoon",
  "purchase_info": {
    "purchase_unit": "bottle",
    "purchase_quantity": 32
  },
  "possible_units": ["cup", "tablespoon", "teaspoon", "bottle"],
  "unit_conversions": {
    "cup": 16.0,
    "tablespoon": 1.0, 
    "teaspoon": 0.33,
    "bottle": 32.0
  }
}
```

**Result:**
- ✅ Users can add "1 bottle honey" to recipes
- ✅ Shopping lists can convert bottles to tablespoons
- ✅ Cost calculations work for all units

## Safety Features

- **Dry Run Mode**: Preview all changes before applying
- **Detailed Logging**: Track every operation with timestamps
- **Error Handling**: Graceful failures with detailed error messages
- **Authentication**: Secure API access with proper credentials
- **Batch Processing**: Efficient handling of large ingredient databases
- **Statistics**: Comprehensive success/failure reporting
- **PATCH Updates**: Uses proper HTTP PATCH method to update only specified fields

## Sample Output

```
🚀 Starting Purchase Unit Conversion Fix Script
======================================================================
Mode: DRY RUN (preview only)
======================================================================
✅ eKitchen authentication successful
🔍 Fetching all ingredients from eKitchen database...
   📥 Fetched 50 ingredients (total: 50)
   📥 Fetched 32 ingredients (total: 82)
✅ Total ingredients fetched: 82

🔍 Analyzing 82 ingredients for conversion issues...
📋 Found 15 ingredients needing fixes:
   1. honey - purchase_unit 'bottle' not in possible_units; not in unit_conversions
   2. diced tomatoes - purchase_unit 'can' not in unit_conversions
   3. peanut butter - purchase_unit 'jar' not in possible_units
   ...

👀 Previewing fixes...

--- 1/15 ---
🔧 [DRY RUN] Fixing: honey (ID: abc123)
   Issues: purchase_unit 'bottle' not in possible_units; not in unit_conversions
   ➕ Adding 'bottle' to possible_units
   🤖 AI estimated: 1 bottle = 32.0 tablespoon
   ✅ [DRY RUN] Would update with 4 conversions

======================================================================
📊 PURCHASE UNIT CONVERSION FIX SUMMARY  
======================================================================
Total ingredients analyzed: 82
Candidates needing fixes: 15
Successfully fixed: 15
Failed fixes: 0

✅ 15 ingredients now have proper purchase unit conversions!
   Users can now use purchase units in recipes and shopping lists

📈 Success rate: 100.0%
======================================================================
```

## Prerequisites

- eKitchen admin credentials in `local.env`
- OpenAI API key for AI-powered conversions
- Internet connection for API calls
- Python 3.7+ with required dependencies

## Troubleshooting

**Authentication Failed:**
- Check `EKITCHEN_ADMIN_EMAIL` and `EKITCHEN_ADMIN_PASSWORD` in `local.env`

**OpenAI Errors:**
- Verify `OPENAI_API_KEY` in `local.env`
- Check API quota and billing

**Database Errors:**
- Ensure eKitchen API is accessible
- Check network connectivity

**No Candidates Found:**
- All ingredients may already have proper conversions
- Run with `--dry-run` to see analysis details