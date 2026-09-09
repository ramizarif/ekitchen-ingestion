#!/usr/bin/env python3
"""
Recover the amounts the importer never captured, from the pages they came from.

655 catalog rows carry quantity '1.0' against a real unit. That is not a
measurement: '1.0' is what the parser wrote when a line gave it no number, and
it is the only x.0 value anywhere in the table. The app renders it as fact, so
a recipe whose source line reads "sugar" tells you "1 cup sugar".

Three routes were on the table -- re-ingest, ask a model, or blank the amount.
This is the first: the source pages still have the real numbers, so nothing here
is guessed. What cannot be recovered confidently is reported, not invented.

    Read      targets.json   (recipe url + the rows still holding the placeholder)
    Scrape    the source page via the existing tiered scraper
    Parse     each source line with services.quantity_parser
    Match     a line to a row by ingredient name, disambiguated by unit
    Emit      a migration body, plus a report of everything it would not touch

Matching is deliberately timid. A wrong amount is worse than a missing one: it
is indistinguishable from a real one, and someone cooks from it. A row is only
proposed when exactly one source line contains the ingredient's words AND its
unit agrees with the row's. Everything else -- no match, several matches, a unit
that disagrees, a line with no number of its own -- lands in the report.

Usage:
    python scripts/recover_missing_amounts.py --targets targets.json --out ./out
    python scripts/recover_missing_amounts.py --targets targets.json --out ./out --limit 15
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.quantity_parser import parse_quantity_and_unit  # noqa: E402
from services.recipe_processor import DirectRecipeProcessor  # noqa: E402


# The parser spells units out; the catalog holds the canonical short forms that
# migration 20260909002608 settled on. Same map, so the two vocabularies meet.
CANONICAL_UNIT = {
    'teaspoon': 'tsp', 'teaspoons': 'tsp', 'tsp': 'tsp',
    'tablespoon': 'tbsp', 'tablespoons': 'tbsp', 'tbsp': 'tbsp', 'tbs': 'tbsp',
    'cup': 'cup', 'cups': 'cup',
    'ounce': 'oz', 'ounces': 'oz', 'oz': 'oz',
    'fluid ounce': 'fl oz', 'fluid ounces': 'fl oz',
    'pound': 'lb', 'pounds': 'lb', 'lb': 'lb', 'lbs': 'lb',
    'gram': 'g', 'grams': 'g', 'g': 'g',
    'kilogram': 'kg', 'kilograms': 'kg', 'kg': 'kg',
    'milliliter': 'ml', 'milliliters': 'ml', 'ml': 'ml',
    'liter': 'l', 'liters': 'l', 'l': 'l',
    'quart': 'qt', 'quarts': 'qt', 'qt': 'qt',
    'pint': 'pt', 'pints': 'pt', 'pt': 'pt',
    'gallon': 'gal', 'gallons': 'gal', 'gal': 'gal',
    'piece': 'piece', 'slice': 'slice', 'clove': 'clove', 'stalk': 'stalk',
    'head': 'head', 'bunch': 'bunch', 'strip': 'strip', 'can': 'can',
    'package': 'package', 'jar': 'jar', 'bottle': 'bottle',
    'pinch': 'pinch', 'dash': 'dash',
}

# Words that say how an ingredient was prepared, not what it is. Dropped before
# matching so "chopped fresh parsley" still meets "parsley".
NOISE_WORDS = {
    'fresh', 'freshly', 'chopped', 'minced', 'diced', 'sliced', 'grated',
    'shredded', 'crushed', 'ground', 'peeled', 'seeded', 'trimmed', 'cubed',
    'halved', 'quartered', 'melted', 'softened', 'divided', 'optional',
    'large', 'medium', 'small', 'extra', 'plus', 'more', 'to', 'taste',
    'and', 'or', 'of', 'the', 'a', 'an', 'for', 'into', 'cut', 'finely',
    'roughly', 'thinly', 'about', 'such', 'as', 'if', 'needed', 'room',
    'temperature', 'packed', 'lightly', 'well', 'very', 'plain', 'whole',
}


def singular(word: str) -> str:
    """Enough of a stemmer to let 'tomatoes' meet 'tomato'."""
    if len(word) > 3 and word.endswith('ies'):
        return word[:-3] + 'y'
    if len(word) > 3 and word.endswith('es') and word[-3] in 'sxzho':
        return word[:-2]
    if len(word) > 2 and word.endswith('s') and not word.endswith('ss'):
        return word[:-1]
    return word


def tokens(text: str) -> List[str]:
    words = re.findall(r"[a-z]+", (text or '').lower())
    return [singular(w) for w in words if w not in NOISE_WORDS and len(w) > 1]


def canonical(unit: Optional[str]) -> Optional[str]:
    if not unit:
        return None
    return CANONICAL_UNIT.get(unit.strip().lower(), unit.strip().lower())


def scraper(use_llm: bool) -> DirectRecipeProcessor:
    """The tiered scraper without the ingestion pipeline around it.

    Tiers 1 and 2 (dedicated parsers, then JSON-LD) are free and read almost
    every page. Tier 3 costs about $0.002 and only runs where they both miss,
    so leaving it on is worth roughly a dollar across the whole catalog.
    """
    rp = DirectRecipeProcessor.__new__(DirectRecipeProcessor)
    rp.log_to_file = False
    rp.openai_client = None
    if use_llm:
        key = os.getenv('OPENAI_API_KEY')
        if key:
            from openai import OpenAI
            rp.openai_client = OpenAI(api_key=key)
        else:
            print('No OPENAI_API_KEY — tier 3 disabled, free tiers only.')
    return rp


def parse_source_lines(lines: List[str]) -> List[Dict[str, Any]]:
    """Each source line with whatever amount it actually states."""
    parsed = []
    for line in lines:
        if not line or not line.strip():
            continue
        got = parse_quantity_and_unit(line)
        parsed.append({
            'line': line.strip(),
            'quantity': got['quantity'],
            'unit': canonical(got['unit']),
            'tokens': set(tokens(line)),
        })
    return parsed


def match_recipe(rows: List[Dict[str, Any]],
                 sources: List[Dict[str, Any]]) -> List[Tuple[Dict, Optional[Dict], str]]:
    """Assign source lines to rows one recipe at a time.

    Row by row is not enough. A recipe can hold two placeholder rows for the
    same ingredient and unit -- 6-Minute Apple Crisp wants cinnamon twice -- and
    matching each in isolation hands both of them the same line, inventing an
    amount for one of them. Nothing in the row says which is which: the rows
    carry no section, so "1 teaspoon salt" for the crust and "1/2 teaspoon salt"
    for the filling are indistinguishable.

    So the unit of work is the (ingredient, unit) group within a recipe, and a
    group only resolves when the answer does not depend on getting the order
    right: one row and one line, one row and one clearly tightest line, or N rows
    against N lines that all state the same amount. A source line is also claimed
    by at most one group, so a bare "pepper" row cannot quietly take the line
    belonging to "black pepper".
    """
    results: List[Tuple[Dict, Optional[Dict], str]] = []

    # Group the rows the way the ambiguity actually arises.
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row['ingredient'].lower(), canonical(row['unit']) or ''), []).append(row)

    # Candidate lines per group, then settle any line two groups both want.
    candidates: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for key, members in groups.items():
        name_tokens = set(tokens(members[0]['ingredient']))
        if not name_tokens:
            candidates[key] = []
            continue
        candidates[key] = [s for s in sources
                           if name_tokens <= s['tokens']
                           and s['quantity'] is not None
                           and s['unit'] == key[1]]

    claimed: Dict[int, Tuple[str, str]] = {}
    for key, lines in candidates.items():
        specificity = len(set(tokens(key[0])))
        for line in lines:
            owner = claimed.get(id(line))
            if owner is None or specificity > len(set(tokens(owner[0]))):
                claimed[id(line)] = key
    for key in candidates:
        candidates[key] = [l for l in candidates[key] if claimed.get(id(l)) == key]

    for key, members in groups.items():
        lines = candidates.get(key) or []
        name_tokens = set(tokens(members[0]['ingredient']))

        if not name_tokens:
            for row in members:
                results.append((row, None, 'ingredient name has nothing to match on'))
            continue

        if not lines:
            # Separate "the page never mentions it" from "it does, without a number".
            mentioned = [s for s in sources if name_tokens <= s['tokens']]
            if not mentioned:
                reason = 'no source line mentions this ingredient'
            elif not any(s['quantity'] is not None for s in mentioned):
                reason = 'the source line states no amount either'
            else:
                units = {s['unit'] or '-' for s in mentioned if s['quantity'] is not None}
                reason = (f"unit disagrees: row says {key[1] or '-'}, "
                          f"source says {'/'.join(sorted(units))}")
            for row in members:
                results.append((row, None, reason))
            continue

        if len(members) == 1:
            if len(lines) == 1:
                results.append((members[0], lines[0], 'ok'))
                continue
            tightest = sorted(lines, key=lambda s: len(s['tokens']))
            if len(tightest[0]['tokens']) < len(tightest[1]['tokens']):
                results.append((members[0], tightest[0], 'ok'))
            else:
                results.append((members[0], None, f'{len(lines)} equally good source lines'))
            continue

        # Several rows want the same ingredient and unit. Only safe when the
        # answer is the same whichever way round they go.
        amounts = {s['quantity'] for s in lines}
        if len(lines) == len(members) and len(amounts) == 1:
            for row, line in zip(members, lines):
                results.append((row, line, 'ok'))
        else:
            reason = (f'{len(members)} rows against {len(lines)} source lines '
                      f'with no way to tell which is which')
            for row in members:
                results.append((row, None, reason))

    return results



def sql_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def write_migration(proposals: List[Dict[str, Any]], path: str) -> None:
    """Emit the proposals as a migration that applies anywhere the catalog lives.

    Row ids are generated per insert, so they do not identify the same row in
    two databases. (source URL, ingredient, current unit) does, and it is unique
    across the proposals because a row whose ingredient and unit are ambiguous
    within one recipe never gets proposed in the first place.

    The `quantity = '1.0'` guard is what makes this safe to re-run and safe to
    ship: it only touches a row still holding the placeholder, so a row someone
    has since corrected by hand is left exactly as they left it.
    """
    seen: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    conflicts = []
    for p in proposals:
        key = (p['url'].strip().lower(), p['ingredient'].strip().lower(), (p['unit'] or '').lower())
        if key in seen:
            # Two rows sharing a key is expected and fine when they resolved to
            # the same number -- a recipe wanting cinnamon twice, both a quarter
            # teaspoon. The UPDATE matches on the key, so it sets both. Two
            # different numbers under one key would mean the matcher assigned
            # something it could not tell apart, and that must not ship.
            if seen[key]['quantity'] != p['quantity']:
                conflicts.append((key, seen[key]['quantity'], p['quantity']))
            continue
        seen[key] = p
    if conflicts:
        raise SystemExit(f"{len(conflicts)} keys carry two different amounts; "
                         f"refusing to emit: {conflicts[:3]}")

    rows = sorted(seen.items())
    values = ",\n".join(
        "    (%s, %s, %s, %s)" % (sql_quote(url), sql_quote(ing), sql_quote(unit), sql_quote(p['quantity']))
        for (url, ing, unit), p in rows
    )

    body = f"""-- +goose Up
