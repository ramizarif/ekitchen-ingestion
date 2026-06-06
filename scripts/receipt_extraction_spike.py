#!/usr/bin/env python3
"""
Receipt-extraction accuracy spike (Phase 0 de-risk for receipt scanning).

Sends one or more receipt images to GPT-4o vision with the draft Phase-2
extraction prompt and prints structured line items. Use this to judge whether
the production model reliably handles real receipts (cryptic abbreviations,
weight items, non-food filtering, cut-off edges) BEFORE building the extractor.

Key design: the model emits BOTH a readable "name" and a "canonical_query" —
the singular, qualifier-stripped base term used to resolve against the ingredient
catalog (e.g. "BNLS CHICK BREAST" -> name "boneless chicken breast",
canonical_query "chicken breast"). Resolution quality hinges on canonical_query.

Usage:
    export OPENAI_API_KEY=sk-...
    ./venv/bin/python scripts/receipt_extraction_spike.py [--json] <image> [<image> ...]

--json  emit a machine-readable {file: [items]} blob to stdout (for piping into
        the catalog match-rate check); human summary goes to stderr.
"""
import base64
import json
import mimetypes
import os
import sys
import time

from openai import OpenAI

MODEL = "gpt-4o"  # matches the ingestion pipeline's vision model
MAX_RETRIES = 3

SYSTEM_PROMPT = """You extract purchased line items from a photo of a grocery receipt for a cooking app.

Return STRICT JSON: {"items": [ ... ]}. No prose. One object per PURCHASED LINE ITEM with:
- "raw": exact text as printed (reconstruct an obvious cut-off first letter from context).
- "name": readable, plain-English product name with store/brand abbreviations expanded
  (e.g. "PBX FNCY PARM SHRD" -> "shredded parmesan", "GV WHL MLK" -> "whole milk").
- "canonical_query": the SINGULAR, base cooking-ingredient term to look up in an
  ingredient catalog. RULES:
    * singular, lowercase ("carrots" -> "carrot", "limes" -> "lime")
    * strip marketing/processing qualifiers that don't change the ingredient:
      organic, natural, fancy, family size, value, light, fat-free, reduced-fat,
      shredded, sliced, baby, large, jumbo, mixed -> drop them
      ("organic carrots" -> "carrot", "shredded parmesan" -> "parmesan",
       "fat-free light vanilla yogurt" -> "vanilla yogurt", "baby broccoli" -> "broccoli")
    * KEEP descriptors that define a distinct catalog ingredient: color of peppers
      ("red bell pepper"), the protein/base noun, style of dairy ("greek yogurt").
    * drop the brand from canonical_query.
    * for a composite/prepared item, set canonical_query to "" (it won't resolve to
      a single ingredient).
- "brand": brand if identifiable (store brand or name brand), else "".
- "quantity": the PURCHASE quantity only — a count ("3 @", "12 CT") or a weight
  ("1.14 lb"). A package SIZE like "16 OZ" is the unit size of one item, so set
  quantity 1 and unit "oz" with the size implied. NEVER treat a trailing standalone
  code/number with no unit (e.g. a 2-4 digit PLU like "80") as quantity — use 1.
- "unit": "count", "lb", "oz", "gallon", "liter", etc. when determinable, else "".
- "is_food": true ONLY for edible grocery food/ingredients. false for non-food
  (laundry detergent, napkins, bags), taxes, deposits, totals, payment lines.
- "is_composite": true ONLY for a PREPARED DISH or MULTI-INGREDIENT KIT that is not a
  single ingredient (e.g. "chicken tikka samosas", "caesar salad kit", "frozen lasagna").
  A single processed product is NOT composite: ketchup, peanut butter, broth, bread,
  yogurt, tomato paste are is_composite=false.
- "confidence": 0.0-1.0 in the name/canonical_query normalization.

EXCLUDE entirely: subtotals, totals, tax, "you saved", payment/change/card lines,
"items in transaction", store address/phone/metadata. Only real purchased line items.
"""


def encode_image(path: str) -> tuple[str, str]:
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    if path.lower().endswith(".webp"):
        mime = "image/webp"
    with open(path, "rb") as f:
        return mime, base64.b64encode(f.read()).decode()


def extract(client: OpenAI, path: str) -> list[dict]:
    mime, b64 = encode_image(path)
    if mime not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        raise ValueError(f"unsupported image type {mime} (OpenAI vision needs jpeg/png/webp/gif; convert HEIC first)")

    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract the purchased line items from this receipt."},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                        ],
                    },
                ],
                temperature=0,
            )
            data = json.loads(resp.choices[0].message.content)
            items = data.get("items", [])
            if not isinstance(items, list):
                raise ValueError("model did not return an items list")
            # Defensive field normalization so downstream consumers don't KeyError.
            norm = []
            for it in items:
                norm.append({
                    "raw": str(it.get("raw", "")),
                    "name": str(it.get("name", "")),
                    "canonical_query": str(it.get("canonical_query", "")),
                    "brand": str(it.get("brand", "")),
                    "quantity": it.get("quantity", 1) or 1,
                    "unit": str(it.get("unit", "")),
                    "is_food": bool(it.get("is_food", False)),
                    "is_composite": bool(it.get("is_composite", False)),
                    "confidence": float(it.get("confidence", 0.0) or 0.0),
                })
            return norm
        except Exception as e:  # noqa: BLE001 — spike: retry any transient failure
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
    raise RuntimeError(f"extraction failed after {MAX_RETRIES} attempts: {last_err}")


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    if not args:
        print("usage: receipt_extraction_spike.py [--json] <image> [<image> ...]", file=sys.stderr)
        sys.exit(2)
    if not os.getenv("OPENAI_API_KEY"):
        print("error: set OPENAI_API_KEY", file=sys.stderr)
        sys.exit(2)

    client = OpenAI()
    out: dict[str, list[dict]] = {}
    log = sys.stderr if as_json else sys.stdout

    for path in args:
        name = os.path.basename(path)
        print(f"\n===== {name} =====", file=log)
        try:
            items = extract(client, path)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR: {e}", file=log)
            continue
        out[name] = items
        for it in items:
            flag = "FOOD" if it["is_food"] else "non-food"
            comp = " [composite]" if it["is_composite"] else ""
            q = f'{it["quantity"]}{(" " + it["unit"]) if it["unit"] else ""}'
            print(f'  {flag:8} {it["raw"]:28.28} -> {it["name"]:26.26} | q="{it["canonical_query"]}" | {q}{comp}', file=log)
        food = sum(1 for i in items if i["is_food"])
        comp = sum(1 for i in items if i["is_composite"])
        resolvable = sum(1 for i in items if i["is_food"] and not i["is_composite"] and i["canonical_query"])
        print(f"  summary: {len(items)} items | {food} food / {len(items)-food} non-food | "
              f"{comp} composite | {resolvable} resolvable (food, non-composite, has query)", file=log)

    if as_json:
        print(json.dumps(out))


if __name__ == "__main__":
    main()
