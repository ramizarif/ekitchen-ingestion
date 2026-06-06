# Handoff: Recipe ingestion is re-polluting the ingredient catalog

**Date:** 2026-06-06
**Author:** diagnosed from the eKitchen backend / prod DB (`ekitchen` database on Railway Postgres)
**For:** ingestion-pipeline owner/agent (`ekitchen-ingestion`)
**Type:** problem statement + evidence. Fix direction is suggested, not prescribed — solve in ingestion.

---

## TL;DR

The recipe-import pipeline, when it extracts an ingredient string it can't match to an existing canonical ingredient, **auto-creates a brand-new `global_ingredients` row** marked `is_canonical = false, needs_enrichment = true`, fills in units/cost/category, and links it to the recipe. **Nothing ever processes those flagged rows**, so they accumulate permanently. A manual catalog cleanup on 2026-06-05 (consolidated everything onto canonical names, stripped synonyms) was **undone within a day**: a Caribbean recipe batch on 2026-06-06 created **123 new non-canonical rows across 59 recipes**. Some are genuinely missing ingredients; some are extraction garbage. Both pollute the catalog and fragment it semantically, which degrades recommendations, ready-to-cook, kitchen dedup, and shopping overlap.

---

## Evidence (measured on prod `ekitchen` DB, 2026-06-06)

Update timeline on `global_ingredients`:

| Day | Rows touched | Non-canonical created |
|-----|----|----|
| 2026-06-05 (manual cleanup) | 546 | **0** |
| 2026-06-06 (Caribbean import batch) | 129 | **123** |

State of the 123 new non-canonical rows:
- **99 / 123** flagged `needs_enrichment = true`; **0** are `ready_for_enrichment` → they're flagged but **no job promotes or processes them**.
- **103 / 123** have `possible_units` populated, **all** have `estimated_cost_value` → the pipeline spends enrichment effort even on garbage rows.
- **0** have `original_name`; 42 have `external_id`.
- Referenced by **120 `recipe_ingredients`** rows across **59 distinct recipes**, plus 3 `kitchen_ingredients`.
- **0** are flagged `potential_duplicate` — even though clear semantic duplicates of existing canonicals exist (see below).

Two failure classes in the 123:

1. **Genuinely missing ingredients** (legit, but should be created canonical or matched, not dumped as non-canonical):
   `callaloo`, `ackee`, `plantain`, `culantro`, `escallion`, `pimento seed`, `red snapper`, `codfish`, `pork loin chop`, `corned beef brisket`, …
2. **Extraction garbage** (should never become an ingredient at all):
   `ingredient needed`, `seasoning ingredient`, `salt and pepper`, `salt and black pepper`, `texa toast`, and raw un-parsed recipe lines like
   `1 cup dried channa (chickpeas) or 1 can of chickpeas (drained and rinsed)3 medium potato`.

Semantic duplication against existing canonicals (same real ingredient, new fragmented row):
- `escallion` → existing canonical `scallion` (spelling variant)
- `codfish` → existing `cod`
- `pork loin chop` → existing `pork loin`
- (`corned beef brisket`→`corn`/`beef`, `olive juice`→`ice` show the current substring matcher is also *noisy*, not just weak.)

---

## Mechanism (what the pipeline is doing)

Observed end-to-end (DB result is verified; the exact Python code path is for you to confirm in `ekitchen-ingestion`):

1. Recipe is scraped/extracted; GPT produces ingredient strings.
2. Each string is matched against `global_ingredients`. The backend matcher (`SearchGlobalIngredients`) is **plain Postgres `ILIKE` + `synonyms` array containment — no fuzzy/trigram/Levenshtein**.
3. On no-match, the pipeline **creates a new `global_ingredients` row** with `is_canonical = false`, `needs_enrichment = true`, and best-effort units/cost/category, then links it to the recipe.
4. There is **no downstream job** that reviews `needs_enrichment = true` rows to promote, merge, or delete them (`ready_for_enrichment = 0` for all 123). They are terminal.

---

## Aggravating factor: the 2026-06-05 cleanup made matching *weaker*

