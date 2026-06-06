#!/usr/bin/env python3
"""
Autonomous Recipe Ingestion Orchestrator
=========================================

Config-driven, unattended ingestion: discovers recipe URLs for a list of dish
names, dedupes against the live eKitchen catalog, ingests each via the existing
DirectRecipeProcessor (parse -> enrich -> image -> create in eKitchen backend),
and tracks every result in a resumable JSON report.

This wraps two existing primitives:
  - SimplifiedRecipeDiscovery.find_recipe_url(dish)      -> recipe URL
  - DirectRecipeProcessor.process_recipe_autonomous(url) -> RecipeProcessingResult

Usage:
    source local.env          # (or prod.env) -- provides EKITCHEN_BASE_URL,
                              #  EKITCHEN_ADMIN_EMAIL/PASSWORD, OPENAI_API_KEY, etc.
    python3 autonomous_ingest.py --config jobs/launch-quick.json --dry-run
    python3 autonomous_ingest.py --config jobs/launch-quick.json --canary 5
    python3 autonomous_ingest.py --config jobs/launch-quick.json            # full run
    python3 autonomous_ingest.py --config jobs/launch-quick.json --resume   # continue

Safety:
  - --dry-run    : discover + dedupe + print the plan; ingest NOTHING.
  - --canary N   : ingest at most N recipes (staged rollout gate).
  - max_cost_usd : hard ceiling on ESTIMATED spend (per-recipe estimate; stops early).
  - dedupe       : skips dishes whose name already exists in the eKitchen catalog.
  - resumable    : re-running with --resume skips dishes already completed OK.

Discovery uses the stealth multi-query extractor against verified site templates
(verified_site_templates.json) — Tasty / SimplyRecipes / EatingWell by default.
Each dish is a search query; the first template yielding results wins.

Job config (JSON):
{
  "job_name": "launch-quick-weeknight",
  "dish_sources": ["data/quick-weeknight/dish-names.txt", "data/easy-essentials/dish-names.txt"],
  "search_templates": null,        // null = use verified_site_templates.json; or a list of "...{query}..." templates
  "max_urls_per_dish": 3,          // candidate URLs to try per dish (fallbacks if a scrape fails)
  "target_count": 90,
  "dedupe_against_catalog": true,
  "generate_image": true,
  "concurrency": 3,
  "max_cost_usd": 15.0,
  "est_cost_per_recipe_usd": 0.05,
  "user_id": null
}
"""

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests

# --- make repo modules importable (this file lives in tools/recipe-ingestion/) ---
THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(REPO_ROOT / "legacy/src/discovery"))

from services.recipe_processor import DirectRecipeProcessor  # noqa: E402
from playwright_url_extractor import PlaywrightRecipeExtractor  # noqa: E402

VERIFIED_TEMPLATES = THIS_DIR / "verified_site_templates.json"
REPORTS_DIR = THIS_DIR / "reports"

# Filler tokens stripped when comparing dish names to existing recipe names.
_STOP = set(
    "recipe the a an with and style homemade easy best classic authentic of in to "
    "my our chef john s simple quick".split()
)


def _norm_tokens(name: str) -> set:
    name = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    return {t for t in name.split() if t and t not in _STOP and len(t) > 2}


# ----------------------------- result tracking -------------------------------


@dataclass
class RecipeRecord:
    dish: str
    url: Optional[str] = None
    status: str = "pending"  # pending | created | skipped_dupe | no_url | failed | dry_run
    recipe_id: Optional[str] = None
    recipe_name: Optional[str] = None
    ingredients_processed: int = 0
    image_generated: bool = False
    processing_time_seconds: float = 0.0
    est_cost_usd: float = 0.0
    error: Optional[str] = None


