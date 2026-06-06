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
    "caribbean": {"label": "Caribbean", "quota": 24},
    "middle-eastern": {"label": "Middle Eastern", "quota": 15},
    "thai": {"label": "Thai", "quota": 15},
    "korean": {"label": "Korean", "quota": 15},
    "indian": {"label": "Indian", "quota": 18},
}
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
    ("egg-dish", r"shakshuka|egg|omelet|frittata"),
    ("veg-side", r"plantain|callaloo|cabbage|aloo|bhindi|saag|dal|chana|beans|lentil"),
]
JUNK_DOMAINS = {
    "youtube.com", "youtu.be", "pinterest.com", "reddit.com", "facebook.com",
    "instagram.com", "tiktok.com", "quora.com", "amazon.com", "wikipedia.org",
    "wikihow.com", "twitter.com", "x.com", "yelp.com", "tripadvisor.com",
    "doordash.com", "ubereats.com", "etsy.com", "walmart.com", "target.com",
}
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

    print("\n## Gap cuisines — what we HAVE (dish + archetype)")
    for key, cfg in GAP_CUISINES.items():
        have = [r for r in catalog if gap_bucket(r.get("cuisine") or "") == key]
        arch = collections.Counter(archetype_of(r["name"]) for r in have)
        print(f"\n### {cfg['label']}: {len(have)} recipes "
              f"(quota: +{cfg['quota']})  archetypes: {dict(arch)}")
        for r in sorted(have, key=lambda x: x["name"] or ""):
            t = r.get("total_time_minutes") or 0
            print(f"    - {r['name']}  [{r.get('cuisine')}, {t}min]")
    print("\nNext: review/edit seeds in data/gap-fill/seeds/<cuisine>.txt, then run `search`.")


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
                if not dom or dom in JUNK_DOMAINS:
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


def cmd_select(args):
    cuisine = args.cuisine
    cfg = GAP_CUISINES[cuisine]
    scored = json.loads((DATA_DIR / f"scored_{cuisine}.json").read_text())

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
        p.add_argument("--cuisine", required=True, choices=list(GAP_CUISINES))
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
