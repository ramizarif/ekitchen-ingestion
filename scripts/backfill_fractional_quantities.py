#!/usr/bin/env python3
"""
Repair ingredient quantities corrupted by the fractional-parsing bug.

Background
----------
Until fix/fractional-quantity-parsing, parse_ingredient_quantity_and_unit tried
its decimal pattern before its fraction pattern, so "1/2 cup heavy cream" parsed
as quantity 1 (the decimal pattern matched the leading "1" and the scan stopped).
Unicode vulgar fractions ("½ cup") matched no pattern at all and fell through to
the default of 1.0. Every recipe ingested before the fix therefore has any
fractional ingredient stored as 1 — typically 2x-4x the real amount, with
nutrition computed off the inflated numbers.

Detection
---------
The raw ingredient text is NOT retained in the database (original_reference is
empty on 98% of rows, reference_as holds the AI-standardized descriptor with no
quantity). The only ground truth is the source page, so this script re-scrapes
each recipe's inspired_by_url and, for every raw ingredient line:

    historic_parse(line)  — the exact buggy implementation, reproduced below
    parse_quantity_and_unit(line) — the fixed parser

If those disagree, the line was mis-parsed at ingest time. The line is then
matched to a stored ingredient row, conservatively: same normalized unit, stored
quantity equal to what the buggy parser would have produced, ingredient name
present in the raw line, and exactly one candidate row. Anything ambiguous is
reported as NEEDS_REVIEW and never written.

Usage
-----
    # audit only (default; writes nothing)
    ./venv/bin/python3 scripts/backfill_fractional_quantities.py --limit 40

    # full audit, resumable
    ./venv/bin/python3 scripts/backfill_fractional_quantities.py

    # apply confirmed fixes + recompute nutrition for touched recipes
    ./venv/bin/python3 scripts/backfill_fractional_quantities.py --apply

Env: EKITCHEN_BASE_URL, EKITCHEN_ADMIN_EMAIL, EKITCHEN_ADMIN_PASSWORD
"""
import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))

from services.quantity_parser import parse_quantity_and_unit  # noqa: E402

DEFAULT_STATE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'fraction-backfill', 'state.json'
)

# Units the API/backend has used interchangeably over time.
UNIT_ALIASES = {
    'tsp': 'teaspoon', 'teaspoons': 'teaspoon',
    'tbsp': 'tablespoon', 'tbs': 'tablespoon', 'tablespoons': 'tablespoon',
    'oz': 'ounce', 'ounces': 'ounce',
    'lb': 'pound', 'lbs': 'pound', 'pounds': 'pound',
    'g': 'gram', 'grams': 'gram',
    'kg': 'kilogram', 'ml': 'milliliter', 'l': 'liter',
    'cups': 'cup', 'cloves': 'clove', 'pieces': 'piece', 'slices': 'slice',
}


def norm_unit(unit: Optional[str]) -> str:
    u = (unit or '').strip().lower()
    return UNIT_ALIASES.get(u, u)


def qty_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# The historic (buggy) parser, reproduced verbatim from the pre-fix
# services/recipe_processor.py so the audit compares against what actually ran.
# Only the quantity half matters — unit parsing was unaffected by the bug.
# ---------------------------------------------------------------------------
_HISTORIC_PATTERNS = [
    r'^(\d+(?:\.\d+)?)\s*',
    r'^(\d+/\d+)\s*',
    r'^(\d+\s+\d+/\d+)\s*',
    r'^(one|two|three|four|five|six|seven|eight|nine|ten)\s*',
]
_HISTORIC_WORDS = {
    'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
    'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
}


def historic_unit(ingredient_text: str, after_quantity: str = None) -> str:
    """The old unit algorithm: longest unit NAME wins, anywhere in the line.

    This is what produced the stored units, so it is how we recognise which
    stored row a given source line created.
    """
    from services.quantity_parser import UNIT_PATTERNS
    text = after_quantity if after_quantity is not None else ingredient_text
    for pattern, unit_name in sorted(UNIT_PATTERNS.items(),
                                     key=lambda kv: len(kv[1]), reverse=True):
        if re.search(pattern, text, re.IGNORECASE):
            return unit_name
    return 'serving'


