#!/usr/bin/env python3
"""
URL-driven ("browse the site") ingestion. Instead of guessing dish names and searching
for them, this harvests recipe URLs directly from Tasty/EatingWell *listing* pages
(topic / trending / latest / category) and ingests those real URLs. Eliminates the
no_url problem and surfaces actually-popular recipes.

Reuses the existing orchestrator wholesale:
  - autonomous_ingest.preflight_check        — dependency gate (auth, OpenAI, image model)
  - PlaywrightRecipeExtractor                 — harvest /recipe/ URLs from any page
  - autonomous_ingest.fetch_existing_recipe_names / is_duplicate — pre-scrape dedup by name
  - autonomous_ingest._ingest_one             — per-URL scrape -> enrich -> image -> create

Config (jobs/<name>.json):
  {
    "job_name": "...",
    "listing_urls": ["https://tasty.co/topic/dinner", "https://tasty.co/latest"],
    "auto_discover_tasty_topics": true,     # also pull /topic/<slug> links off tasty.co
    "per_page": 40,                          # max recipe URLs to harvest per listing page
    "target_count": 60, "max_cost_usd": 12.0, "est_cost_per_recipe_usd": 0.20,
    "concurrency": 3, "scrape_retries": 2, "dedupe_against_catalog": true
  }

Usage:
  ../../venv/bin/python -u harvest_ingest.py --config jobs/<name>.json [--dry-run | --canary N] [--skip-preflight]
"""
import argparse
import os
import sys
import time
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
import autonomous_ingest as ai  # reuse preflight, dedup, _ingest_one, report types, extractor


# Sweet/dessert classifier for the "savory-only" pass. Matches on the slug-derived name
# (cheap, pre-scrape). Conservative: drops clear sweets; keeps savory pies/breads
# (chicken pot pie, garlic bread, cornbread) by only flagging sweet-qualified pie/bread.
# Stem matching (no trailing \b) so plurals are caught: "brownie" -> "brownies",
# "pancake" -> "pancakes", "cinnamon roll" -> "cinnamon rolls", "blondie" -> "blondies".
# Deliberately NO bare "cake"/"pie"/"bread"/"honey" (would drop savory crab cakes, pot
# pie, garlic bread, honey-garlic ribs) — those are handled by _SWEET_PIE_BREAD.
_SWEET = re.compile(
    r"(brownie|cookie|cupcake|cheesecake|shortcake|pancake|muffin|crepe|smoothie|"
    r"slushie|slush|milkshake|latte|whipped\s*coffee|macaron|macaroon|cinnamon\s*roll|"
    r"sweet\s*roll|blondie|waffle|french\s*toast|energy\s*bite|dessert|donut|doughnut|"
    r"pudding|\btart|custard|frosting|icing|ice\s*cream|biscotti|fudge|\bcandy|caramel|"
    r"marshmallow|sundae|parfait|mousse|truffle|churro|cobbler|crumble|meringue|toffee|"
    r"praline|sorbet|gelato|popsicle|baklava|chocolate|peanut\s*butter|nutella)", re.I)
_SWEET_PIE_BREAD = re.compile(
    r"\b(apple|pumpkin|pecan|cherry|key\s*lime|banana|chocolate|berry|blueberry|"
    r"strawberry|peach|lemon|sweet|cream|monkey|zucchini)\s+(pie|bread|loaf)\b", re.I)


def is_sweet(name: str) -> bool:
    return bool(_SWEET.search(name) or _SWEET_PIE_BREAD.search(name))


def slug_to_name(recipe_url: str) -> str:
    """/recipe/creamy-tuscan-chicken -> 'Creamy Tuscan Chicken' (display + dedup key)."""
    # eatingwell is /recipe/<id>/<slug>/ — the numeric id is its own path segment, so the
    # last segment is already the clean slug. Do NOT strip leading digits (tasty slugs like
    # "2-ingredient-pasta" / "100-layer-lasagna" legitimately start with a number).
    slug = urlparse(recipe_url).path.rstrip("/").split("/")[-1]
    return re.sub(r"\s+", " ", slug.replace("-", " ").replace("_", " ")).strip().title()


def discover_tasty_topics(max_topics: int = 25) -> list:
    """Grab /topic/<slug> listing URLs off the Tasty homepage (JS-rendered, needs Playwright)."""
    topics = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://tasty.co/", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3500)
            hrefs = page.eval_on_selector_all("a[href*='/topic/']", "els => els.map(e => e.getAttribute('href'))")
            browser.close()
        seen = set()
        for h in hrefs or []:
            if not h:
                continue
            path = urlparse(h).path
            m = re.match(r"^/topic/([a-z0-9][a-z0-9_-]+)/?$", path, re.I)
            if m and m.group(1).lower() != "community" and path not in seen:
                seen.add(path)
                topics.append(f"https://tasty.co{path}")
        topics.append("https://tasty.co/latest")
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️  topic auto-discovery failed: {str(e)[:80]}")
    return topics[:max_topics]


def harvest(extractor, listing_urls: list, per_page: int) -> list:
    seen, out = set(), []
    for lu in listing_urls:
        try:
            urls = extractor.extract_recipe_urls_from_search_page(lu, per_page)
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️  harvest failed on {lu}: {str(e)[:70]}")
            urls = []
        n_new = 0
        for u in urls:
            if u not in seen:
                seen.add(u)
                out.append(u)
                n_new += 1
        print(f"   📥 {lu} -> {n_new} new recipe URLs (running total {len(out)})")
    return out