@dataclass
class JobReport:
    job_name: str
    config: dict
    started_at: str
    records: List[RecipeRecord] = field(default_factory=list)

    def summary(self) -> dict:
        by_status: Dict[str, int] = {}
        for r in self.records:
            by_status[r.status] = by_status.get(r.status, 0) + 1
        return {
            "total_dishes": len(self.records),
            "by_status": by_status,
            "created": by_status.get("created", 0),
            "est_cost_usd": round(sum(r.est_cost_usd for r in self.records), 4),
        }


def _report_path(job_name: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR / f"{job_name}.json"


def _write_report(report: JobReport) -> None:
    """Crash-safe incremental write so progress is never lost mid-run."""
    path = _report_path(report.job_name)
    payload = {
        "job_name": report.job_name,
        "config": report.config,
        "started_at": report.started_at,
        "summary": report.summary(),
        "records": [asdict(r) for r in report.records],
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)


def _load_prior_records(job_name: str) -> Dict[str, RecipeRecord]:
    path = _report_path(job_name)
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    out = {}
    for rec in data.get("records", []):
        out[rec["dish"]] = RecipeRecord(**{k: rec.get(k) for k in RecipeRecord.__dataclass_fields__})
    return out


# ----------------------------- catalog dedupe --------------------------------


def _request_with_retry(method: str, url: str, *, attempts: int = 4, timeout: int = 60, **kwargs):
    """HTTP request with retry-on-transient-failure (timeouts, 5xx, conn errors).
    Prod (Railway) can be slow/cold-starting; one timeout shouldn't kill the run."""
    last = None
    for i in range(attempts):
        try:
            resp = requests.request(method, url, timeout=timeout, **kwargs)
            if resp.status_code >= 500:
                last = RuntimeError(f"HTTP {resp.status_code}")
                raise last
            resp.raise_for_status()
            return resp
        except Exception as e:  # noqa: BLE001 — retry any transient failure
            last = e
            if i < attempts - 1:
                time.sleep(3 * (i + 1))  # 3s, 6s, 9s backoff
    raise last


def fetch_existing_recipe_names(base_url: str, email: str, password: str) -> List[set]:
    """Authenticate against eKitchen and return token-sets of existing recipe names.
    Retries transient failures; raises only after exhausting attempts."""
    login = _request_with_retry(
        "POST", f"{base_url}/auth/login", json={"email": email, "password": password}, timeout=45
    )
    token = login.json().get("access_token") or login.json().get("token")
    if not token:
        raise RuntimeError("could not obtain access token from /auth/login response")

    headers = {"Authorization": f"Bearer {token}"}
    names: List[set] = []
    offset, limit = 0, 200
    while True:
        resp = _request_with_retry(
            "GET", f"{base_url}/global-recipes/?limit={limit}&offset={offset}",
            headers=headers, timeout=90,
        )
        batch = resp.json() or []
        for r in batch:
            toks = _norm_tokens(r.get("name", ""))
            if toks:
                names.append(toks)
        if len(batch) < limit:
            break
        offset += limit
    return names


def is_duplicate(dish: str, existing: List[set]) -> bool:
    st = _norm_tokens(dish)
    if not st:
        return False
    for ex in existing:
        inter = len(st & ex)
        if inter >= 2 and inter >= 0.6 * len(st):
            return True
        if len(st) == 1 and st <= ex:
            return True
    return False


# ----------------------------- orchestration ---------------------------------


def load_dishes(dish_sources: List[str]) -> List[str]:
    dishes: List[str] = []
    seen = set()
    for src in dish_sources:
        p = (REPO_ROOT / src) if not os.path.isabs(src) else Path(src)
        if not p.exists():
            print(f"⚠️  dish source not found: {p}")
            continue
        for line in p.read_text().splitlines():
            d = line.strip()
            if d and d.lower() not in seen:
                seen.add(d.lower())
                dishes.append(d)
    return dishes


def load_templates(config: dict) -> List[str]:
    """Search-URL templates to use: explicit config override, else the 'verified'
    set from verified_site_templates.json."""
    explicit = config.get("search_templates")
    if explicit:
        return list(explicit)
    data = json.loads(VERIFIED_TEMPLATES.read_text())
    return [t["url_template"] for t in data.get("verified", [])]


# Leading qualifiers stripped from a dish name before searching, so verbose names
# (e.g. "15-Minute Garlic Butter Shrimp") still match on sites with stricter search.
# Flavor descriptors (spicy/crispy/creamy) are kept — they're part of the dish.
_QUERY_QUALIFIER = re.compile(
    r"^(?:\d+[- ]?minute|quick|easy|simple|classic|homemade|the\s+best|best|authentic|"
    r"one[- ]?pan|one[- ]?pot|sheet[- ]?pan|weeknight)\s+", re.I)


def clean_query(dish: str) -> str:
    """Strip leading ease/time qualifiers to improve search hit-rate."""
    q = dish.strip()
    prev = None
    while prev != q:
        prev = q
        q = _QUERY_QUALIFIER.sub("", q).strip()
    return q or dish.strip()


def discover_candidates(extractor: PlaywrightRecipeExtractor, templates: List[str],
                        dish: str, max_urls: int) -> List[str]:
    """Search verified templates in priority order; return the first template's
    recipe URLs (prefers the highest-priority relevant source, minimizes scraping)."""
    q = clean_query(dish).replace(" ", "+")
    for tpl in templates:
        try:
            urls = extractor.extract_recipe_urls_from_search_page(tpl.format(query=q), max_urls)
        except Exception:  # noqa: BLE001
            urls = []
        if urls:
            return urls[:max_urls]
    return []


# Per-domain request stagger: serialize and space out requests to the same site
# so a pool of workers doesn't trigger burst bot-blocking (observed on SimplyRecipes
# when 3 workers scraped it concurrently). Cross-domain requests still run in parallel.
_MIN_DOMAIN_INTERVAL = 4.0  # seconds between same-domain scrapes; run_job may override
_DOMAIN_LOCKS: Dict[str, threading.Lock] = {}
_DOMAIN_LAST: Dict[str, float] = {}
_DOMAIN_GUARD = threading.Lock()


def _domain_throttle(url: str) -> None:
    """Block until >= _MIN_DOMAIN_INTERVAL has elapsed since the last request to
    this URL's domain. Serializes same-domain access across worker threads."""
    domain = urlparse(url).netloc.replace("www.", "")
    with _DOMAIN_GUARD:
        lock = _DOMAIN_LOCKS.setdefault(domain, threading.Lock())
    with lock:
        wait = _MIN_DOMAIN_INTERVAL - (time.time() - _DOMAIN_LAST.get(domain, 0.0))
        if wait > 0:
            time.sleep(wait)
        _DOMAIN_LAST[domain] = time.time()


# Thread-local processor: each worker authenticates once and reuses its own
# instance, avoiding shared auth-token races across threads.
_tls = threading.local()


def _worker_processor() -> DirectRecipeProcessor:
    if not hasattr(_tls, "proc"):
        _tls.proc = DirectRecipeProcessor(log_to_file=True)
    return _tls.proc


def _ingest_one(dish: str, urls: List[str], config: dict, est_cost: float) -> RecipeRecord:
    """Try candidate URLs for a dish in order until one ingests successfully.
    Per-domain stagger + retry-with-backoff guard against burst bot-blocking.
    Runs inside a worker thread with a thread-local processor."""
    rec = RecipeRecord(dish=dish)
    last_err = "no candidate urls"
    retries = int(config.get("scrape_retries", 2))
    backoff = float(config.get("scrape_backoff_seconds", 3.0))
    image_dir = config.get("_image_dir")
    for url in urls:
        rec.url = url
        for attempt in range(retries + 1):
            _domain_throttle(url)  # space out same-domain requests
            try:
                result = _worker_processor().process_recipe_autonomous(
                    url, save_images_dir=image_dir, user_id=config.get("user_id")
                )
                if getattr(result, "success", False):
                    rec.recipe_id = getattr(result, "recipe_id", None)
                    rec.recipe_name = getattr(result, "recipe_name", None)
                    rec.ingredients_processed = getattr(result, "ingredients_processed", 0)
                    rec.image_generated = getattr(result, "image_generated", False)
                    rec.processing_time_seconds = getattr(result, "processing_time_seconds", 0.0)
                    rec.status = "created"
                    rec.est_cost_usd = est_cost
                    return rec
                last_err = getattr(result, "error_message", "unknown error")
                # Definitive duplicate (caught before enrichment/image) — don't retry
                # or try other candidates; record as a skipped dupe.
                if last_err == "DUPLICATE_RECIPE":
                    rec.status = "skipped_dupe"
                    rec.recipe_name = getattr(result, "recipe_name", None)
                    return rec
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))  # linear backoff (e.g. 3s, 6s)
    rec.status = "failed"
    rec.error = last_err
    return rec


