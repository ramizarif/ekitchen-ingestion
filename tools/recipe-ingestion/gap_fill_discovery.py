#!/usr/bin/env python3
"""
Gap-fill discovery (READ-ONLY): find recipe URLs to close the cuisine gaps in
docs/INGESTION_CUISINE_GAPS.md (ekitchen backend repo) without ingesting anything.

Pipeline (each step writes JSON consumed by the next; all under data/gap-fill/):

  1. inventory  — pull the live catalog (cuisine, name, ingredients) and print a
                  per-gap-cuisine dish list so we know what we have / don't have.
  2. search     — open-web search (DuckDuckGo) per dish seed, junk-domain filter,
                  per-domain cap across the pool (source diversity), dedupe
                  against catalog names.
  3. score      — metadata-only tiered scrape per URL (recipe-scrapers dedicated
                  -> JSON-LD wild_mode; no LLM, no ingestion, $0): total time,
                  pantry-staple overlap, fresh-ingredient and protein counts.
  4. select     — basket-aware greedy selection: maximize pantry coverage and
                  fresh-ingredient overlap with the already-selected basket,
                  penalize never-seen ingredients and repeated dish archetypes.
                  Emits a reviewable report + URL list per cuisine.

Spends NO OpenAI money and writes NOTHING to the backend. The selected URL
lists feed the existing ingestion (autonomous_ingest.py or /api/v1/ingest).

Usage:
    ../../venv/bin/python gap_fill_discovery.py inventory [--refresh]
    ../../venv/bin/python gap_fill_discovery.py search --cuisine caribbean
    ../../venv/bin/python gap_fill_discovery.py score --cuisine caribbean
    ../../venv/bin/python gap_fill_discovery.py select --cuisine caribbean
"""
import argparse
import collections
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent.parent
DATA_DIR = REPO_ROOT / "data" / "gap-fill"
SEEDS_DIR = DATA_DIR / "seeds"

# Gap cuisines and ingestion quotas, from INGESTION_CUISINE_GAPS.md.
GAP_CUISINES = {
    "caribbean": {"label": "Caribbean", "quota": 24, "kind": "cuisine"},
    "middle-eastern": {"label": "Middle Eastern", "quota": 15, "kind": "cuisine"},
    "thai": {"label": "Thai", "quota": 15, "kind": "cuisine"},
    "korean": {"label": "Korean", "quota": 15, "kind": "cuisine"},
    "indian": {"label": "Indian", "quota": 18, "kind": "cuisine"},
}

# Meal-type gaps (P-12). Same machinery, different axis: a gap is "a slice of the catalog we
# are short of", and breakfast is short in exactly the way Caribbean was — 55 recipes against
# dinner's 512. The axis matters for the dedupe and the inventory, not for search or scoring,
# so the only thing that changes is how members_of_gap() picks the slice.
GAP_MEAL_TYPES = {
    "breakfast": {"label": "Breakfast", "quota": 30, "kind": "meal_type", "meal_type": "breakfast"},
}

# Dish-list gaps (P-04b). A third axis: not a slice of the catalog at all, but a named list of
# dishes we want to exist. `members_of_gap` has nothing to report for these — the gap IS the seed
# file — so inventory says so rather than printing a misleading "0 recipes".
GAP_DISH_LISTS = {
    # `rail` is the super-easy rail's own query, applied as a selection filter — see
    # cmd_select_dish_list. Keep these three numbers in sync with the backend query.
    "easy-essentials": {
        "label": "Easy Essentials", "quota": 9, "kind": "dish_list",
        # No step limit, deliberately. A <=6 step cut excluded exactly three recipes in prod —
        # 3-Ingredient Peanut Butter Cookies, Grilled Cheese and Waffle Breakfast Sandwich — all
        # false negatives, and two of them the most iconic super-easy dishes we have. Step count
        # measures how granularly a source wrote its instructions, not how hard the dish is.
        "rail": {"max_minutes": 20, "max_ingredients": 8, "max_steps": 99},
        "seeded_dishes": (
            "bacon and egg sandwich", "grilled cheese sandwich", "blt sandwich",
            "mashed potatoes", "roast chicken breast", "pan fried pork chops",
            "cheese pizza", "buttered egg noodles", "no bake energy bites",
        ),
    },
}

