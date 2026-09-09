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
    # \d* before the point: EatingWell and others write ".25 cup", and a
    # pattern demanding a leading digit reads that as no amount at all.
    ('decimal', re.compile(r'^(\d*\.\d+|\d+)')),                            # 2 / 0.5 / .25
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

# An amount that was never in the source is not an amount. Inventing one put
# "1.0 cup sugar" on 659 recipe rows and "1.0 serving salt" on 1,504 more, and
# neither is distinguishable afterwards from a number the recipe really gave —
# they simply read as fact. Absent is the honest answer, and the columns are
# nullable precisely so it can be said.
DEFAULT_QUANTITY = None
DEFAULT_UNIT = None

# How far past the quantity a unit may sit and still be THE unit. Wide enough
# for adjectives and a masked parenthetical ("2 (14.5 ounce) cans ..."), narrow
# enough to exclude trailing prep phrases ("... cut into pieces").
UNIT_SEARCH_WINDOW = 40

_COMPILED_UNIT_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), name) for pattern, name in UNIT_PATTERNS.items()
]

# Parenthetical asides carry units that are NOT the ingredient's unit —
# "2 (8 ounce) packages cream cheese" is packages, not ounces.
_PARENTHETICAL = re.compile(r'\([^)]*\)')


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


def _match_unit(text: str) -> Optional[str]:
    """The unit belonging to the quantity: the FIRST one in the line.

    The old rule scanned the whole line and took whichever unit had the longest
    NAME, wherever it appeared. That picked up trailing asides — "1/2 cup fresh
    lemon juice, plus 2 tbsp, divided" became tablespoon, and "1 1/2 cups rice
    (or 100 g uncooked)" became gram. Position is what identifies the unit, not
    name length; ties at the same position go to the longer match so "fl oz"
    beats the "oz" inside it.
    """
    masked = _PARENTHETICAL.sub(lambda m: ' ' * len(m.group()), text)

    best_key = None
    best_unit = DEFAULT_UNIT
    for pattern, unit_name in _COMPILED_UNIT_PATTERNS:
        match = pattern.search(masked)
        # A unit only counts if it sits near the quantity. Past that it belongs
        # to a preparation phrase, not the measurement: "1 (14 oz) block
        # extra-firm tofu, cut into pieces" is not measured in pieces.
        if not match or match.start() > UNIT_SEARCH_WINDOW:
            continue
        key = (match.start(), -(match.end() - match.start()))
        if best_key is None or key < best_key:
            best_key, best_unit = key, unit_name
    return best_unit


def format_quantity(value: float) -> str:
    """Render a parsed quantity the way the eKitchen API expects it."""
    if value == int(value):
        return str(int(value))
    # 4dp keeps 1/3 and 5/6 usable without printing float noise.
    return '{0:g}'.format(round(value, 4))


def parse_quantity_and_unit(ingredient_text: str) -> Dict[str, Optional[str]]:
    """
    Parse a leading quantity and a unit out of a raw ingredient string.

    Examples:
        "1/2 cup heavy cream"  -> {'quantity': '0.5', 'unit': 'cup'}
        "½ cup heavy cream"    -> {'quantity': '0.5', 'unit': 'cup'}
        "1 1/2 cups flour"     -> {'quantity': '1.5', 'unit': 'cup'}
        "12 oz ribeye steak"   -> {'quantity': '12',  'unit': 'ounce'}
        "salt to taste"        -> {'quantity': None,  'unit': None}

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

    return {'quantity': quantity, 'unit': _match_unit(remaining_text)}
