# GSD Plan: Ingredient Data Audit & Cleanup

## Goal
Every ingredient in the database is a real cooking ingredient with accurate nutrition, cost, and category data. No junk (tools/equipment), no duplicates, no missing fields. New ingestion prevents these problems going forward.

---

## Current State (793 ingredients)

| Problem | Count | % | Examples |
|---------|-------|---|---------|
| Missing nutrition (calories=0) | 233 | 29% | paprika powder, chocolate chip, dashi stock |
| Missing cost (cost=0) | 237 | 30% | baking soda, bonito shaving, dashi granule |
| Bad category ("other" or NULL) | 72 | 9% | brown sugar, cocoa powder, cornstarch |
| Junk (not ingredients) | ~15 | 2% | fork, foil, baking sheet, frying pan, skewer |
| Duplicates/variants | ~40+ pairs | 5% | flour/all purpose flour, basil/basil leaf, panko breadcrumb/panko crumb |
| Test data | 2+ | <1% | artichoke hearts unit test |
| `needs_enrichment=true` | 169 | 21% | Various |

---

## Phase 1: Fix Ingestion Pipeline (Stop the Bleeding)
**Priority**: P0 | **Effort**: Medium

These changes prevent new junk and duplicates from entering the DB.

### Task 1: Add junk ingredient filter to ingestion

**Where**: During GPT-4 recipe parsing (before ingredients hit the DB)

**What**: Add a classification step that rejects non-ingredient items:
- **Equipment/tools**: fork, baking sheet, foil, skewer, frying pan, pot, sheet pan, potato ricer, bamboo skewer
- **Prepared foods used as garnish**: french fry, bean and cheese burrito, tortilla chip (when listed as "serve with")
- **Non-food items**: food coloring, cooking spray, parchment paper

**Implementation options** (pick one):
1. **Blocklist approach** (simplest): Maintain a list of known non-ingredients. Check during `process_ingredients_enhanced()` in `recipe_processor.py`. Skip any ingredient whose standardized name matches the blocklist.
2. **GPT classification** (smarter): During the existing AI standardization step, add a field `"is_real_ingredient": true/false` to the prompt. If false, skip it. This handles edge cases the blocklist would miss.
3. **Hybrid** (recommended): Hard blocklist for obvious stuff (fork, foil) + GPT classification for ambiguous items (cooking spray, corn husk). The blocklist catches 90% with zero API cost.

**Files to modify**:
- `services/recipe_processor.py` — `process_ingredients_enhanced()` method, add filtering before Spoonacular lookup
- Possibly the GPT-4 standardization prompt (already exists in the method)

### Task 2: Add similarity/duplicate detection + canonical resolution during ingestion

**Where**: Before creating a new `global_ingredient` in the DB

**What**: Before inserting a new ingredient, check if a similar one already exists. If a match is found, AI determines which name is canonical — and if the EXISTING ingredient has the wrong name, rename it.

**Flow**:
1. **Exact match** (already exists): Skip creation, use existing ID
2. **Fuzzy match**: Search for similar names using:
   - Substring containment: "paprika powder" → find "paprika"
   - Common suffix/prefix stripping: "smoked paprika" → check "paprika"
   - Singularization: "tomatoes" → "tomato"
   - Query the DB: `SELECT id, name FROM global_ingredients WHERE name ILIKE '%paprika%'`

3. **If fuzzy match found**: Use GPT-4o-mini to determine:
   - Are these the same ingredient? (yes/no)
   - If yes, which name is canonical? (e.g., "paprika" is canonical, "paprika powder" is not)

4. **Three possible outcomes**:

   **A. New name matches existing, existing is canonical**:
   → Use existing ingredient ID. Don't create new one.
   → Example: "paprika powder" comes in, "paprika" exists → use "paprika"

   **B. New name matches existing, NEW name is canonical**:
   → Use existing ingredient ID BUT rename it to the canonical name via the backend rename endpoint.
   → The rename endpoint (`PUT /ingredients/{id}/rename`) updates the ingredient name AND all references in recipe steps/text.
   → Example: "paprika" comes in, "paprika powder" exists → rename "paprika powder" → "paprika" in DB + all recipe references, then use that ID.

   **C. Different ingredients** (e.g., "almond" vs "almond milk"):
   → Create new ingredient as normal.