GAPS = {**GAP_CUISINES, **GAP_MEAL_TYPES, **GAP_DISH_LISTS}


def members_of_gap(catalog, key):
    """The catalog rows already inside a gap — by cuisine alias, or by meal_type."""
    cfg = GAPS[key]
    if cfg["kind"] == "dish_list":
        return []  # defined by its seed file, not by a catalog slice
    if cfg["kind"] == "meal_type":
        want = cfg["meal_type"]
        return [r for r in catalog if (r.get("meal_type") or "").strip().lower() == want]
    return [r for r in catalog if gap_bucket(r.get("cuisine") or "") == key]
# Sub-cuisine labels that count toward a gap bucket when reading the catalog.
CUISINE_ALIASES = {
    "middle-eastern": ["middle eastern", "turkish", "persian", "lebanese", "israeli",
                       "palestinian", "moroccan", "egyptian", "iraqi", "syrian"],
    "caribbean": ["caribbean", "jamaican", "trinidadian", "haitian", "cuban"],
    "thai": ["thai"],
    "korean": ["korean"],
    "indian": ["indian", "south asian", "punjabi", "british-indian"],
}

# Pantry staples real users stock (gaps doc, n=16 kitchens). Normalized
# substring match against ingredient names.
PANTRY_STAPLES = [
    "olive oil", "vegetable oil", "canola oil", "oil", "salt", "pepper",
    "garlic", "butter", "rice", "sugar", "milk", "onion", "soy sauce",
    "egg", "flour", "paprika", "garlic powder", "onion powder",
    "chili powder", "turmeric", "cumin", "cinnamon", "cayenne", "ginger",
    "cardamom", "water", "vinegar", "ketchup", "mayonnaise", "honey",
    "brown sugar", "baking powder", "baking soda", "oregano", "thyme",
    "bay leaf", "bay leaves", "curry powder", "allspice", "coriander",
    "chicken stock", "chicken broth", "stock", "broth", "tomato paste",
]
# Fresh proteins (not inventoried by users; recipes should need <= 2).
PROTEINS = [
    "chicken", "beef", "pork", "lamb", "goat", "oxtail", "turkey", "duck",
    "shrimp", "prawn", "salmon", "tilapia", "snapper", "cod", "mackerel",
    "saltfish", "salt fish", "whitefish", "fish", "tofu", "paneer", "tempeh",
]
# Dish archetypes for diversity scoring (first match wins).
ARCHETYPES = [
    ("curry", r"curry|massaman|panang|korma|tikka masala|butter chicken|vindaloo"),
    ("stew-braise", r"stew|brais|oxtail|jjigae|tagine|ropa|pelau|goulash"),
    ("soup", r"soup|tom yum|tom kha|shorba|broth|rasam|sundubu"),
    ("rice-dish", r"rice|biryani|bibimbap|pilaf|pulao|jollof|congee"),
    ("noodle", r"noodle|pad thai|pad see|japchae|chow|lo mein|drunken"),
    ("grill-roast", r"jerk|grill|kebab|kabob|tandoori|bulgogi|satay|kofta|shish|galbi|roast"),
    ("fried", r"fried|fritter|katsu|pakora|65\b|karaage|tostones"),
    ("salad", r"salad|larb|som tum|tabbouleh|fattoush|slaw"),
    ("street-wrap", r"shawarma|taco|doubles|roti|arayes|patty|wrap|gyro|pita"),
    ("egg-dish", r"shakshuka|egg|omelet|frittata|tamagoyaki|menemen|cilbir|\u00e7\u0131lb\u0131r"),
    ("veg-side", r"plantain|callaloo|cabbage|aloo|bhindi|saag|dal|chana|beans|lentil"),
    # Breakfast archetypes (P-12). Appended, not inserted, so first-match-wins leaves every
    # existing cuisine bucket exactly as it was — none of the rules above can match these words.
    # They exist because the selection penalty is -1.2 per repeat of an archetype, and without
    # them every pancake scores as "other": the catalog already holds NINE pancake variants and
    # six waffles out of 55 breakfast recipes, which is the shape of the gap, not a fix for it.
    ("pancake", r"pancake|hotcake|dutch baby|blini|crepe|cr\u00eape|pajeon|okonomiyaki"),
    ("waffle", r"waffle|gaufre"),
    ("french-toast", r"french toast|torrija|pain perdu"),
    ("porridge-oats", r"oatmeal|overnight oats|porridge|congee|jook|juk|grits|muesli|granola|chia pudding"),
    ("breakfast-sandwich", r"breakfast sandwich|bagel|biscuit sandwich|croissant sandwich|mcmuffin|toastie"),
    ("toast-tartine", r"toast|tartine|manakish|manaqish|smorrebrod|sm\u00f8rrebr\u00f8d|molletes"),
    ("pastry-bake", r"muffin|scone|croissant|danish|babka|cinnamon roll|coffee cake|strata|quiche|frittata"),
    ("smoothie-drink", r"smoothie|juice|lassi|shake|latte|chai"),
    ("yogurt-bowl", r"parfait|yogurt|yoghurt|skyr|labneh|acai|a\u00e7a\u00ed"),
    ("hash-skillet", r"hash|skillet|scramble|silog|tocilog|tapsilog|longsilog|fry-up|full english"),
]
JUNK_DOMAINS = {
    "youtube.com", "youtu.be", "pinterest.com", "reddit.com", "facebook.com",
    "instagram.com", "tiktok.com", "quora.com", "amazon.com", "wikipedia.org",
    "wikihow.com", "twitter.com", "x.com", "yelp.com", "tripadvisor.com",
    "doordash.com", "ubereats.com", "etsy.com", "walmart.com", "target.com",
}
def is_junk_domain(dom: str) -> bool:
    """True for a junk source, INCLUDING its regional and language subdomains.

    An exact-match check let en.wikipedia.org and au.pinterest.com straight through — both
    showed up in a real breakfast pool. Matching the registrable suffix catches every
    fr./de./au./en. variant of the same non-recipe site.
    """
    return any(dom == j or dom.endswith("." + j) for j in JUNK_DOMAINS)


BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Dest": "document",
    "Upgrade-Insecure-Requests": "1",
}


def load_env():
    for name in ("local.env", "prod.env"):
        p = REPO_ROOT / name
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            break


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).strip()


def norm_tokens(s: str) -> frozenset:
    drop = {"the", "a", "an", "and", "with", "easy", "best", "quick", "simple",
            "recipe", "homemade", "authentic", "classic"}
    return frozenset(t for t in norm(s).split() if t and t not in drop)


def archetype_of(name: str) -> str:
    n = norm(name)
    for label, pat in ARCHETYPES:
        if re.search(pat, n):
            return label
    return "other"


def is_staple(ing_name: str) -> bool:
    n = norm(ing_name)
    if not n:
        return True
    return any(re.search(rf"\b{re.escape(s)}\b", n) for s in PANTRY_STAPLES)


def proteins_in(ing_names) -> set:
    found = set()
    for ing in ing_names:
        n = norm(ing)
        for p in PROTEINS:
            if re.search(rf"\b{re.escape(p)}\b", n):
                found.add("fish" if p in ("salmon", "tilapia", "snapper", "cod",
                                          "mackerel", "saltfish", "salt fish",
                                          "whitefish", "fish") else p)
                break
    return found


def gap_bucket(cuisine: str):
    c = norm(cuisine)
    for key, aliases in CUISINE_ALIASES.items():
        if any(c == a or a in c for a in aliases):
            return key
    return None


# --------------------------------------------------------------------------
# Step 1: inventory
# --------------------------------------------------------------------------

def ekitchen_login(base):
    r = requests.post(f"{base}/auth/login",
                      json={"email": os.environ["EKITCHEN_ADMIN_EMAIL"],
                            "password": os.environ["EKITCHEN_ADMIN_PASSWORD"]},
                      timeout=45)
    r.raise_for_status()
    tok = r.json().get("access_token") or r.json().get("token")
    if not tok:
        raise RuntimeError("no token from /auth/login")
    return {"Authorization": f"Bearer {tok}"}