def historic_remaining(ingredient_text: str) -> str:
    """Text left after the OLD parser consumed its quantity (units read from this)."""
    remaining = (ingredient_text or '').lower().strip()
    for pattern in _HISTORIC_PATTERNS:
        match = re.match(pattern, remaining, re.IGNORECASE)
        if match:
            return remaining[match.end():].strip()
    return remaining


def historic_quantity(ingredient_text: str) -> str:
    quantity = "1.0"
    remaining = (ingredient_text or '').lower().strip()
    for pattern in _HISTORIC_PATTERNS:
        match = re.match(pattern, remaining, re.IGNORECASE)
        if not match:
            continue
        raw = match.group(1)
        if '/' in raw:
            if ' ' in raw:  # mixed number (unreachable in practice — decimal won first)
                whole, frac = raw.split()
                num, den = frac.split('/')
                quantity = str(float(whole) + float(num) / float(den))
            else:
                num, den = raw.split('/')
                quantity = str(float(num) / float(den))
        elif raw.lower() in _HISTORIC_WORDS:
            quantity = _HISTORIC_WORDS[raw.lower()]
        else:
            quantity = raw
        break
    return quantity


def quantities_differ(a: str, b: str) -> bool:
    """True only for a MEANINGFUL difference.

    The fixed parser rounds to 4dp, so a value the old parser stored as
    0.33333334326744 (the source page wrote it that way) now renders as 0.3333.
    That is a formatting change, not corruption, and must not be counted as a
    fix — hence the relative tolerance rather than a bare float compare.
    """
    fa, fb = qty_float(a), qty_float(b)
    if fa is None or fb is None:
        return a != b
    return abs(fa - fb) > max(1e-4, 0.005 * max(abs(fa), abs(fb)))