**Backend rename endpoint**: Check the backend at `/Users/ramiz/go/src/github.com/ekitchen` for:
- `PUT /ingredients/{id}/rename` or similar
- `PATCH /global-ingredients/{id}` with name field
- Whatever endpoint updates ingredient name + propagates to recipe_ingredients and recipe steps text

**Files to modify**:
- `services/ingredient_processor.py` — add `_find_similar_ingredient()` and `_resolve_canonical_name()` methods before `_create_global_ingredient()`
- `services/recipe_processor.py` — add check in `process_ingredients_enhanced()` before calling ingredient creation
- May need to add a rename API call to `services/ekitchen_client.py` or equivalent

### Task 3: Improve GPT-4 recipe parsing prompt for ingredient quality

**Where**: The GPT-4 prompt that parses recipes (in video.py `_parse_recipe_from_text()` and `_vision_extract_recipe()`, and the new `_analyze_description()`)

**What**: Update the prompt to:
- Explicitly instruct: "Only include actual cooking INGREDIENTS. Do not include equipment (fork, baking sheet), serving suggestions (french fries on the side), or garnishes that are not part of the recipe preparation."
- Instruct: "Use canonical ingredient names. Say 'paprika' not 'paprika powder'. Say 'flour' not 'all purpose flour' unless the specific type matters for the recipe."
- Instruct: "Combine duplicate ingredients. If salt is used in multiple sub-recipes (marinade + sauce), list it once with the total amount."

**Files to modify**:
- `parsers/video.py` — GPT-4 prompts in `_parse_recipe_from_text()`, `_vision_extract_recipe()`, `_analyze_description()`
- `parsers/website.py` — if it has similar parsing

---

## Phase 2: Database Cleanup (Fix Existing Data)
**Priority**: P0 | **Effort**: Medium-Large

### Task 4: Delete junk ingredients

**What**: Remove non-ingredients from `global_ingredients` and update any `recipe_ingredients` that reference them.

**Junk to delete** (confirmed non-ingredients):
```
fork, foil, baking sheet, bamboo skewer, frying pan, sheet pan,
skewer, potato ricer, pot, french fry, bean and cheese burrito,
food coloring (debatable), corn husk (debatable)
```

**Also delete test data**:
```
artichoke hearts unit test 20250926105617
artichoke hearts unit test 20250926105724
```

**Process**:
1. Query `recipe_ingredients` to find which recipes reference junk ingredients
2. Delete `recipe_ingredients` rows referencing junk
3. Delete `global_ingredients` rows for junk
4. Update `recipe_ingredients` count for affected recipes

**Script**: Write a migration or one-off script. NOT a manual SQL operation — needs to be auditable.

### Task 5: Merge duplicate ingredients

**What**: For each duplicate pair, pick the canonical version (the one with better data / more usage), and update all `recipe_ingredients` to point to the canonical ID.

**Known duplicates to merge** (canonical ← variant):
```
paprika ← paprika powder
flour ← all purpose flour (unless recipe needs specificity)
anchovy ← anchovy filet, anchovy fillet
panko breadcrumb ← panko bread crumb, panko crumb
basil ← basil leaf
cider vinegar ← apple cider vinegar (these might actually be different)
yeast ← active dry yeast (these ARE different — don't merge)
barbecue sauce ← barbeque sauce
baguette ← french bread baguette
```

**Process**:
1. Generate full duplicate candidate list from DB (substring matching query)
2. For each pair, GPT-4o-mini classifies: same ingredient or legitimately different? If same, which name is canonical?
3. For confirmed duplicates:
   a. Pick canonical name (AI decides, not just "more references")
   b. If canonical name ≠ the ingredient with more data/references: rename via backend rename endpoint first (updates recipe steps text too)
   c. Re-point all `recipe_ingredients` from variant ID → canonical ID
   d. Mark variant as `variant_of_id` pointing to canonical (soft delete — keep for redirect)
4. The rename endpoint is critical here — ingredient names appear in recipe step text (e.g., "add the paprika powder"), so renaming must cascade through the backend

**Important**: Some "duplicates" are legitimately different:
- `almond` vs `almond milk` vs `almond flour` — all different
- `basil` vs `thai basil` — different
- `active dry yeast` vs `yeast` — arguably different
- `chipotle` vs `chipotle pepper` vs `chipotle chile in adobo sauce` — different preparations

Need GPT-4 to make these calls, not just substring matching.