def cmd_inventory(args):
    cache = DATA_DIR / "catalog.json"
    if cache.exists() and not args.refresh:
        catalog = json.loads(cache.read_text())
        print(f"(cached) {len(catalog)} recipes from {cache} — use --refresh to refetch\n")
    else:
        load_env()
        base = os.environ["EKITCHEN_BASE_URL"]
        headers = ekitchen_login(base)
        print(f"Fetching catalog from {base} ...")
        listing, offset = [], 0
        while True:
            batch = requests.get(f"{base}/global-recipes/",
                                 params={"limit": 200, "offset": offset},
                                 headers=headers, timeout=90).json() or []
            listing.extend(batch)
            if len(batch) < 200:
                break
            offset += 200
        print(f"  {len(listing)} recipes listed; fetching ingredient details ...")

        def detail(r):
            try:
                d = requests.get(f"{base}/global-recipes/{r['id']}",
                                 headers=headers, timeout=60).json()
                return {"id": r["id"], "name": r.get("name"),
                        "cuisine": r.get("cuisine"),
                        "meal_type": r.get("meal_type"),
                        "total_time_minutes": r.get("total_time_minutes"),
                        "dietary_classification": r.get("dietary_classification"),
                        "inspired_by_url": r.get("inspired_by_url"),
                        "ingredients": [i.get("name", "") for i in (d.get("ingredients") or [])]}
            except Exception as e:
                print(f"    detail failed for {r.get('name')}: {e}")
                return None

        catalog = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(detail, r) for r in listing]
            for i, f in enumerate(as_completed(futs), 1):
                row = f.result()
                if row:
                    catalog.append(row)
                if i % 100 == 0:
                    print(f"    {i}/{len(listing)} details fetched")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(catalog, indent=1))
        print(f"  wrote {cache}\n")

    # ---- analysis ----
    by_cuisine = collections.Counter((r.get("cuisine") or "Unknown").strip() for r in catalog)
    print("## Catalog by cuisine (top 15)")
    for c, n in by_cuisine.most_common(15):
        print(f"  {c:<22} {n}")

    by_meal = collections.Counter((r.get("meal_type") or "Unknown").strip() for r in catalog)
    print("\n## Catalog by meal type")
    for m, n in by_meal.most_common():
        print(f"  {m:<22} {n}")

    print("\n## Gaps — what we HAVE (dish + archetype)")
    for key, cfg in GAPS.items():
        have = members_of_gap(catalog, key)
        arch = collections.Counter(archetype_of(r["name"]) for r in have)
        print(f"\n### {cfg['label']}: {len(have)} recipes "
              f"(quota: +{cfg['quota']})  archetypes: {dict(arch)}")
        if cfg["kind"] == "dish_list":
            print("    (a named dish list — see the seeds file; nothing to inventory)")
            continue
        if cfg["kind"] == "meal_type":
            # For a meal-type gap the cuisine spread is the story. Breakfast is 75% American,
            # and the feed's cuisine-diversity rerank penalises repeats — so a lopsided pool
            # partly suppresses itself. Seeds should be read against this line, not the count.
            cs = collections.Counter((r.get("cuisine") or "Unknown").strip() for r in have)
            print(f"    cuisines: {dict(cs.most_common(8))}")
        for r in sorted(have, key=lambda x: x["name"] or ""):
            t = r.get("total_time_minutes") or 0
            print(f"    - {r['name']}  [{r.get('cuisine')}, {t}min]")
    print("\nNext: review/edit seeds in data/gap-fill/seeds/<gap>.txt, then run `search`.")


# --------------------------------------------------------------------------
# Step 2: search
# --------------------------------------------------------------------------

