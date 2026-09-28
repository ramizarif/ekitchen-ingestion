#!/usr/bin/env python3
"""
Ingest a gap-fill selection (P-12 and any later gap run).

`gap_fill_discovery.py select` produces a reviewed, curated list of URLs — one per domain,
archetype-balanced, deduped against the live catalog. This is the last step: hand those URLs
to the same DirectRecipeProcessor every scraped recipe goes through, so a gap-fill recipe is
indistinguishable from any other once it lands.

Deliberately dumb about WHICH urls to take. The thinking happened in `select`, and the list is
reviewed by a human before this runs; re-deciding here would mean two places could disagree
about what is being ingested.

  ⚠ SPENDS MONEY (OpenAI + DALL-E + Spoonacular per recipe) and WRITES TO WHATEVER
    EKITCHEN_BASE_URL POINTS AT — which in this repo's local.env is PRODUCTION.

Canary first, per the data/beginner-starter/INGESTION-PLAN.md precedent:

    ./venv/bin/python tools/recipe-ingestion/ingest_gap_selection.py --gap breakfast --dry-run
    ./venv/bin/python tools/recipe-ingestion/ingest_gap_selection.py --gap breakfast --limit 2
    # verify those 2 in prod, then:
    ./venv/bin/python tools/recipe-ingestion/ingest_gap_selection.py --gap breakfast

Already-ingested URLs are skipped on a re-run, so the final command does not re-pay for the
canary: the backend dedups on inspired_by_url, and we check the same field up front rather
than spending a scrape to be told.
"""
import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(REPO_ROOT / "legacy/src/discovery"))

from services.recipe_processor import DirectRecipeProcessor  # noqa: E402

DATA_DIR = REPO_ROOT / "data" / "gap-fill"
EST_COST_PER_RECIPE = 0.20


def load_env():
    for name in ("local.env", "prod.env"):
        p = REPO_ROOT / name
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    import os
                    os.environ.setdefault(k.strip(), v.strip())
            break


def already_ingested(base, token, urls):
    """URLs already in the catalog, by inspired_by_url.

    Round 1 of P-12 learned this the expensive way: the harvester deduped on a slug-derived
    NAME while the backend dedupes on inspired_by_url, so two recipes came back 409 after
    being paid for. Checking the backend's own key before spending is the fix.
    """
    seen = set()
    try:
        r = requests.get(f"{base}/global-recipes", params={"limit": 2000},
                         headers={"Authorization": f"Bearer {token}"}, timeout=120)
        rows = r.json()
        rows = rows.get("data", rows) if isinstance(rows, dict) else rows
        for row in rows or []:
            u = (row.get("inspired_by_url") or "").strip()
            if u:
                seen.add(u.rstrip("/"))
    except Exception as e:
        print(f"  ! could not pre-check existing URLs ({e}); relying on backend dedupe")
    return {u for u in urls if u.rstrip("/") in seen}


def main():
    ap = argparse.ArgumentParser(description="Ingest a reviewed gap-fill selection")
    ap.add_argument("--gap", required=True, help="gap key, e.g. breakfast")
    ap.add_argument("--limit", type=int, default=None, help="ingest at most N (canary)")
    ap.add_argument("--dry-run", action="store_true", help="show what would run; spend nothing")
    ap.add_argument("--images", default=str(DATA_DIR / "images"),
                    help="where hero images are written before upload")
    args = ap.parse_args()

    load_env()
    import os
    base = os.environ.get("EKITCHEN_BASE_URL", "")
    sel_file = DATA_DIR / f"selected_{args.gap}.json"
    if not sel_file.exists():
        sys.exit(f"no selection: {sel_file} — run `gap_fill_discovery.py select --gap {args.gap}` first")
    selection = json.loads(sel_file.read_text())

    print(f"target backend : {base}")
    print(f"selection      : {sel_file.name} ({len(selection)} recipes)")
    if "railway" in base or "prod" in base:
        print("  ⚠ this is PRODUCTION — recipes become visible to all users immediately")

    token = None
    if not args.dry_run:
        r = requests.post(f"{base}/auth/login", json={
            "email": os.environ["EKITCHEN_ADMIN_EMAIL"],
            "password": os.environ["EKITCHEN_ADMIN_PASSWORD"]}, timeout=60)
        r.raise_for_status()
        token = r.json()["access_token"]
        done = already_ingested(base, token, [s["url"] for s in selection])
        if done:
            print(f"  skipping {len(done)} already in the catalog")
            selection = [s for s in selection if s["url"] not in done]

    todo = selection[: args.limit] if args.limit else selection
    print(f"to ingest      : {len(todo)}   est. ${len(todo) * EST_COST_PER_RECIPE:.2f}\n")

    if args.dry_run:
        for s in todo:
            print(f"  would ingest  {(s.get('title') or '')[:52]:54s} {urlparse(s['url']).netloc}")
        print("\n(dry run — nothing scraped, nothing spent, nothing written)")
        return

    Path(args.images).mkdir(parents=True, exist_ok=True)
    print(f"images         : {args.images}\n")
    proc = DirectRecipeProcessor(log_to_file=True)
    created, failed = [], []
    for i, s in enumerate(todo, 1):
        title = (s.get("title") or s.get("dish") or "")[:50]
        print(f"[{i}/{len(todo)}] {title} — {urlparse(s['url']).netloc}")
        try:
            # save_images_dir is NOT optional in practice: the shared image step starts with
            # `if not save_images_dir: return None, None`, so omitting it silently produces a
            # recipe with no hero photo. The 2-recipe canary caught exactly that.
            res = proc.process_recipe_autonomous(s["url"], save_images_dir=args.images)
            if getattr(res, "success", False):
                created.append((getattr(res, "recipe_id", "?"), getattr(res, "recipe_name", title)))
                print(f"         created {created[-1][0]}  {created[-1][1]}")
            else:
                err = getattr(res, "error_message", "unknown")
                failed.append((title, err))
                print(f"         FAILED  {err}")
        except Exception as e:
            failed.append((title, str(e)))
            print(f"         ERROR   {e}")
        time.sleep(2)  # be a good citizen; these are small independent blogs

    print(f"\ncreated {len(created)}  failed {len(failed)}  est. spend ${len(todo) * EST_COST_PER_RECIPE:.2f}")
    for rid, name in created:
        print(f"  {rid}  {name}")
    for t, e in failed:
        print(f"  FAILED  {t}: {e}")
    if created:
        print("\nRollback if needed: DELETE /global-recipes/{id} for the ids above.")


if __name__ == "__main__":
    main()