# ---------------------------------------------------------------------------
# eKitchen API
# ---------------------------------------------------------------------------
class EKitchen:
    def __init__(self):
        self.base = os.environ['EKITCHEN_BASE_URL'].rstrip('/')
        self.session = requests.Session()
        self.login()

    def login(self):
        resp = self.session.post(
            f"{self.base}/auth/login",
            json={"email": os.environ['EKITCHEN_ADMIN_EMAIL'],
                  "password": os.environ['EKITCHEN_ADMIN_PASSWORD']},
            timeout=60,
        )
        resp.raise_for_status()
        self.session.headers.update({'Authorization': f"Bearer {resp.json()['access_token']}"})

    def list_recipes(self) -> List[Dict[str, Any]]:
        out, offset = [], 0
        while True:
            resp = self.session.get(f"{self.base}/global-recipes/",
                                    params={"limit": 100, "offset": offset}, timeout=120)
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            out.extend(batch)
            offset += len(batch)
            if len(batch) < 100:
                break
        return out

    def get_recipe(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        for _ in range(3):
            try:
                resp = self.session.get(f"{self.base}/global-recipes/{recipe_id}", timeout=90)
                if resp.status_code == 200:
                    return resp.json()
            except requests.RequestException:
                time.sleep(1)
        return None

    def patch_ingredients(self, recipe_id: str, ingredients: List[Dict[str, Any]]) -> bool:
        resp = self.session.patch(f"{self.base}/global-recipes/{recipe_id}",
                                  json={"ingredients": ingredients}, timeout=120)
        if resp.status_code != 200:
            print(f"      PATCH failed {resp.status_code}: {resp.text[:200]}")
        return resp.status_code == 200

    def recompute_nutrition(self, recipe_id: str) -> bool:
        resp = self.session.post(
            f"{self.base}/admin/global-recipes/{recipe_id}/recompute-nutrition", timeout=180)
        return resp.status_code == 200


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
def scrape_lines(processor, url: str) -> Optional[List[str]]:
    """Raw ingredient lines from the source page. Free tiers only (no LLM spend)."""
    try:
        html = processor._fetch_page_html(url)
        for candidate in (processor._scrape_via_recipe_scrapers(url, html),
                          processor._scrape_via_jsonld(html, url) if html else None):
            if candidate and len(candidate.get('ingredients') or []) >= 3:
                return candidate['ingredients']
    except Exception:
        return None
    return None


def match_row(line: str, old_qty: str, old_unit: str, new_parse: Dict[str, str],
              rows: List[Dict[str, Any]], claimed: set) -> Optional[int]:
    """Index of the single stored row this raw line produced, or None.

    Identity is the OLD parser's output, since that is what was written. The
    quantity may already equal the corrected value if the quantity backfill has
    run over this row, so either is accepted.
    """
    line_l = line.lower()
    accepted = {q for q in (qty_float(old_qty), qty_float(new_parse['quantity']))
                if q is not None}
    candidates = []
    for idx, row in enumerate(rows):
        if idx in claimed:
            continue
        stored_f = qty_float(row.get('quantity'))
        if stored_f is None or not any(abs(stored_f - q) <= 1e-4 for q in accepted):
            continue
        # The stored unit came from the old algorithm; the backend may since
        # have standardized an alias (tsp -> teaspoon).
        if norm_unit(row.get('unit')) not in {norm_unit(old_unit),
                                              norm_unit(new_parse['unit'])}:
            continue
        name = (row.get('name') or '').strip().lower()
        if not name:
            continue
        # ingredient name (or its head noun) must actually appear in the line
        if name in line_l or all(tok in line_l for tok in name.split() if len(tok) > 3):
            candidates.append(idx)
    return candidates[0] if len(candidates) == 1 else None


def audit_recipe(processor, recipe: Dict[str, Any]) -> Dict[str, Any]:
    result = {"id": recipe['id'], "name": recipe['name'],
              "url": recipe.get('inspired_by_url') or '', "status": "", "fixes": [], "review": []}

    if not result['url']:
        result['status'] = 'NO_SOURCE_URL'
        return result

    lines = scrape_lines(processor, result['url'])
    if not lines:
        result['status'] = 'SCRAPE_FAILED'
        return result

    rows = recipe.get('ingredients') or []
    claimed = set()
    for line in lines:
        if not isinstance(line, str) or not line.strip():
            continue
        old_qty = historic_quantity(line)
        old_unit = historic_unit(line, historic_remaining(line))
        new = parse_quantity_and_unit(line)

        qty_wrong = quantities_differ(old_qty, new['quantity'])
        unit_differs = norm_unit(old_unit) != norm_unit(new['unit'])

        # "1 (4 pound) pork shoulder roast" masks its only unit inside the
        # parenthetical and lands on the 'serving' fallback. Neither the old
        # value (1 pound, understating a 4lb roast) nor 'serving' is right, and
        # rewriting a concrete unit to the fallback loses information and would
        # skew the nutrition recompute. Report, don't write.
        unit_downgrade = (unit_differs
                          and new['unit'] == 'serving' and old_unit != 'serving')
        unit_wrong = unit_differs and not unit_downgrade

        if not qty_wrong and not unit_wrong:
            if unit_downgrade:
                result['review'].append({
                    "line": line.strip()[:120], "stored_quantity": old_qty,
                    "correct_quantity": new['quantity'], "stored_unit": old_unit,
                    "correct_unit": new['unit'], "unit": new['unit'],
                    "reason": "unit would downgrade to 'serving'"})
            continue  # this line was parsed correctly at ingest

        idx = match_row(line, old_qty, old_unit, new, rows, claimed)
        entry = {"line": line.strip()[:120],
                 "stored_quantity": old_qty, "correct_quantity": new['quantity'],
                 "stored_unit": old_unit, "correct_unit": new['unit'],
                 "unit": new['unit'],
                 "qty_wrong": qty_wrong, "unit_wrong": unit_wrong}
        if idx is None:
            result['review'].append(entry)
            continue
        claimed.add(idx)

        # Report against the row's CURRENT values, not the parser comparison —
        # an earlier pass may already have corrected the quantity, and counting
        # that as outstanding work would overstate what is left to do.
        row = rows[idx]
        entry['stored_quantity'] = str(row.get('quantity'))
        entry['stored_unit'] = row.get('unit')
        entry['qty_wrong'] = quantities_differ(entry['stored_quantity'], new['quantity'])
        entry['unit_wrong'] = (unit_wrong
                               and norm_unit(row.get('unit')) != norm_unit(new['unit']))
        if not entry['qty_wrong'] and not entry['unit_wrong']:
            continue  # already correct in the database

        entry.update({"ingredient": row.get('name'), "row_index": idx})
        result['fixes'].append(entry)

    result['status'] = 'HAS_FIXES' if result['fixes'] else 'CLEAN'
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--limit', type=int, default=0, help='audit only the first N recipes')
    ap.add_argument('--apply', action='store_true', help='write fixes to prod (default: audit only)')
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--state', default=DEFAULT_STATE, help='resumable audit checkpoint')
    ap.add_argument('--fresh', action='store_true', help='ignore any existing checkpoint')
    args = ap.parse_args()

    api = EKitchen()
    print(f"Target: {api.base}")
    if 'railway.app' in api.base and args.apply:
        print("*** APPLYING TO PRODUCTION ***")

    os.makedirs(os.path.dirname(os.path.abspath(args.state)), exist_ok=True)
    audited: Dict[str, Any] = {}
    if os.path.exists(args.state) and not args.fresh:
        audited = json.load(open(args.state))
        print(f"Resuming from checkpoint: {len(audited)} recipes already audited")

    if not args.apply:
        print("Loading catalog...")
        summaries = api.list_recipes()
        todo = [r for r in summaries if r['id'] not in audited]
        if args.limit:
            todo = todo[:args.limit]
        print(f"Catalog: {len(summaries)} recipes | to audit now: {len(todo)}")

        from services.recipe_processor import DirectRecipeProcessor
        processor = DirectRecipeProcessor(log_to_file=False)
        processor.logger.disabled = True

        def work(summary):
            full = api.get_recipe(summary['id'])
            return audit_recipe(processor, full) if full else None

        done = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for res in pool.map(work, todo):
                done += 1
                if res:
                    audited[res['id']] = res
                    flag = (f"{len(res['fixes'])} fixes" if res['fixes']
                            else res['status'].lower())
                    print(f"  [{done}/{len(todo)}] {res['name'][:52]:<52} {flag}")
                if done % 25 == 0:
                    json.dump(audited, open(args.state, 'w'), indent=1)
        json.dump(audited, open(args.state, 'w'), indent=1)

    results = list(audited.values())
    by_status = {}
    for r in results:
        by_status.setdefault(r['status'], []).append(r)

    broken = [r for r in results if r['fixes']]
    total_fixes = sum(len(r['fixes']) for r in results)
    total_review = sum(len(r['review']) for r in results)

    print("\n" + "=" * 72)
    print("FRACTIONAL QUANTITY AUDIT")
    print("=" * 72)
    print(f"  audited            {len(results)}")
    for status in sorted(by_status):
        print(f"  {status.lower():<18} {len(by_status[status])}")
    all_fixes = [f for r in results for f in r['fixes']]
    qty_only = [f for f in all_fixes if f.get('qty_wrong') and not f.get('unit_wrong')]
    unit_only = [f for f in all_fixes if f.get('unit_wrong') and not f.get('qty_wrong')]
    both = [f for f in all_fixes if f.get('qty_wrong') and f.get('unit_wrong')]

    print(f"\n  recipes with confirmed corruption : {len(broken)}")
    print(f"  ingredient rows to correct        : {total_fixes}")
    print(f"      wrong quantity only           : {len(qty_only)}")
    print(f"      wrong unit only               : {len(unit_only)}")
    print(f"      wrong quantity AND unit       : {len(both)}")
    print(f"  rows needing manual review        : {total_review}")

    if broken:
        print("\n  Worst affected:")
        for r in sorted(broken, key=lambda x: -len(x['fixes']))[:15]:
            print(f"    {r['name'][:50]:<50} {len(r['fixes'])} rows")
            for f in r['fixes'][:3]:
                print(f"        {f['stored_quantity']} {f.get('stored_unit','?')} -> "
                      f"{f['correct_quantity']} {f.get('correct_unit','?')}"
                      f"  ({f['ingredient']})   [{f['line'][:46]}]")

    if not args.apply:
        print(f"\nAudit only — nothing written. Checkpoint: {args.state}")
        print("Re-run with --apply to correct the confirmed rows.")
        return

    print(f"\nApplying fixes to {len(broken)} recipes...")
    rollback_path = os.path.join(os.path.dirname(os.path.abspath(args.state)), 'rollback.json')
    rollback: Dict[str, Any] = {}
    if os.path.exists(rollback_path):
        rollback = json.load(open(rollback_path))

    fixed = failed = 0
    for i, r in enumerate(broken, 1):
        full = api.get_recipe(r['id'])
        if not full:
            failed += 1
            continue
        rows = full['ingredients']
        # Snapshot the pre-write state so this backfill can be undone.
        if r['id'] not in rollback:
            rollback[r['id']] = {"name": full.get('name'),
                                 "ingredients": json.loads(json.dumps(rows))}
            json.dump(rollback, open(rollback_path, 'w'), indent=1)
        changed = 0
        for f in r['fixes']:
            # Re-locate the row by identity rather than trusting the index
            # captured at audit time — the list may have been reordered, and a
            # stale index would rewrite the wrong ingredient's quantity.
            idx = f['row_index']
            if not (idx < len(rows)
                    and (rows[idx].get('name') or '') == (f.get('ingredient') or '')):
                matches = [k for k, row in enumerate(rows)
                           if (row.get('name') or '') == (f.get('ingredient') or '')]
                if len(matches) != 1:
                    print(f"      skip (row moved/ambiguous): {f.get('ingredient')}")
                    continue
                idx = matches[0]
            # Re-verify the row still holds a value this fix was derived from.
            # (The quantity may already be corrected from an earlier pass.)
            stored_now = str(rows[idx].get('quantity'))
            if (quantities_differ(stored_now, f['stored_quantity'])
                    and quantities_differ(stored_now, f['correct_quantity'])):
                print(f"      skip (unexpected value): {f.get('ingredient')}")
                continue

            row_changed = False
            if f.get('qty_wrong', True) and quantities_differ(stored_now, f['correct_quantity']):
                rows[idx]['quantity'] = f['correct_quantity']
                rows[idx]['quantity_value'] = float(f['correct_quantity'])
                row_changed = True
            if f.get('unit_wrong') and f.get('correct_unit'):
                if norm_unit(rows[idx].get('unit')) != norm_unit(f['correct_unit']):
                    rows[idx]['unit'] = f['correct_unit']
                    row_changed = True
            changed += row_changed
        if not changed:
            continue
        if api.patch_ingredients(r['id'], rows) and api.recompute_nutrition(r['id']):
            fixed += 1
            print(f"  [{i}/{len(broken)}] fixed {changed} rows: {r['name'][:50]}")
        else:
            failed += 1
            print(f"  [{i}/{len(broken)}] FAILED: {r['name'][:50]}")

    print(f"\nRecipes repaired: {fixed}   failed: {failed}")


if __name__ == '__main__':
    main()