-- +goose StatementBegin

-- The amounts the importer never captured, read back off the pages they came from.
--
-- {len(rows)} rows carried quantity '1.0' against a real unit. That is not a
-- measurement -- '1.0' is what the parser wrote when a line gave it no number,
-- and it was the only x.0 value in the table -- but the app rendered it as fact,
-- so a source line reading "sugar" reached the screen as "1 cup sugar".
--
-- Every value below was read from the recipe's own source page by
-- scripts/recover_missing_amounts.py in the ingestion repo, matched to its row
-- by ingredient name with the row's unit as the disambiguator. Nothing here is
-- inferred: where the page was unreadable, stated no amount of its own, or
-- offered two equally good lines, the row was left alone and reported instead.
-- See docs/UNIT_REVIEW_LIST.md for what remains.
--
-- Keyed on (source URL, ingredient, unit) rather than row id, because ids are
-- generated per insert and do not name the same row in two databases. The
-- quantity = '1.0' guard makes it idempotent, and leaves alone any row someone
-- has already corrected by hand.

CREATE TEMP TABLE recovered_amounts (
    source_url TEXT,
    ingredient TEXT,
    unit       TEXT,
    quantity   TEXT
) ON COMMIT DROP;

INSERT INTO recovered_amounts (source_url, ingredient, unit, quantity) VALUES
{values};