def run_job(config: dict, dry_run: bool, canary: Optional[int], resume: bool,
            max_dishes: Optional[int] = None) -> JobReport:
    job_name = config["job_name"]
    base_url = os.environ.get("EKITCHEN_BASE_URL", "https://ekitchen-production.up.railway.app")
    email = os.environ.get("EKITCHEN_ADMIN_EMAIL", "")
    password = os.environ.get("EKITCHEN_ADMIN_PASSWORD", "")
    concurrency = max(1, int(config.get("concurrency", 3)))
    templates = load_templates(config)
    max_urls_per_dish = int(config.get("max_urls_per_dish", 3))

    print(f"\n{'='*70}\n🤖 AUTONOMOUS INGEST: {job_name}\n{'='*70}")
    print(f"   backend     : {base_url}")
    print(f"   mode        : {'DRY RUN' if dry_run else ('CANARY ' + str(canary)) if canary else 'FULL RUN'}")
    print(f"   concurrency : {concurrency}")
    print(f"   templates   : {len(templates)} search template(s)")

    dishes = load_dishes(config["dish_sources"])
    if max_dishes:
        dishes = dishes[:max_dishes]
    print(f"   dishes      : {len(dishes)} loaded from {len(config['dish_sources'])} source(s)"
          + (f" (capped to {max_dishes})" if max_dishes else ""))

    existing: List[set] = []
    if config.get("dedupe_against_catalog", True):
        if not (email and password):
            print("⚠️  EKITCHEN_ADMIN_EMAIL/PASSWORD not set; cannot dedupe. Source an env file.")
        else:
            print("   deduping against live catalog...")
            try:
                existing = fetch_existing_recipe_names(base_url, email, password)
                print(f"   catalog     : {len(existing)} existing recipes")
            except Exception as e:  # noqa: BLE001
                # Non-fatal: the processor's own per-worker dedup + the backend's
                # unique-name 409 still prevent duplicates; we just lose the cheap
                # pre-discovery skip (slightly more scrape cost).
                print(f"   ⚠️  catalog dedup fetch failed ({e}); continuing with processor-level dedup only")
                existing = []

    prior = _load_prior_records(job_name) if resume else {}

    report = JobReport(job_name=job_name, config=config, started_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    target = config.get("target_count", 0) or len(dishes)
    if canary:
        target = min(target, canary)
    max_cost = float(config.get("max_cost_usd", 0) or 0)
    est_cost = float(config.get("est_cost_per_recipe_usd", 0.05))
    extractor = PlaywrightRecipeExtractor()

    # Per-domain stagger interval + image output dir (enables DALL-E hero images).
    global _MIN_DOMAIN_INTERVAL
    _MIN_DOMAIN_INTERVAL = float(config.get("min_domain_interval_seconds", 4.0))
    image_dir = config.get("image_dir") or str(THIS_DIR / "generated-recipe-images" / "autonomous" / job_name)
    if not dry_run:
        os.makedirs(image_dir, exist_ok=True)
    config["_image_dir"] = image_dir

    lock = threading.Lock()
    created = 0
    spent = 0.0

    def record(rec: RecipeRecord) -> None:
        nonlocal created, spent
        with lock:
            report.records.append(rec)
            if rec.status == "created":
                created += 1
                spent += rec.est_cost_usd
            _write_report(report)

    # Main thread: resume + dedupe gates (cheap), and discovery (Playwright).
    # Discovery is run up front so the limit checks happen before any paid LLM work.
    to_ingest: List[tuple] = []
    for dish in dishes:
        if created >= target or (max_cost and spent >= max_cost):
            break
        if dish in prior and prior[dish].status in ("created", "skipped_dupe"):
            record(prior[dish])
            continue
        if existing and is_duplicate(dish, existing):
            record(RecipeRecord(dish=dish, status="skipped_dupe"))
            print(f"   ⏭️  dupe: {dish}")
            continue
        urls = discover_candidates(extractor, templates, dish, max_urls_per_dish)
        if not urls:
            record(RecipeRecord(dish=dish, url=None, status="no_url"))
            continue
        if dry_run:
            record(RecipeRecord(dish=dish, url=urls[0], status="dry_run"))
            continue
        to_ingest.append((dish, urls))
        # Stop discovery once we have enough candidates (target + a small buffer)
        # so canary/partial runs don't over-scrape the entire dish list.
        if len(to_ingest) >= (target - created) + concurrency:
            break

    if dry_run:
        _write_report(report)
        return report

    # Parallel ingestion with a bounded pool; stop submitting once limits hit.
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {}
        for dish, urls in to_ingest:
            with lock:
                if created + len(futures) >= target:
                    break
                if max_cost and (spent + len(futures) * est_cost) >= max_cost:
                    break
            futures[ex.submit(_ingest_one, dish, urls, config, est_cost)] = dish

        for fut in as_completed(futures):
            rec = fut.result()
            record(rec)
            if rec.status == "created":
                print(f"   ✅ [{created}/{target}] {rec.recipe_name}  ({rec.recipe_id})")
            elif rec.status == "failed":
                print(f"   ❌ {rec.dish} -> {rec.error}")
            with lock:
                if created >= target or (max_cost and spent >= max_cost):
                    for f in futures:
                        f.cancel()  # cancels only not-yet-started tasks
                    break

    _write_report(report)
    return report


def preflight_check(config: dict) -> bool:
    """Verify external dependencies are healthy BEFORE any ingestion. Aborts the run
    (returns False) if any CRITICAL dep is down; optional deps only warn. Catches the
    failure modes we've hit: OpenAI quota, dead Spoonacular sub, prod auth timeouts,
    retired image model."""
    base_url = os.environ.get("EKITCHEN_BASE_URL", "https://ekitchen-production.up.railway.app")
    email = os.environ.get("EKITCHEN_ADMIN_EMAIL", "")
    password = os.environ.get("EKITCHEN_ADMIN_PASSWORD", "")
    results = []  # (name, critical, ok, detail)

    # eKitchen auth + ingredient API (CRITICAL)
    try:
        login = _request_with_retry("POST", f"{base_url}/auth/login",
                                    json={"email": email, "password": password}, timeout=45, attempts=3)
        tok = login.json().get("access_token") or login.json().get("token")
        srch = _request_with_retry("GET", f"{base_url}/global-ingredients/search?q=salt&limit=1",
                                   headers={"Authorization": f"Bearer {tok}"}, timeout=45, attempts=3)
        results.append(("eKitchen auth + ingredient API", True, bool(tok) and srch.status_code == 200,
                        f"login+search HTTP {srch.status_code}"))
    except Exception as e:  # noqa: BLE001
        results.append(("eKitchen auth + ingredient API", True, False, str(e)[:90]))

    # OpenAI chat / quota (CRITICAL)
    try:
        import openai
        oc = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        oc.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "ping"}], max_tokens=2)
        results.append(("OpenAI chat (quota/billing)", True, True, "responded"))
    except Exception as e:  # noqa: BLE001
        results.append(("OpenAI chat (quota/billing)", True, False, str(e)[:90]))

    # OpenAI image model (CRITICAL for images) — cheapest tier to keep preflight ~free
    if config.get("preflight_image_check", True):
        try:
            import openai
            oc = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
            oc.images.generate(model="gpt-image-1", prompt="a single red apple on white",
                               size="1024x1024", quality="low", n=1)
            results.append(("OpenAI image (gpt-image-1)", True, True, "generated"))
        except Exception as e:  # noqa: BLE001
            results.append(("OpenAI image (gpt-image-1)", True, False, str(e)[:90]))

    # Spoonacular (NON-critical — pipeline degrades to eKitchen lookup + OpenAI)
    sk = os.environ.get("SPOONACULAR_API_KEY", "")
    sbase = os.environ.get("SPOONACULAR_BASE_URL", "https://api.spoonacular.com")
    try:
        if "rapidapi.com" in sbase:
            sp = requests.get(f"{sbase}/food/ingredients/search", params={"query": "salt", "number": 1},
                              headers={"X-RapidAPI-Key": sk, "X-RapidAPI-Host": sbase.replace("https://", "")}, timeout=20)
        else:
            sp = requests.get(f"{sbase}/food/ingredients/search", params={"query": "salt", "number": 1, "apiKey": sk}, timeout=20)
        results.append(("Spoonacular (optional enrichment)", False, sp.status_code == 200, f"HTTP {sp.status_code}"))
    except Exception as e:  # noqa: BLE001
        results.append(("Spoonacular (optional enrichment)", False, False, str(e)[:60]))

    print(f"\n{'='*70}\n🩺 PREFLIGHT DEPENDENCY CHECK\n{'='*70}")
    for name, critical, ok, detail in results:
        mark = "✅" if ok else ("🔴" if critical else "⚠️ ")
        print(f"   {mark} {name}: {detail}")
    crit_fail = [r for r in results if r[1] and not r[2]]
    if crit_fail:
        print(f"\n❌ PREFLIGHT FAILED — {len(crit_fail)} critical dependency down. Aborting before any ingestion.")
        return False
    warns = [r for r in results if not r[1] and not r[2]]
    if warns:
        print(f"\n⚠️  {len(warns)} optional dependency degraded — continuing with fallbacks (eKitchen + OpenAI).")
    print("✅ Preflight passed — critical dependencies green.")
    return True


