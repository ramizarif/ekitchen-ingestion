"""
Ingredient quantity/unit parsing — the single implementation shared by every
ingestion path.

This logic used to be copy-pasted into three classes (services.recipe_processor,
legacy direct_recipe_processor, tools/data-maintenance rebuild). A bug in the
quantity pattern ordering therefore had to be fixed in three places, so it never
was: every fractional quantity ("1/2 cup heavy cream") silently parsed as 1.
All three now delegate here.
"""
import re
from typing import Dict, Optional

# Unicode vulgar fractions. Recipe sites and hand-authored recipes use these
# constantly ("½ cup"); the old ASCII-only patterns never matched them, so they
# fell through to the default quantity of 1.
VULGAR_FRACTIONS = {
    '¼': 0.25, '½': 0.5, '¾': 0.75,
    '⅐': 1 / 7, '⅑': 1 / 9, '⅒': 0.1,
    '⅓': 1 / 3, '⅔': 2 / 3,
    '⅕': 0.2, '⅖': 0.4, '⅗': 0.6, '⅘': 0.8,
    '⅙': 1 / 6, '⅚': 5 / 6,
    '⅛': 0.125, '⅜': 0.375, '⅝': 0.625, '⅞': 0.875,
}
_VULGAR_CLASS = '[' + ''.join(VULGAR_FRACTIONS) + ']'

WRITTEN_NUMBERS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
}

# Quantity forms, MOST SPECIFIC FIRST — this ordering is the whole point.
# A leading-decimal pattern matches the "1" of "1/2" and, because the scan
# stops at the first hit, swallows the fraction. Mixed numbers and fractions
# must therefore be tried before the plain decimal form.
_QUANTITY_PATTERNS = (
    ('mixed_ascii', re.compile(r'^(\d+)\s+(\d+)\s*/\s*(\d+)')),           # 1 1/2
    ('mixed_vulgar', re.compile(r'^(\d+)\s*(' + _VULGAR_CLASS + ')')),    # 1½ / 1 ½
    ('fraction', re.compile(r'^(\d+)\s*/\s*(\d+)')),                      # 1/2
    ('vulgar', re.compile(r'^(' + _VULGAR_CLASS + ')')),                  # ½
    ('decimal', re.compile(r'^(\d+(?:\.\d+)?)')),                         # 2 / 0.5
    # \b matters: without it "tenderloin" matches "ten" and parses as 10.
    ('written', re.compile(r'^(one|two|three|four|five|six|seven|eight|nine|ten)\b',
                           re.IGNORECASE)),
)

# Unit patterns, unchanged from the original implementation.
UNIT_PATTERNS = {
    # Volume
    r'\b(cups?|cup)\b': 'cup',
    r'\b(tablespoons?|tablespoon|tbsp|tbs)\b': 'tablespoon',
    r'\b(teaspoons?|teaspoon|tsp)\b': 'teaspoon',
    r'\b(quarts?|quart|qt)\b': 'quart',
    r'\b(pints?|pint|pt)\b': 'pint',
    r'\b(gallons?|gallon|gal)\b': 'gallon',
    r'\b(fluid ounces?|fluid ounce|fl oz|floz)\b': 'fluid ounce',
    r'\b(liters?|liter|litres?|litre|l)\b': 'liter',
    r'\b(milliliters?|milliliter|ml)\b': 'milliliter',

    # Weight
    r'\b(pounds?|pound|lbs?|lb)\b': 'pound',
    r'\b(ounces?|ounce|oz)\b': 'ounce',
    r'\b(grams?|gram|g)\b': 'gram',
    r'\b(kilograms?|kilogram|kg)\b': 'kilogram',

    # Count/pieces
    r'\b(pieces?|piece)\b': 'piece',
    r'\b(slices?|slice)\b': 'slice',
    r'\b(cloves?|clove)\b': 'clove',
    r'\b(stalks?|stalk)\b': 'stalk',
    r'\b(heads?|head)\b': 'head',
    r'\b(bunches?|bunch)\b': 'bunch',
    r'\b(strips?|strip)\b': 'strip',

    # Special
    r'\b(cans?|can)\b': 'can',
    r'\b(packages?|package|pkg)\b': 'package',
    r'\b(jars?|jar)\b': 'jar',
    r'\b(bottles?|bottle)\b': 'bottle',
    r'\b(pinch|pinches)\b': 'pinch',
    r'\b(dash|dashes)\b': 'dash',
}

DEFAULT_QUANTITY = "1.0"
DEFAULT_UNIT = "serving"

# Sorted once at import: longer unit names first, so "fluid ounce" wins over
# "ounce" and "milliliter" over "liter".
_SORTED_UNIT_PATTERNS = sorted(
    UNIT_PATTERNS.items(), key=lambda item: len(item[1]), reverse=True
)


def _match_quantity(text: str):
    """Return (value, end_offset) for the leading quantity, or (None, 0)."""
    for kind, pattern in _QUANTITY_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        try:
            if kind == 'mixed_ascii':
                whole, numerator, denominator = (int(g) for g in match.groups())
                value = whole + numerator / denominator
            elif kind == 'mixed_vulgar':
                value = int(match.group(1)) + VULGAR_FRACTIONS[match.group(2)]
            elif kind == 'fraction':
                numerator, denominator = int(match.group(1)), int(match.group(2))
                value = numerator / denominator
            elif kind == 'vulgar':
                value = VULGAR_FRACTIONS[match.group(1)]
            elif kind == 'decimal':
                value = float(match.group(1))
            else:  # written
                value = float(WRITTEN_NUMBERS[match.group(1).lower()])
        except ZeroDivisionError:
            # Nonsense like "1/0 cup" — fall through to the next (looser) form
            # rather than blowing up the whole ingestion run.
            continue
        return value, match.end()
    return None, 0


def format_quantity(value: float) -> str:
    """Render a parsed quantity the way the eKitchen API expects it."""
    if value == int(value):
        return str(int(value))
    # 4dp keeps 1/3 and 5/6 usable without printing float noise.
    return '{0:g}'.format(round(value, 4))


def parse_quantity_and_unit(ingredient_text: str) -> Dict[str, str]:
    """
    Parse a leading quantity and a unit out of a raw ingredient string.

    Examples:
        "1/2 cup heavy cream"  -> {'quantity': '0.5', 'unit': 'cup'}
        "½ cup heavy cream"    -> {'quantity': '0.5', 'unit': 'cup'}
        "1 1/2 cups flour"     -> {'quantity': '1.5', 'unit': 'cup'}
        "12 oz ribeye steak"   -> {'quantity': '12',  'unit': 'ounce'}
        "salt to taste"        -> {'quantity': '1.0', 'unit': 'serving'}

    Ranges ("10-12 oz steak") resolve to the low end, which is what the
    original implementation did by accident and is the safer default for
    nutrition math.
    """
    remaining_text = (ingredient_text or "").lower().strip()

    value, end = _match_quantity(remaining_text)
    if value is None:
        quantity = DEFAULT_QUANTITY
    else:
        quantity = format_quantity(value)
        remaining_text = remaining_text[end:].strip()

    unit = DEFAULT_UNIT
    for pattern, unit_name in _SORTED_UNIT_PATTERNS:
        if re.search(pattern, remaining_text, re.IGNORECASE):
            unit = unit_name
            break

    return {'quantity': quantity, 'unit': unit}
