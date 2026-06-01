#!/usr/bin/env python3
"""
re_audit.py — Multi-dimensional audit of the eKitchen global recipe catalog.

Consumes the detail dump produced by the smoke test:
    source prod.env && go test -tags=smoke -count=1 -run Test_DumpGlobalRecipeDetails \
        -timeout 600s ./smoketest      # -> smoketest/global_recipes_detail_dump.json

Usage:
    python3 re_audit.py [path-to-detail-dump.json]

Reports the full launch-readiness picture and PASS/FAIL against the Phase 13
exit criteria CAT-01..09. Also surfaces the dimensions Ramiz cares about:
ingredient overlap (kitchen-aware feature health), cuisine diversity, and
easy/quick weeknight depth.

NOTE: the catalog uses free-form `tag_names` (no controlled meal-type taxonomy
or `collection:` namespace until the Phase 13 tag-backfill runs). Meal-type and
collection numbers below are therefore INFERRED from tag synonyms / structured
fields and represent a floor, not the post-backfill state.
"""
import json
import sys
import collections
import re

# ---- CAT-01..09 launch targets (canonical Phase 13, 800+ catalog) -----------
CAT = {
    "CAT-01": ("total recipes", ">= 800"),
    "CAT-02": ("no duplicate dish names", "0 dupes"),
    "CAT-03": ("quick (<=30 min)", ">= 38%"),
    "CAT-04": ("easy difficulty", ">= 30%"),
    "CAT-05": ("carries a meal-type tag", ">= 95%"),
    "CAT-06": ("meal-type distribution", "breakfast>=12% salad>=7% side>=7% soup>=8%"),
    "CAT-07": ("cuisine balance", "American<=22%, every surfaced cuisine>=12, top-6<=60%"),
    "CAT-08": ("chicken recipes", ">= 20%"),
    "CAT-09": ("format collections", ">= 4 collections with >= 15 each"),
}

# Staples excluded from "overlap health" so pantry basics don't mask the signal.
STAPLES = {
    "salt", "pepper", "black pepper", "ground black pepper", "water", "oil",
    "olive oil", "vegetable oil", "sugar", "granulated sugar", "flour",
    "all-purpose flour", "butter", "unsalted butter", "garlic", "onion",
    "egg", "eggs", "milk", "garlic clove", "garlic cloves",
}

# Meal-type controlled vocab -> tag synonyms (lowercased substring match).
MEAL_TYPES = {
    "breakfast": ["breakfast", "brunch"],
    "lunch": ["lunch"],
    "dinner": ["dinner", "main course", "main dish", "main", "entree", "entrée"],
    "dessert": ["dessert", "sweet"],
    "appetizer": ["appetizer", "starter", "hors"],
    "snack": ["snack"],
    "soup": ["soup", "stew", "chili"],
    "salad": ["salad"],
    "side": ["side", "side dish"],
}

# Format collections (CAT-09) -> tag/name synonyms.
FORMATS = {
    "one-pot": ["one-pot", "one pot", "one-pan", "skillet", "dutch oven"],
    "sheet-pan": ["sheet-pan", "sheet pan", "tray bake", "traybake"],
    "5-ingredient": ["5-ingredient", "5 ingredient", "five-ingredient"],
    "air-fryer": ["air-fryer", "air fryer", "airfryer"],
    "slow-cooker": ["slow-cooker", "slow cooker", "crockpot", "crock-pot"],
    "meal-prep": ["meal-prep", "meal prep"],
    "grilled": ["grilled", "grill", "bbq", "barbecue"],
    "no-bake": ["no-bake", "no bake"],
}


def pct(n, d):
    return (100.0 * n / d) if d else 0.0


def norm_tags(r):
    return [t.strip().lower() for t in (r.get("tag_names") or []) if t and t.strip()]


def ing_names(r):
    out = []
    for ing in (r.get("ingredients") or []):
        nm = (ing.get("name") or "").strip().lower()
        if nm:
            out.append(nm)
    return out


def ing_ids(r):
    return [ing.get("ingredient_id") for ing in (r.get("ingredients") or []) if ing.get("ingredient_id")]


def has_meal_type(tags):
    hit = set()
    for mt, syns in MEAL_TYPES.items():
        for t in tags:
            if any(s == t or s in t for s in syns):
                hit.add(mt)
                break
    return hit


def is_chicken(r):
    name = (r.get("name") or "").lower()
    if "chicken" in name:
        return True
    return any("chicken" in n for n in ing_names(r))