UPDATE recipe_ingredients ri
SET quantity   = ra.quantity,
    updated_at = CURRENT_TIMESTAMP
FROM recovered_amounts ra, global_recipes gr, global_ingredients gi
WHERE ri.recipe_id = gr.id
  AND ri.ingredient_id = gi.id
  AND lower(trim(gr.inspired_by_url)) = ra.source_url
  AND lower(trim(gi.name)) = ra.ingredient
  AND lower(trim(ri.unit)) = ra.unit
  AND ri.quantity = '1.0';

-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin

-- The placeholder is not restored. '1.0' never meant one of anything; these are
-- the numbers the recipes actually state.

-- +goose StatementEnd
"""
    with open(path, 'w') as fh:
        fh.write(body)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--targets', required=True, help='JSON exported from the catalog')
    ap.add_argument('--out', required=True, help='directory for the proposals, report and SQL')
    ap.add_argument('--limit', type=int, default=0, help='only process this many recipes')
    ap.add_argument('--delay', type=float, default=1.0, help='seconds between page fetches')
    ap.add_argument('--migration', default='',
                    help='write a goose migration body applying the proposals to this path')
    ap.add_argument('--no-llm', action='store_true',
                    help='free tiers only; skips the ~$0.002 fallback on pages they miss')
    args = ap.parse_args()

    targets = json.load(open(args.targets))
    if args.limit > 0:
        targets = targets[:args.limit]
    os.makedirs(args.out, exist_ok=True)

    cache_path = os.path.join(args.out, 'scrape_cache.json')
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}

    rp = scraper(use_llm=not args.no_llm)
    proposals: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    reasons: Counter = Counter()
    unreachable: List[Dict[str, str]] = []

    for i, target in enumerate(targets, 1):
        url = target['url']
        print(f"[{i}/{len(targets)}] {target['recipe'][:56]}")

        if url in cache:
            lines = cache[url]
        else:
            try:
                data = rp.scrape_recipe_from_url(url)
            except Exception as e:                      # noqa: BLE001
                print(f"    scrape raised {type(e).__name__}: {e}")
                data = None
            lines = (data or {}).get('ingredients') or []
            cache[url] = lines
            json.dump(cache, open(cache_path, 'w'))
            time.sleep(args.delay)

        if not lines:
            unreachable.append({'recipe': target['recipe'], 'url': url})
            for row in target['items']:
                skipped.append({**row, 'recipe': target['recipe'], 'url': url,
                                'reason': 'source page could not be read'})
                reasons['source page could not be read'] += 1
            continue

        sources = parse_source_lines(lines)
        for row, hit, reason in match_recipe(target['items'], sources):
            if hit is None:
                skipped.append({**row, 'recipe': target['recipe'], 'url': url, 'reason': reason})
                reasons[reason.split(':')[0]] += 1
                continue
            proposals.append({
                'row_id': row['row_id'],
                'recipe': target['recipe'],
                'url': url,
                'ingredient': row['ingredient'],
                'was': f"1 {row['unit']}",
                'quantity': hit['quantity'],
                'unit': hit['unit'],
                'source_line': hit['line'],
            })
            reasons['recovered'] += 1

    json.dump(proposals, open(os.path.join(args.out, 'proposals.json'), 'w'), indent=2)
    if args.migration:
        write_migration(proposals, args.migration)
        print(f"\nMigration written to {args.migration}")
    json.dump(skipped, open(os.path.join(args.out, 'skipped.json'), 'w'), indent=2)

    total = len(proposals) + len(skipped)
    print(f"\n{len(proposals)}/{total} rows recovered from source.")
    for reason, n in reasons.most_common():
        print(f"  {n:>4}  {reason}")
    if unreachable:
        print(f"\n{len(unreachable)} pages could not be read:")
        for u in unreachable[:20]:
            print(f"  {u['recipe'][:50]}  {u['url']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