def cmd_search(args):
    from ddgs import DDGS  # pip install ddgs
    cuisine = args.cuisine
    seeds_file = SEEDS_DIR / f"{cuisine}.txt"
    if not seeds_file.exists():
        sys.exit(f"no seeds file: {seeds_file}")
    seeds = [l.strip() for l in seeds_file.read_text().splitlines()
             if l.strip() and not l.startswith("#")]

    catalog = json.loads((DATA_DIR / "catalog.json").read_text())
    existing = [norm_tokens(r["name"]) for r in catalog if r.get("name")]

    def is_dupe(dish):
        st = norm_tokens(dish)
        return any(len(st & e) >= max(2, len(st) - 1) and len(st | e) - len(st & e) <= 2
                   for e in existing)

    pool, domain_count = [], collections.Counter()
    per_domain_cap = args.domain_cap
    with DDGS() as ddgs:
        for dish in seeds:
            if is_dupe(dish):
                print(f"  SKIP (already in catalog): {dish}")
                continue
            q = f"{dish} recipe"
            try:
                results = list(ddgs.text(q, max_results=args.per_dish))
            except Exception as e:
                print(f"  search failed for '{q}': {e}")
                continue
            kept = 0
            for res in results:
                url = res.get("href") or ""
                dom = urlparse(url).netloc.lower().removeprefix("www.")
                if not dom or is_junk_domain(dom):
                    continue
                if any(seg in url.lower() for seg in ("/category/", "/tag/", "/collection",
                                                      "/recipes/", "/search", "/best-")):
                    # listing-ish pages; individual recipes only
                    if not re.search(r"/recipes?/[a-z0-9-]{8,}", url.lower()):
                        continue
                if domain_count[dom] >= per_domain_cap:
                    continue
                pool.append({"dish": dish, "url": url, "domain": dom,
                             "title": res.get("title", "")})
                domain_count[dom] += 1
                kept += 1
            print(f"  {dish}: {kept} urls kept")
            time.sleep(args.delay)

    out = DATA_DIR / f"pool_{cuisine}.json"
    out.write_text(json.dumps(pool, indent=1))
    print(f"\n{len(pool)} URLs from {len(domain_count)} domains -> {out}")
    print("top domains:", domain_count.most_common(10))


# --------------------------------------------------------------------------
# Step 3: score (metadata-only scrape, $0)
# --------------------------------------------------------------------------

def scrape_meta(url):
    from recipe_scrapers import scrape_html
    resp = requests.get(url, headers=BROWSER_HEADERS, timeout=20)
    resp.raise_for_status()
    scraper = None
    try:
        scraper = scrape_html(html=resp.text, org_url=url)
    except Exception:
        scraper = scrape_html(html=resp.text, org_url=url, wild_mode=True)

    def safe(fn, default=None):
        try:
            v = fn()
            return v if v not in (None, "") else default
        except Exception:
            return default
    title = safe(scraper.title)
    ings = safe(scraper.ingredients, []) or []
    steps = safe(scraper.instructions_list, []) or []
    total = safe(scraper.total_time, 0) or 0
    if not title or not ings or not steps:
        raise ValueError("incomplete recipe data")
    return {"title": title, "total_time": int(total), "ingredients": ings,
            "n_steps": len(steps)}


def cmd_score(args):
    cuisine = args.cuisine
    pool = json.loads((DATA_DIR / f"pool_{cuisine}.json").read_text())
    scored, failed = [], 0

    def work(cand):
        try:
            meta = scrape_meta(cand["url"])
        except Exception as e:
            return cand["url"], str(e)[:90], None
        ings = meta["ingredients"]
        staple_hits = [i for i in ings if is_staple(i)]
        fresh = [i for i in ings if not is_staple(i)]
        prots = proteins_in(ings)
        return None, None, {**cand, **meta,
                            "n_ingredients": len(ings),
                            "pantry_frac": round(len(staple_hits) / max(1, len(ings)), 2),
                            "fresh": fresh,
                            "proteins": sorted(prots),
                            "archetype": archetype_of(cand["dish"] + " " + meta["title"])}

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(work, c) for c in pool]
        for f in as_completed(futs):
            url, err, row = f.result()
            if row:
                scored.append(row)
            else:
                failed += 1
                print(f"  drop {url}: {err}")

    out = DATA_DIR / f"scored_{cuisine}.json"
    out.write_text(json.dumps(scored, indent=1))
    print(f"\nscored {len(scored)} / dropped {failed} -> {out}")


# --------------------------------------------------------------------------
# Step 4: select (basket-aware greedy)
# --------------------------------------------------------------------------

def fresh_key(ing: str) -> str:
    """Collapse an ingredient line to a coarse item key ('2 ripe plantains, sliced'
    -> 'plantain')."""
    n = norm(ing)
    n = re.sub(r"\b(\d+|half|quarter|cup|cups|tbsp|tablespoon|tablespoons|tsp|teaspoon|"
               r"teaspoons|ounce|ounces|oz|pound|pounds|lb|lbs|gram|grams|g|kg|ml|liter|"
               r"litre|large|small|medium|fresh|chopped|sliced|diced|minced|grated|ripe|"
               r"boneless|skinless|ground|of|to|taste|optional|finely|roughly|cut|into|"
               r"pieces|divided|plus|more|for|serving|about|inch|can|cans|package)\b", " ", n)
    toks = [t for t in n.split() if len(t) > 2]
    return " ".join(toks[-2:]) if toks else n


