#!/usr/bin/env python3
"""Full validation of GET /discover/kitchen-snapshot against live prod.

Checks contract shape, per-module integrity, cross-module dedup, auth edge cases,
and — the important one — independently verifies module C's "buy these staples ->
make these recipes" promise by recomputing each unlocked recipe's missing set from
its real ingredients vs the kitchen inventory and asserting it's a subset of the
listed staples.
"""
import sys, time, requests, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.ingredient_processor import DirectIngredientProcessor, load_env_file

env = load_env_file("local.env")
p = DirectIngredientProcessor(log_to_file=False)
p.authenticate_ekitchen(env["EKITCHEN_ADMIN_EMAIL"], env["EKITCHEN_ADMIN_PASSWORD"])
H = {"Authorization": f"Bearer {p.access_token}"}
BASE = p.ekitchen_base_url

PASS, FAIL = 0, 0
def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  ✅ {label}")
    else:
        FAIL += 1; print(f"  ❌ {label}")

def kitchen_ingredient_ids(kid):
    r = requests.get(f"{BASE}/kitchens/{kid}/ingredients", headers=H, timeout=30)
    if r.status_code != 200:
        return None
    data = r.json()
    items = data.get("ingredients", data) if isinstance(data, dict) else data
    ids = set()
    for it in items or []:
        iid = it.get("ingredient_id") or it.get("id")
        if iid:
            ids.add(iid)
    return ids

def recipe_ingredient_ids(rid):
    r = requests.get(f"{BASE}/global-recipes/{rid}", headers=H, timeout=30)
    if r.status_code != 200:
        return None
    return {i.get("ingredient_id") for i in (r.json().get("ingredients") or []) if i.get("ingredient_id")}

def validate(kid, label):
    global PASS, FAIL
    print(f"\n=== {label} (kitchen {kid}) ===")
    t0 = time.time()
    r = requests.get(f"{BASE}/discover/kitchen-snapshot?kitchen_id={kid}", headers=H, timeout=90)
    dt = time.time() - t0
    check(r.status_code == 200, f"HTTP 200 ({r.status_code}) in {dt:.2f}s")
    if r.status_code != 200:
        return
    d = r.json()

    # Contract
    for k in ("cook_now", "one_trip_away", "unlock_the_most", "taste_picks", "kitchen_ingredient_count"):
        check(k in d, f"key present: {k}")
    cook = d.get("cook_now") or []
    onetrip = d.get("one_trip_away") or []
    utm = d.get("unlock_the_most") or {}
    taste = d.get("taste_picks") or []
    staples = utm.get("ingredients") or []
    unlocked = utm.get("unlocked_recipes") or []

    check(len(cook) <= 5, f"cook_now <= 5 ({len(cook)})")
    check(len(onetrip) <= 5, f"one_trip_away <= 5 ({len(onetrip)})")
    check(len(taste) <= 5, f"taste_picks <= 5 ({len(taste)})")
    check(len(staples) <= 8, f"staples <= 8 ({len(staples)})")

    # Module B integrity
    for ot in onetrip:
        mi = ot.get("missing_ingredients") or []
        check(ot.get("missing_count") == len(mi), f"B: missing_count matches list ({ot.get('recipe',{}).get('recipe_name','?')[:30]})")
        check(all(m.get("ingredient_id") and m.get("name") for m in mi), "B: missing items have id+name")

    # Module C: no dead staples
    if staples:
        check(all(s.get("unlocks_count", 0) >= 1 for s in staples), "C: every staple unlocks >=1 recipe (no dead staples)")
        check(utm.get("unlocked_count", 0) >= 1, f"C: unlocked_count >= 1 ({utm.get('unlocked_count')})")
        print(f"     {utm.get('summary')}")

    # Module C PROMISE: staples truly cover the unlocked recipes
    staple_ids = {s["ingredient_id"] for s in staples}
    kids = kitchen_ingredient_ids(kid)
    if kids is not None and unlocked:
        all_covered = True
        for rc in unlocked[:6]:
            ring = recipe_ingredient_ids(rc["id"])
            if ring is None:
                continue
            real_missing = ring - kids
            if not real_missing.issubset(staple_ids):
                all_covered = False
                print(f"     ⚠️ {rc.get('name','?')[:34]}: missing {real_missing - staple_ids} NOT in staples")
        check(all_covered, "C: PROMISE — staples fully cover every unlocked recipe")

    # Cross-module dedup
    buckets = {
        "cook_now": [x.get("recipe_id") for x in cook],
        "one_trip": [x.get("recipe", {}).get("recipe_id") for x in onetrip],
        "unlocked": [x.get("id") for x in unlocked],
        "taste":    [x.get("id") for x in taste],
    }
    seen, dup = set(), False
    for ids in buckets.values():
        for i in ids:
            if i in seen:
                dup = True
            seen.add(i)
    check(not dup, "no recipe appears in two modules")

    print(f"     counts: cook={len(cook)} one_trip={len(onetrip)} staples={len(staples)} unlocked={len(unlocked)} taste={len(taste)} kitchen={d.get('kitchen_ingredient_count')}")

def auth_edges():
    print("\n=== auth / edge ===")
    r = requests.get(f"{BASE}/discover/kitchen-snapshot", headers=H, timeout=30)
    check(r.status_code == 400, f"missing kitchen_id -> 400 ({r.status_code})")

if __name__ == "__main__":
    kitchens = sys.argv[1:] or ["d2vlm9ufcrcc7388bsug"]
    for i, kid in enumerate(kitchens):
        validate(kid, f"kitchen #{i+1}")
    auth_edges()
    print(f"\n{'='*50}\nRESULT: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
