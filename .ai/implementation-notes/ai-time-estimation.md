# AI-Powered Cook Time Estimation

## Problem

Video recipes (TikTok, Instagram, YouTube) often don't include structured time metadata, resulting in imported recipes showing `0 minutes` for prep_time, cook_time, and total_time fields. This makes recipes appear instant/unrealistic in the eKitchen app.

## Solution

Enhanced the AI decisions generation to intelligently estimate cooking times when they're missing from the source.

## Implementation

### 1. Enhanced AI Prompt (`_create_ai_decision_prompt`)

**Updated Input Format:**
```
Prep Time: 0 minutes (0 = not specified, estimate needed)
Cook Time: 0 minutes (0 = not specified, estimate needed)
Total Time: 0 minutes (0 = not specified, estimate needed)
```

**New Response Fields:**
```json
{
  "difficulty": "Easy|Medium|Hard",
  "cuisine": "cuisine_type",
  "tags": ["tag1", "tag2", "tag3"],
  "cozy_description": "...",
  "cozy_instructions": ["...", "..."],
  "dalle_prompt": "...",
  "category": "breakfast|lunch|dinner|snack|dessert",
  "estimated_prep_time_minutes": 15,  // NEW - only if original is 0
  "estimated_cook_time_minutes": 30,  // NEW - only if original is 0
  "estimated_total_time_minutes": 45  // NEW - only if original is 0
}
```

**Guidelines Added:**
```
4. TIME ESTIMATION (only if times are 0 or missing):
   - Analyze the ingredients and cooking steps to estimate realistic times
   - PREP_TIME: Chopping, mixing, measuring (usually 5-30 minutes)
   - COOK_TIME: Active cooking time (stovetop, oven, etc.)
   - TOTAL_TIME: Prep + Cook + any resting/cooling time
   - Be realistic but practical for home cooks
   - Examples: Simple pasta (10 prep, 15 cook, 25 total),
               Roasted chicken (15 prep, 60 cook, 75 total)
```

### 2. Time Application Logic

**Location:** After `generate_ai_decisions()` in both processing flows

**Implementation:**
```python
# Apply AI-estimated times if original times are missing (0 or None)
if ai_decisions:
    if (not recipe_data['prep_time'] or recipe_data['prep_time'] == 0) and ai_decisions.get('estimated_prep_time_minutes'):
        recipe_data['prep_time'] = ai_decisions['estimated_prep_time_minutes']
        self._log_and_print(f"   Using AI-estimated prep time: {recipe_data['prep_time']} minutes")

    if (not recipe_data['cook_time'] or recipe_data['cook_time'] == 0) and ai_decisions.get('estimated_cook_time_minutes'):
        recipe_data['cook_time'] = ai_decisions['estimated_cook_time_minutes']
        self._log_and_print(f"   Using AI-estimated cook time: {recipe_data['cook_time']} minutes")

    if (not recipe_data['total_time'] or recipe_data['total_time'] == 0) and ai_decisions.get('estimated_total_time_minutes'):
        recipe_data['total_time'] = ai_decisions['estimated_total_time_minutes']
        self._log_and_print(f"   Using AI-estimated total time: {recipe_data['total_time']} minutes")
```

**Applied in:**
- `_process_recipe_data()` - lines 1434-1446 (for video recipes via `process_parsed_recipe`)
- `process_recipe_autonomous()` - lines 1605-1616 (for website recipes, as fallback)

### 3. Fallback Time Estimation

Enhanced `_fallback_ai_decisions()` with rule-based estimates when OpenAI is unavailable:

```python
# Rule-based time estimation
if not recipe_data['prep_time'] or recipe_data['prep_time'] == 0:
    # Base prep on ingredient count: 5 + (count * 2), max 30 min
    fallback_times['estimated_prep_time_minutes'] = min(5 + (ingredient_count * 2), 30)

if not recipe_data['cook_time'] or recipe_data['cook_time'] == 0:
    # Base cook on difficulty
    if difficulty == "Easy":
        fallback_times['estimated_cook_time_minutes'] = 15
    elif difficulty == "Medium":
        fallback_times['estimated_cook_time_minutes'] = 30
    else:  # Hard
        fallback_times['estimated_cook_time_minutes'] = 60

if not recipe_data['total_time'] or recipe_data['total_time'] == 0:
    # Sum prep + cook
    prep = fallback_times.get('estimated_prep_time_minutes', recipe_data['prep_time'] or 0)
    cook = fallback_times.get('estimated_cook_time_minutes', recipe_data['cook_time'] or 0)
    fallback_times['estimated_total_time_minutes'] = prep + cook
```