# Appliance-specific and variant recipes are fine in a cuisine gap and wrong in a dish list: the
# point of "Easy Essentials" is the dish everyone means, cookable with a pan. An Instant Pot mash
# is a different recipe wearing the same name.
APPLIANCE_RE = re.compile(r"\b(instant pot|air.?fry|slow.?cook|crock.?pot|sous vide|pressure cook|"
                          r"bread machine|microwave)\w*", re.I)


def cmd_select_dish_list(args, cfg, scored):
    """Selection for a named dish list (P-04b), which wants the opposite of the cuisine heuristic.

    A cuisine gap is a shape problem — spread the archetypes, share a shopping basket, avoid a
    tenth pancake. A dish list has already decided what it wants; the dishes ARE the diversity,
    and `dish_seen` alone enforces it. Reusing the cuisine scorer here actively hurts, because its
    -1.2 archetype penalty demotes the second recipe of any archetype regardless of quality: it
    picked a 6-ingredient Instant Pot mash over allrecipes' 5-ingredient "Best Mashed Potatoes"
    purely because "other" had been used once.

    So rank on what "easy essential" actually means — pantry-heavy, few ingredients, few steps,
    quick, no special appliance — and keep only the source diversity that matters (one domain).
    """
    # The rail rule is a HARD filter, not a preference. These recipes exist to populate the
    # super-easy rail, whose query is difficulty='Easy' AND <=20min AND <=8 ingredients AND
    # <=6 steps. A candidate that misses it would be scraped, paid for, and then never appear on
    # the rail it was ingested for — so it is worth nothing here however good a recipe it is.
    # A dish with no passing candidate is reported and DROPPED, not downgraded into the run.
    rail = cfg.get("rail")
    best, used_domains = [], collections.Counter()
    by_dish, rejected = collections.defaultdict(list), collections.defaultdict(list)
    for r in scored:
        if rail:
            why = []
            # An appliance recipe is not an "easy essential" — it is a different recipe wearing the
            # same name, and it needs equipment the rail cannot assume. Rejecting it is what makes
            # a dish drop out honestly instead of being filled by the only thing that could pass:
            # mashed potatoes cannot be done in 20 minutes without a pressure cooker, so the rule
            # correctly says mashed potatoes is not a super-easy recipe.
            if APPLIANCE_RE.search(r["title"]):
                why.append("appliance")
            if not r["total_time"] or r["total_time"] > rail["max_minutes"]:
                why.append(f"{r['total_time'] or '?'}min")
            if r["n_ingredients"] > rail["max_ingredients"]:
                why.append(f"{r['n_ingredients']}ing")
            if r["n_steps"] > rail["max_steps"]:
                why.append(f"{r['n_steps']}st")
            if why:
                rejected[r["dish"]].append((r["title"], ",".join(why), r["domain"]))
                continue
        by_dish[r["dish"]].append(r)

    for dish in sorted(by_dish):
        def score(r):
            s = 2.0 * r["pantry_frac"]
            s -= 0.15 * r["n_ingredients"]
            s -= 0.10 * r["n_steps"]
            if r["total_time"] and r["total_time"] <= 30:
                s += 1.0
            if APPLIANCE_RE.search(r["title"]):
                s -= 2.0
            s -= 0.6 * used_domains[r["domain"]]
            return s

        pick = max(by_dish[dish], key=score)
        used_domains[pick["domain"]] += 1
        best.append(pick)

    out = DATA_DIR / f"selected_{args.cuisine}.json"
    out.write_text(json.dumps(best, indent=1))
    print(f"## Selected {len(best)}/{cfg['quota']} for {cfg['label']}\n")
    for r in best:
        print(f"  {r['dish'][:26]:<26} {r['title'][:44]:<44} {r['total_time'] or '?':>3}min  "
              f"pantry {int(r['pantry_frac']*100):>3}%  {r['n_ingredients']:>2}ing {r['n_steps']:>2}st  "
              f"{r['domain']}")
    seeded = {r["dish"] for r in scored}
    for dish in sorted(d for d in cfg.get("seeded_dishes", ()) if d not in seeded):
        print(f"\n  NOTHING SCRAPEABLE AT ALL for {dish!r} — every search result failed to scrape")
    for dish in sorted(set(rejected) - set(by_dish)):
        print(f"\n  NO CANDIDATE PASSES THE RAIL RULE for {dish!r} — dropping it:")
        for title, why, dom in sorted(rejected[dish], key=lambda x: x[0])[:6]:
            print(f"      {title[:44]:46s} {why:16s} {dom}")
    print(f"\n  distinct domains: {len({r['domain'] for r in best})}")
    print(f"\n-> {out}")