The cleanup **stripped all synonyms** (now 0/1021 rows have any). Synonyms were one of the matcher's few tools (the `$1 ILIKE ANY(synonyms)` tier). With synonyms gone, **more extracted strings fail to match → more auto-creates**. The cleanup and the auto-create-on-no-match behavior are now actively in tension: cleanup removes fuzz-matching ability, ingestion punishes the lack of it by minting more non-canonical rows. Any fix needs to account for "how do we match `escallion`→`scallion` now that synonyms are gone."

---

## Why this causes real problems

The recommendation/cooking features key off `ingredient_id`, so **fragmenting one real ingredient into multiple rows silently breaks matching**:

1. **Recommendations & ready-to-cook degrade.** A recipe that imported `escallion` (new id) won't surface for a user whose kitchen has `scallion` (different id) — they look like different ingredients to the Redis inverted index. Every fragment is a missed match.
2. **Kitchen/pantry dedup breaks.** A user can end up with both `cod` and `codfish`, `pork loin` and `pork loin chop` — counted as distinct stock.
3. **Shopping-overlap optimization worsens.** The marginal-gain greedy planner treats fragments as separate needs, producing worse "one trip" plans.
4. **Garbage surfaces to users.** `ingredient needed`, `seasoning ingredient`, and raw recipe-line strings can appear in ingredient search, recipe ingredient lists, and shopping lists.
5. **Unbounded, self-undoing growth.** Every import adds rows faster than any manual cleanup can remove them; point-in-time cleanups don't hold. Catalog quality trends down without an ingestion-side gate.
6. **Wasted enrichment cost** on rows that are duplicates or garbage (units + cost computed for `ingredient needed`).
7. **Downstream feature risk (receipt scanning):** the upcoming receipt feature maps cryptic items to this same catalog. A fragmented, synonym-less catalog makes that harder — and it's adopting a *skip-on-no-match, never auto-create* policy specifically to avoid replicating this pollution. The import path should arguably do the same.

---

## Fix direction (suggested — solve in ingestion)

Not prescriptive; pick what fits the pipeline:

- **Stop auto-creating on weak/no match.** Either skip the ingredient, or create into a **quarantine state excluded from canonical search/recommendations** until explicitly reviewed/promoted — don't let unreviewed rows participate in matching or surface to users.
- **Match harder before creating.** Add fuzzy/trigram (`pg_trgm` similarity) or a GPT-based "resolve to existing canonical or say NONE" step against the current catalog (this is the approach receipt scanning is taking). This directly catches `escallion`→`scallion`, `codfish`→`cod`.
- **Reject extraction garbage pre-create.** Validate ingredient strings: drop multi-ingredient strings (contains " or ", commas, embedded quantities/measurements), length caps, and a blocklist (`ingredient needed`, `seasoning ingredient`, bare `salt and pepper`). These are extraction failures, not ingredients.
- **Actually process `needs_enrichment = true`.** Build the promotion/dedup pass that's implied by the flag (99 rows are sitting unprocessed). Promote genuine-missing → canonical; merge duplicates; delete garbage.
- **Decide the post-cleanup aliasing model.** Synonyms were removed; if `escallion` and `scallion` should resolve together, there needs to be *some* alias mechanism (re-introduce synonyms, a variant table, or canonical-resolution at match time). Align this with whatever the cleanup intended.

---

## Verification / triage queries (prod `ekitchen` DB)

```sql
-- the 123 (today's non-canonical)
SELECT id, name, needs_enrichment, external_id, updated_at::date
FROM global_ingredients WHERE NOT is_canonical ORDER BY updated_at DESC;

-- which recipes pulled them in
SELECT DISTINCT ri.recipe_id, gr.title
FROM recipe_ingredients ri
JOIN global_ingredients g ON g.id = ri.ingredient_id
JOIN global_recipes gr ON gr.id = ri.recipe_id
WHERE NOT g.is_canonical;

-- candidate canonical matches for the real ones (manual review)
SELECT nc.name AS noncanon, c.name AS maybe_canonical
FROM global_ingredients nc
JOIN global_ingredients c ON c.is_canonical
 AND lower(c.name) % lower(nc.name)   -- requires pg_trgm; else use ILIKE
WHERE NOT nc.is_canonical;
```

**Immediate cleanup (backend side, separate from the pipeline fix):** the 123 can be triaged now — promote genuine ingredients to canonical, merge the spelling/variant duplicates, delete the garbage — but it'll just refill until the ingestion-side gate above lands.