def main():
    ap = argparse.ArgumentParser(description="Autonomous recipe ingestion orchestrator")
    ap.add_argument("--config", required=True, help="Path to job config JSON")
    ap.add_argument("--dry-run", action="store_true", help="Discover + dedupe only; ingest nothing")
    ap.add_argument("--canary", type=int, default=None, help="Ingest at most N recipes")
    ap.add_argument("--resume", action="store_true", help="Skip dishes already completed in prior report")
    ap.add_argument("--max-dishes", type=int, default=None, help="Cap total dishes considered (for quick validation)")
    ap.add_argument("--skip-preflight", action="store_true", help="Skip the external-dependency health check")
    args = ap.parse_args()

    config = json.loads(Path(args.config).read_text())

    # Gate: verify external dependencies are green before spending time/money.
    if not args.dry_run and not args.skip_preflight:
        if not preflight_check(config):
            sys.exit(1)

    report = run_job(config, dry_run=args.dry_run, canary=args.canary, resume=args.resume,
                     max_dishes=args.max_dishes)

    print(f"\n{'='*70}\n📊 SUMMARY: {report.job_name}\n{'='*70}")
    print(json.dumps(report.summary(), indent=2))
    print(f"\n📄 report: {_report_path(report.job_name)}")


if __name__ == "__main__":
    main()