def run_job(config: dict, dry_run: bool, canary):
    job_name = config["job_name"]
    base_url = os.environ.get("EKITCHEN_BASE_URL", "https://ekitchen-production.up.railway.app")
    email = os.environ.get("EKITCHEN_ADMIN_EMAIL", "")
    password = os.environ.get("EKITCHEN_ADMIN_PASSWORD", "")
    per_page = int(config.get("per_page", 40))
    target = int(config.get("target_count", 0) or 0)
    max_cost = float(config.get("max_cost_usd", 0) or 0)
    est_cost = float(config.get("est_cost_per_recipe_usd", 0.20))
    concurrency = max(1, int(config.get("concurrency", 3)))

    print(f"\n{'='*70}\n🌐 HARVEST INGEST: {job_name}\n{'='*70}")
    print(f"   backend : {base_url}")
    print(f"   mode    : {'DRY RUN' if dry_run else ('CANARY ' + str(canary)) if canary else 'FULL RUN'}")

    # 1) Build listing-URL set
    listing = list(config.get("listing_urls", []))
    if config.get("auto_discover_tasty_topics"):
        discovered = discover_tasty_topics()
        print(f"   discovered {len(discovered)} tasty topic/listing pages")
        for d in discovered:
            if d not in listing:
                listing.append(d)
    print(f"   listing pages: {len(listing)}")

    # 2) Harvest recipe URLs
    extractor = ai.PlaywrightRecipeExtractor()
    ai._MIN_DOMAIN_INTERVAL = float(config.get("min_domain_interval_seconds", 4.0))
    recipe_urls = harvest(extractor, listing, per_page)
    print(f"\n   harvested {len(recipe_urls)} unique recipe URLs total")

    # 3) Pre-scrape dedup against live catalog (by slug-derived name)
    existing = []
    if config.get("dedupe_against_catalog", True) and email and password:
        try:
            existing = ai.fetch_existing_recipe_names(base_url, email, password)
            print(f"   catalog : {len(existing)} existing recipes")
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️  catalog dedup fetch failed ({str(e)[:60]}); relying on processor dedup")

    net_new = []
    for u in recipe_urls:
        name = slug_to_name(u)
        if existing and ai.is_duplicate(name, existing):
            continue
        net_new.append((name, u))
    print(f"   net-new after name-dedup: {len(net_new)} (skipped {len(recipe_urls) - len(net_new)} likely dupes)")

    if config.get("exclude_sweet"):
        before = len(net_new)
        net_new = [(n, u) for n, u in net_new if not is_sweet(n)]
        print(f"   savory-only filter: kept {len(net_new)} savory, dropped {before - len(net_new)} sweet/dessert")

    report = ai.JobReport(job_name=job_name, config=config, started_at=time.strftime("%Y-%m-%dT%H:%M:%S"))

    if dry_run:
        for name, u in net_new:
            report.records.append(ai.RecipeRecord(dish=name, url=u, status="dry_run"))
        ai._write_report(report)
        print(f"\n{'='*70}\n📊 DRY RUN: {job_name}\n{'='*70}")
        print(json.dumps({"listing_pages": len(listing), "harvested": len(recipe_urls),
                          "net_new": len(net_new), "est_cost_if_run": round(len(net_new) * est_cost, 2)}, indent=2))
        for name, u in net_new[:20]:
            print(f"   + {name}  ({u})")
        return report

    # 4) Ingest net-new URLs (reuse _ingest_one: throttle + retry + dedup + image + create)
    image_dir = config.get("image_dir") or str(THIS_DIR / "generated-recipe-images" / "harvest" / job_name)
    os.makedirs(image_dir, exist_ok=True)
    config["_image_dir"] = image_dir

    queue = net_new[:canary] if canary else net_new
    created = [0]
    spent = [0.0]

    def work(item):
        name, u = item
        if max_cost and spent[0] >= max_cost:
            return ai.RecipeRecord(dish=name, url=u, status="skipped_budget")
        rec = ai._ingest_one(name, [u], config, est_cost)
        if rec.status == "created":
            created[0] += 1
            spent[0] += est_cost
        report.records.append(rec)
        ai._write_report(report)
        mark = {"created": "✅", "skipped_dupe": "⏭️", "failed": "❌"}.get(rec.status, "•")
        print(f"   {mark} {rec.status:13} {name}  (created {created[0]}, ~${spent[0]:.2f})")
        return rec

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = []
        for item in queue:
            if target and created[0] >= target:
                break
            if max_cost and spent[0] >= max_cost:
                break
            futs.append(ex.submit(work, item))
        for _ in as_completed(futs):
            pass

    print(f"\n{'='*70}\n📊 SUMMARY: {job_name}\n{'='*70}")
    from collections import Counter
    by = Counter(r.status for r in report.records)
    print(json.dumps({"harvested": len(recipe_urls), "net_new": len(net_new),
                      "by_status": dict(by), "created": created[0],
                      "est_cost_usd": round(spent[0], 2)}, indent=2))
    print(f"\n📄 report: {ai._report_path(job_name)}")
    return report


def main():
    ap = argparse.ArgumentParser(description="URL-driven (browse listing pages) recipe ingestion")
    ap.add_argument("--config", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--canary", type=int, default=None)
    ap.add_argument("--skip-preflight", action="store_true")
    args = ap.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    if not args.skip_preflight and not args.dry_run:
        if not ai.preflight_check(config):
            sys.exit(1)

    run_job(config, args.dry_run, args.canary)


if __name__ == "__main__":
    main()