def bar(label, value, width=28):
    filled = int(round(value / 100.0 * width))
    return f"{label:<22} {'█'*filled}{'·'*(width-filled)} {value:5.1f}%"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "smoketest/global_recipes_detail_dump.json"
    data = json.load(open(path))
    N = len(data)

    print("=" * 74)
    print(f"  eKITCHEN CATALOG AUDIT  —  {N} recipes  ({path})")
    print("=" * 74)

    # ---- CUISINE ------------------------------------------------------------
    cuisine = collections.Counter((r.get("cuisine") or "Unknown").strip() for r in data)
    top6 = cuisine.most_common(6)
    top6_share = pct(sum(n for _, n in top6), N)
    american = cuisine.get("American", 0)
    surfaced = [(c, n) for c, n in cuisine.items() if n >= 12]
    thin = sorted([(c, n) for c, n in cuisine.items() if n < 12 and c != "Unknown"], key=lambda x: x[1])

    print("\n## CUISINE DIVERSITY  ({} distinct)".format(len(cuisine)))
    for c, n in cuisine.most_common(12):
        print("  " + bar(c, pct(n, N)) + f"  ({n})")
    print(f"  Top-6 concentration: {top6_share:.1f}%   American: {pct(american,N):.1f}% ({american})")
    print(f"  Surfaced (>=12): {len(surfaced)} cuisines   Thin (<12, would-hide): {len(thin)}")
    if thin:
        print("  Thin tail: " + ", ".join(f"{c}({n})" for c, n in thin[:18]))

    # ---- DIFFICULTY / QUICK -------------------------------------------------
    diff = collections.Counter((r.get("difficulty") or "Unknown") for r in data)
    easy = diff.get("Easy", 0)
    times = [r.get("total_time_minutes") or 0 for r in data]
    quick = sum(1 for t in times if 0 < t <= 30)
    quick_and_easy = sum(1 for r in data if (r.get("difficulty") == "Easy" and 0 < (r.get("total_time_minutes") or 0) <= 30))
    print("\n## DIFFICULTY & SPEED")
    for d in ("Easy", "Medium", "Hard"):
        print("  " + bar(d, pct(diff.get(d, 0), N)) + f"  ({diff.get(d,0)})")
    print("  " + bar("Quick (<=30 min)", pct(quick, N)) + f"  ({quick})")
    print("  " + bar("Quick AND Easy", pct(quick_and_easy, N)) + f"  ({quick_and_easy})")
    # time buckets
    buckets = collections.Counter()
    for t in times:
        if t <= 0: buckets["unknown"] += 1
        elif t <= 20: buckets["<=20m"] += 1
        elif t <= 30: buckets["21-30m"] += 1
        elif t <= 45: buckets["31-45m"] += 1
        elif t <= 60: buckets["46-60m"] += 1
        else: buckets[">60m"] += 1
    print("  time buckets: " + "  ".join(f"{k}:{pct(v,N):.0f}%" for k, v in
          sorted(buckets.items(), key=lambda x: ["<=20m","21-30m","31-45m","46-60m",">60m","unknown"].index(x[0]))))

    # ---- CHICKEN ------------------------------------------------------------
    chicken = sum(1 for r in data if is_chicken(r))
    print("\n## PROTEIN ANCHOR")
    print("  " + bar("Chicken (name/ingr)", pct(chicken, N)) + f"  ({chicken})")

    # ---- MEAL-TYPE ----------------------------------------------------------
    mt_counter = collections.Counter()
    tagged = 0
    multi = 0
    for r in data:
        hits = has_meal_type(norm_tags(r))
        if hits:
            tagged += 1
            if len(hits) > 1:
                multi += 1
            for h in hits:
                mt_counter[h] += 1
    print("\n## MEAL-TYPE COVERAGE  (inferred from free-form tags — pre-backfill floor)")
    print("  " + bar("Has any meal-type", pct(tagged, N)) + f"  ({tagged})")
    print(f"  Multi-meal-type (ambiguous, fails 'exactly one'): {multi}")
    for mt in ("breakfast", "lunch", "dinner", "dessert", "appetizer", "soup", "salad", "side", "snack"):
        print("  " + bar(mt, pct(mt_counter.get(mt, 0), N)) + f"  ({mt_counter.get(mt,0)})")

    # ---- FORMAT COLLECTIONS -------------------------------------------------
    fmt_counter = {}
    has_collection_ns = 0
    for r in data:
        tags = norm_tags(r)
        name = (r.get("name") or "").lower()
        if any(t.startswith("collection:") for t in tags):
            has_collection_ns += 1
        for fmt, syns in FORMATS.items():
            blob = " ".join(tags) + " " + name
            if any(s in blob for s in syns):
                fmt_counter[fmt] = fmt_counter.get(fmt, 0) + 1
    qualifying = {k: v for k, v in fmt_counter.items() if v >= 15}
    print("\n## FORMAT COLLECTIONS  (inferred; no `collection:` namespace until backfill)")
    print(f"  Recipes with explicit `collection:` tag: {has_collection_ns}")
    for fmt, n in sorted(fmt_counter.items(), key=lambda x: -x[1]):
        flag = "OK" if n >= 15 else "  "
        print(f"  [{flag}] {fmt:<14} {n}")

    # ---- DEDUP --------------------------------------------------------------
    names = collections.Counter((r.get("name") or "").strip().lower() for r in data)
    dupes = {n: c for n, c in names.items() if c > 1 and n}
    print("\n## DEDUP")
    print(f"  Duplicate dish names: {len(dupes)}")
    if dupes:
        for n, c in list(dupes.items())[:10]:
            print(f"    x{c}  {n}")

    # ---- NUTRITION ----------------------------------------------------------
    has_cal = sum(1 for r in data if (r.get("calories") or 0) > 0)
    print("\n## NUTRITION")
    print("  " + bar("Non-zero calories", pct(has_cal, N)) + f"  ({has_cal})")

    # ---- IMAGES -------------------------------------------------------------
    has_img = sum(1 for r in data if r.get("thumbnail_photo_id"))
    print("\n## IMAGES")
    print("  " + bar("Has thumbnail", pct(has_img, N)) + f"  ({has_img})")

    # ---- INGREDIENT OVERLAP (kitchen-aware feature health) ------------------
    freq = collections.Counter()
    freq_nonstaple = collections.Counter()
    per_recipe_counts = []
    id_to_name = {}
    recipe_ing_sets = []
    for r in data:
        ids = set(ing_ids(r))
        per_recipe_counts.append(len(ids))
        recipe_ing_sets.append(ids)
        for ing in (r.get("ingredients") or []):
            iid = ing.get("ingredient_id")
            nm = (ing.get("name") or "").strip().lower()
            if not iid:
                continue
            id_to_name[iid] = nm
            freq[iid] += 1
            if nm not in STAPLES:
                freq_nonstaple[iid] += 1
    distinct = len(freq)
    avg_ing = sum(per_recipe_counts) / N if N else 0
    in_2plus = sum(1 for _, c in freq.items() if c >= 2)
    in_5plus = sum(1 for _, c in freq.items() if c >= 5)
    singletons = sum(1 for _, c in freq.items() if c == 1)

    print("\n## INGREDIENT OVERLAP  (kitchen-aware / next-best-ingredient health)")
    print(f"  Distinct ingredients: {distinct}   Avg ingredients/recipe: {avg_ing:.1f}")
    print(f"  Used in >=5 recipes: {in_5plus}   >=2 recipes: {in_2plus}   singletons: {singletons} ({pct(singletons,distinct):.0f}% of distinct)")
    print("  Top staples (most-shared ingredients):")
    for iid, c in freq.most_common(12):
        print(f"     {c:4d}  {id_to_name.get(iid,'?')}")
    print("  Top NON-staple connectors (drive recipe unlocks):")
    for iid, c in freq_nonstaple.most_common(12):
        print(f"     {c:4d}  {id_to_name.get(iid,'?')}")

    # Coverage: if a user stocks the top-K most common ingredients, how many
    # recipes become >=70% covered? Proxy for "the catalog rewards a stocked kitchen".
    for K in (20, 40, 60):
        topK = set(iid for iid, _ in freq.most_common(K))
        reachable = 0
        for s in recipe_ing_sets:
            if not s:
                continue
            if len(s & topK) / len(s) >= 0.7:
                reachable += 1
        print(f"  With top-{K} ingredients stocked: {reachable} recipes ({pct(reachable,N):.0f}%) are >=70% covered")

    # ---- CAT-01..09 SCORECARD ----------------------------------------------
    def verdict(ok):
        return "PASS ✅" if ok else "FAIL ❌"

    cat_quick = pct(quick, N)
    cat_easy = pct(easy, N)
    cat_mt = pct(tagged, N)
    cat_chicken = pct(chicken, N)
    bf, sal, sd, sp = (pct(mt_counter.get(k, 0), N) for k in ("breakfast", "salad", "side", "soup"))
    cat06_ok = bf >= 12 and sal >= 7 and sd >= 7 and sp >= 8
    cat07_ok = pct(american, N) <= 22 and len(thin) == 0 and top6_share <= 60
    cat09_ok = len(qualifying) >= 4

    print("\n" + "=" * 74)
    print("  LAUNCH SCORECARD — CAT-01..09  (target: 800+ catalog)")
    print("=" * 74)
    rows = [
        ("CAT-01", "total >= 800", f"{N}", N >= 800),
        ("CAT-02", "0 duplicate names", f"{len(dupes)} dupes", len(dupes) == 0),
        ("CAT-03", "quick >= 38%", f"{cat_quick:.1f}%", cat_quick >= 38),
        ("CAT-04", "easy >= 30%", f"{cat_easy:.1f}%", cat_easy >= 30),
        ("CAT-05", "meal-tagged >= 95%", f"{cat_mt:.1f}%", cat_mt >= 95),
        ("CAT-06", "bf>=12 sal>=7 side>=7 soup>=8", f"bf{bf:.0f} sal{sal:.0f} sd{sd:.0f} sp{sp:.0f}", cat06_ok),
        ("CAT-07", "Amer<=22 all>=12 top6<=60", f"Amer{pct(american,N):.0f}% thin{len(thin)} top6 {top6_share:.0f}%", cat07_ok),
        ("CAT-08", "chicken >= 20%", f"{cat_chicken:.1f}%", cat_chicken >= 20),
        ("CAT-09", ">=4 collections >=15", f"{len(qualifying)} qualify", cat09_ok),
    ]
    passed = 0
    for cid, target, actual, ok in rows:
        passed += ok
        print(f"  {cid}  {target:<30} {actual:<22} {verdict(ok)}")
    print("-" * 74)
    print(f"  {passed}/9 criteria PASS")
    print("=" * 74)


if __name__ == "__main__":
    main()