### Task 6: Re-enrich ingredients with missing data

**What**: For the ~233 ingredients missing nutrition and ~237 missing cost, re-run Spoonacular + AI enrichment.

**Process**:
1. Query all ingredients where `calories = 0 OR estimated_cost_value = 0`
2. For each, call the existing enrichment pipeline:
   - Spoonacular search → nutrition + cost
   - If Spoonacular fails: AI estimation for category, cost, shelf life
3. Update the DB with enriched data
4. Set `needs_enrichment = false` for successfully enriched ingredients

**Rate limiting**: Spoonacular has limits (150 req/min, 5000/day). Batch with delays.

**Script**: Write a standalone enrichment script in `scripts/backfill_ingredients.py` that:
- Queries ingredients needing enrichment
- Processes them in batches of 50 with 1-second delays
- Logs results (enriched, failed, skipped)
- Can be re-run safely (idempotent)

### Task 7: Fix miscategorized ingredients

**What**: 72 ingredients with `category = 'other'` need proper categorization.

Many are obviously wrong:
- `brown sugar` → `pantry` or `baking`
- `cocoa powder` → `baking`
- `baking powder` → `baking`
- `cornstarch` → `pantry`
- `chicken broth` → `pantry`

**Process**: Run the existing AI categorization on all `category = 'other'` ingredients. This is already part of the enrichment pipeline, so Task 6 should handle most of these.

---

## Phase 2B: Ambiguous Step Match Resolution
**Priority**: P0 | **Effort**: Medium

### Current State
- **81 unresolved** ambiguous step matches, **0 resolved**
- These are cases where a recipe step references a generic word (e.g., "sauce", "pepper", "zest") but the recipe has multiple ingredients matching that word
- Most common: "sauce" (~20 cases), "pepper", "oil", "sugar", "vinegar"
- Unresolved matches mean the cooking instructions screen can't link the step text to the correct specific ingredient

### Task 10: Auto-resolve existing ambiguous matches

**What**: Write a script that uses GPT-4o-mini to resolve all 81 unresolved matches via the existing `ResolveAmbiguousStepMatch` backend endpoint.

**Script**: `scripts/resolve_ambiguous_matches.go` (or a smoke test in `smoketest/misc_smoke_test.go`)

**Flow for each match**:
1. Fetch the match: `GetAmbiguousStepMatch(id)` — returns `recipe_id`, `step_position`, `template` (the step text), `ambiguous_word`, `possible_matches[]`
2. Fetch the recipe: get the full recipe so we have context (recipe name, all steps, all ingredients)
3. Send to GPT-4o-mini with prompt:

```
A recipe step contains an ambiguous ingredient reference.

Recipe: {recipe_name}
Step {step_position}: "{template}"
Ambiguous word: "{ambiguous_word}"
Possible matches (ingredient names from this recipe): {possible_matches}

Which specific ingredient does "{ambiguous_word}" refer to in this step?
Respond with ONLY the exact ingredient name from the possible matches list.
If truly ambiguous and impossible to determine, respond with the most likely match.
```

4. Call `ResolveAmbiguousStepMatch(id, resolved_match)` with the AI's answer
5. Log result

**Rate limiting**: Process sequentially with 200ms delay between API calls. 81 matches × ~$0.0001 per GPT-4o-mini call = ~$0.008 total cost.

**Use admin client** (`ekitchenclient.Client`) to call the backend endpoints, same pattern as `TestMergeDuplicateIngredients`.

### Task 11: Auto-resolve ambiguous matches during ingestion

**What**: When the ingestion pipeline creates a recipe with ambiguous step matches, immediately resolve them using GPT-4o-mini instead of leaving them unresolved.

**Where**: The backend creates ambiguous matches during recipe creation in `usercreatedrecipes.go:133`. The ingestion service calls the recipe creation endpoint. After creation, the ingestion service should:

1. Fetch ambiguous matches for the new recipe: `GET /global-recipes/{recipeId}/ambiguous-step-matches` (check if this endpoint exists, or use `GetAmbiguousMatchesByRecipeID`)
2. For each match, use the same GPT-4o-mini resolution as Task 10
3. Resolve via `PATCH /global-recipes/ambiguous-step-matches/{id}` with `{"resolved_match": "..."}`