def cmd_select(args):
    cuisine = args.cuisine
    cfg = GAPS[cuisine]
    scored = json.loads((DATA_DIR / f"scored_{cuisine}.json").read_text())
    if cfg["kind"] == "dish_list":
        return cmd_select_dish_list(args, cfg, scored)

    # hard filters
    pool = []
    for r in scored:
        if len(r["proteins"]) > 2:
            continue
        if r["total_time"] > 60:
            continue
        pool.append(r)

    selected, basket_fresh, seen_keys = [], collections.Counter(), set()
    arch_count = collections.Counter()
    sig_used, sig_max = 0, args.signature_max
    dish_seen = set()

    while pool and len(selected) < cfg["quota"]:
        def score(r):
            keys = {fresh_key(i) for i in r["fresh"]}
            overlap = len([k for k in keys if basket_fresh[k] > 0])
            new_rare = len([k for k in keys if k not in seen_keys])
            s = 2.0 * r["pantry_frac"]
            s += 0.8 * (overlap / max(1, len(keys)))
            s -= 0.5 * (new_rare / max(1, len(keys)))
            s -= 1.2 * arch_count[r["archetype"]]
            if r["total_time"] and r["total_time"] <= 30:
                s += 0.8
            elif r["total_time"] > 30 and sig_used >= sig_max:
                s -= 99  # signature budget spent
            if norm_tokens(r["dish"]) in dish_seen:
                s -= 99  # one recipe per dish
            return s

        pool.sort(key=score, reverse=True)
        pick = pool.pop(0)
        if score(pick) < -50:
            break
        selected.append(pick)
        dish_seen.add(norm_tokens(pick["dish"]))
        arch_count[pick["archetype"]] += 1
        if pick["total_time"] > 30:
            sig_used += 1
        for i in pick["fresh"]:
            k = fresh_key(i)
            basket_fresh[k] += 1
            seen_keys.add(k)

    out = DATA_DIR / f"selected_{cuisine}.json"
    out.write_text(json.dumps(selected, indent=1))

    print(f"## Selected {len(selected)}/{cfg['quota']} for {cfg['label']}\n")
    for r in selected:
        print(f"  {r['title'][:58]:<58} {r['total_time']:>3}min  "
              f"pantry {int(r['pantry_frac']*100):>3}%  {','.join(r['proteins']) or '-':<14} "
              f"{r['archetype']:<12} {r['domain']}")
    print(f"\n  archetype spread: {dict(arch_count)}")
    print(f"  >30min signatures used: {sig_used}/{sig_max}")
    shared = [k for k, n in basket_fresh.most_common(15) if n >= 2]
    print(f"  shared fresh ingredients (2+ recipes): {shared}")
    print(f"  distinct domains: {len({r['domain'] for r in selected})}")
    print(f"\n-> {out}")
    print("Ingest with: urls = [r['url'] for r in selected]")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inventory"); p.add_argument("--refresh", action="store_true")
    for name in ("search", "score", "select"):
        p = sub.add_parser(name)
        p.add_argument("--gap", "--cuisine", dest="cuisine", required=True,
                       choices=list(GAPS), metavar="GAP")
        if name == "search":
            p.add_argument("--per-dish", type=int, default=8)
            p.add_argument("--domain-cap", type=int, default=4)
            p.add_argument("--delay", type=float, default=1.5)
        if name == "select":
            p.add_argument("--signature-max", type=int, default=5)
    args = ap.parse_args()
    {"inventory": cmd_inventory, "search": cmd_search,
     "score": cmd_score, "select": cmd_select}[args.cmd](args)


if __name__ == "__main__":
    main()