## Examples

### Before (Video Recipe with No Times):
```json
{
  "name": "Quick Pasta Carbonara",
  "prep_time_minutes": 0,
  "cook_time_minutes": 0,
  "total_time_minutes": 0
}
```

### After (AI Estimation Applied):
```json
{
  "name": "Quick Pasta Carbonara",
  "prep_time_minutes": 10,
  "cook_time_minutes": 15,
  "total_time_minutes": 25
}
```

## Estimation Guidelines

The AI follows these heuristics:

| Recipe Complexity | Prep Time | Cook Time | Total Time |
|------------------|-----------|-----------|------------|
| Simple (≤5 ingredients, basic steps) | 5-10 min | 10-20 min | 15-30 min |
| Medium (6-12 ingredients, moderate steps) | 10-20 min | 20-40 min | 30-60 min |
| Complex (>12 ingredients, advanced techniques) | 20-30 min | 40-90 min | 60-120 min |

**Specific Examples:**
- **Quick Stir-Fry:** 10 prep (chop veggies), 10 cook (high heat), 20 total
- **Pasta Carbonara:** 10 prep (bacon, eggs), 15 cook (pasta, sauce), 25 total
- **Roasted Chicken:** 15 prep (season, prep), 60 cook (oven), 75 total
- **Lasagna:** 30 prep (layers), 60 cook (bake), 90 total

## Logging

When AI estimates times, logs show:
```
🤖 PHASE 4: AI RECIPE DECISIONS
   Using AI-estimated prep time: 10 minutes
   Using AI-estimated cook time: 15 minutes
   Using AI-estimated total time: 25 minutes
```

This provides transparency about which values came from AI estimation vs. source data.

## Fallback Behavior

If OpenAI API is unavailable, rule-based fallback provides reasonable estimates:

| Ingredient Count | Prep Time Estimate |
|-----------------|-------------------|
| 3 ingredients | 5 + (3×2) = 11 min |
| 6 ingredients | 5 + (6×2) = 17 min |
| 10 ingredients | 5 + (10×2) = 25 min |
| 15+ ingredients | 30 min (capped) |

| Difficulty | Cook Time Estimate |
|-----------|-------------------|
| Easy | 15 min |
| Medium | 30 min |
| Hard | 60 min |

## Impact

**Before:**
- Video recipes showed "0 min" for all time fields
- Users had no idea how long recipes would take
- Recipes appeared unrealistic/instant

**After:**
- All imported recipes have realistic time estimates
- Times based on actual recipe complexity
- Better user experience and planning

## Testing

To verify AI time estimation:

1. **Import a video recipe** without time metadata (most TikTok recipes)
2. **Check logs** for "Using AI-estimated..." messages
3. **Verify in eKitchen** that recipe shows realistic cook times
4. **Test fallback** by disabling OpenAI (should still get rule-based estimates)

## Code References

**AI Prompt:**
- `services/recipe_processor.py:890-961` - `_create_ai_decision_prompt()` method
- Lines 915-917: New estimated time fields in JSON response
- Lines 927-933: Time estimation guidelines

**Time Application:**
- `services/recipe_processor.py:1434-1446` - Applied in `_process_recipe_data()`
- `services/recipe_processor.py:1605-1616` - Applied in `process_recipe_autonomous()`

**Fallback Estimation:**
- `services/recipe_processor.py:992-1023` - Enhanced `_fallback_ai_decisions()`
- Lines 992-1009: Rule-based time calculation logic

## Deployment

Committed in: `92bef78` - "feat: Add AI-powered cook time estimation for video recipes"
Deployed to: `development` branch (production)