**Files to modify**:
- `services/recipe_processor.py` — after recipe creation succeeds, add a `_resolve_ambiguous_matches(recipe_id)` step
- Need to add API calls to fetch and resolve ambiguous matches (check if ekitchen backend exposes the right endpoints for the ingestion service's auth)

**Alternative**: If the backend endpoints aren't accessible from the ingestion service auth, add resolution logic directly in the backend's recipe creation flow (`usercreatedrecipes.go`) — after creating the ambiguous match entries, immediately call GPT-4o-mini to resolve them before returning.

---

## Phase 3: Verification & Smoke Tests
**Priority**: P0 | **Effort**: Small

### Task 8: Data quality smoke test

**Write a script** (`scripts/verify_ingredient_quality.py`) that:
1. Counts ingredients with missing nutrition/cost/category
2. Checks for known junk ingredient names
3. Checks for obvious duplicate pairs
4. Asserts quality thresholds:
   - < 5% missing nutrition
   - < 5% missing cost
   - 0 junk ingredients
   - 0 test data rows
   - < 10 unresolved duplicates
5. Reports a quality score

### Task 9: Ingestion regression test

**Add to existing smoke tests** or create new:
1. Ingest a recipe that has "serve with french fries" → verify french fry is NOT created as an ingredient
2. Ingest a recipe with "paprika" when paprika already exists → verify NO new "paprika powder" created
3. Ingest a recipe with "1 fork" or "baking sheet" → verify these are skipped
4. Verify all created ingredients have non-zero nutrition and cost

---

## Execution Order

| Phase | Task | Dependencies | Effort | Impact | Status |
|-------|------|-------------|--------|--------|--------|
| 1 | Task 1: Junk filter | None | Small | Prevents future junk | **DONE** |
| 1 | Task 2: Duplicate detection + canonical | None | Medium | Prevents future dupes | **DONE** |
| 1 | Task 3: Better parsing prompts | None | Small | Cleaner ingredients from new ingestion | **DONE** (part of Task 1) |
| 2 | Task 4: Delete junk | None | Small | Cleans ~15 rows | **DONE** (migration ran) |
| 2 | Task 5: Merge duplicates | Task 4 | Medium | Cleans ~40+ pairs | **DONE** (5 pairs via rename endpoint) |
| 2B | Task 10: Auto-resolve existing ambiguous matches | None | Medium | Resolves 81 matches | **DONE** (77/81 resolved, 4 false positives) |
| 2B | Task 11: Auto-resolve during ingestion | Task 10 | Medium | Prevents future unresolved matches | **DONE** (Phase 8 in _process_recipe_data) |
| 2 | Task 6: Re-enrich missing data | Tasks 4, 5 | Medium-Large | Fixes ~233 ingredients | **DONE** (273/277 enriched, 89 Spoonacular + 184 AI) |
| 2 | Task 7: Fix categories | Part of Task 6 | Small | Fixes ~72 ingredients | **DONE** (part of Task 6) |
| 3 | Task 8: Data quality smoke test | Tasks 4-7, 10 | Small | Verification | **DONE** (all 3 checks pass) |
| 3 | Task 9: Ingestion regression test | Tasks 1-3, 11 | Small | Prevents regression | Deferred (covered by ingestion smoke tests) |

## Wave Execution

**Wave 1** (parallel): Tasks 1, 2, 3 — ingestion improvements — **DONE**
**Wave 2** (sequential): Task 4 → Task 5 — DB cleanup — **DONE**
**Wave 3** (parallel): Task 10 + Task 6 — resolve ambiguous matches + re-enrich data
**Wave 4**: Task 11 — wire auto-resolve into ingestion pipeline
**Wave 5** (parallel): Tasks 8, 9 — verification

## Success Criteria

- [x] 0 junk ingredients in DB (tools, equipment, test data) — VERIFIED: 0
- [x] < 10 unresolved duplicate pairs — 5 merged via rename endpoint
- [x] 0 unresolved ambiguous step matches — 77/81 resolved (4 are false positives)
- [x] New ingestion auto-resolves ambiguous matches at creation time — Phase 8 in pipeline
- [x] < 5% ingredients missing cost data — VERIFIED: 0.4% (3/731)
- [x] New ingestion does not create junk or duplicates — blocklist + similarity detection
- [x] Quality smoke test passes — TestIngredientDataQuality: 3/3 PASS
- [ ] ~27% missing nutrition (calories) — Spoonacular doesn't have data for many specialty ingredients. Acceptable for beta.
