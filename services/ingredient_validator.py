"""
Ingredient name validation gate.

Guards the global ingredient catalog against extraction garbage. Every name
must pass validate_ingredient_name() before a new global_ingredients row may
be created. This is the fix for catalog pollution documented in
docs/CATALOG_POLLUTION_HANDOFF.md — raw recipe lines, placeholder strings,
and multi-ingredient fragments were being minted as real ingredients.

Pure stdlib, no side effects: safe to import from any pipeline or tool.
"""

import re
from typing import Tuple

# Placeholder / garbage strings that GPT extraction emits when it can't
# identify a real ingredient. These are extraction failures, not ingredients.
GARBAGE_BLOCKLIST = {
    'ingredient', 'ingredients', 'ingredient needed', 'ingredients needed',
    'seasoning ingredient', 'seasoning ingredients',
    'salt and pepper', 'salt & pepper',
    'salt and pepper to taste', 'to taste',
    'optional', 'optional ingredient', 'as needed', 'for garnish', 'garnish',
    'n/a', 'none', 'unknown', 'misc', 'other', 'etc',
    'topping', 'toppings', 'veggy', 'veggie', 'veggies', 'chopped veggy',
}

# Placeholder phrases anywhere in the name ("any other topping of choice",
# "cheese of choice"). Checked as substrings after lowercasing.
GARBAGE_PHRASES = (
    'of choice', 'of your choice', 'any other', 'your favorite', 'your favourite',
)

# "salt and (black|white|ground...) pepper" in any variant is a seasoning
# instruction, not an ingredient.
SALT_AND_PEPPER_RE = re.compile(r'^salt and (\w+ )?pepper$')

# Multi-word names containing "and"/"or" that ARE single real ingredients.
LEGITIMATE_COMPOUND_NAMES = {
    'half and half',
    'pork and beans',
    'sweet and sour sauce',
    'five spice',  # defensive: not compound, but cheap to keep
}

# Measurement / packaging tokens that signal an un-parsed recipe line rather
# than a clean ingredient name ("1 cup dried channa", "1 can of chickpeas").
MEASUREMENT_TOKENS = {
    'cup', 'cups', 'tablespoon', 'tablespoons', 'tbsp', 'teaspoon',
    'teaspoons', 'tsp', 'ounce', 'ounces', 'oz', 'pound', 'pounds', 'lb',
    'lbs', 'gram', 'grams', 'g', 'kg', 'kilogram', 'kilograms', 'ml',
    'milliliter', 'milliliters', 'liter', 'liters', 'litre', 'litres',
    'quart', 'quarts', 'pint', 'pints', 'gallon', 'gallons',
    'can', 'cans', 'jar', 'jars', 'package', 'packages', 'pkg',
    'bottle', 'bottles', 'box', 'boxes', 'bag', 'bags', 'bunch', 'bunches',
    'pinch', 'dash', 'handful', 'drained', 'rinsed', 'divided',
}

MAX_NAME_LENGTH = 40   # longest real ingredient names are well under this
MAX_WORD_COUNT = 5     # e.g. "extra virgin olive oil" = 4 words


def validate_ingredient_name(name: str) -> Tuple[bool, str]:
    """Decide whether *name* is acceptable as a global ingredient name.

    Returns (True, "ok") for valid names, (False, reason) for rejects.
    This must stay conservative in what it rejects: a false reject only
    drops one ingredient line from one recipe; a false accept pollutes the
    shared catalog for every feature keyed on ingredient_id.
    """
    if not name or not name.strip():
        return False, "empty name"

    cleaned = name.strip().lower()

    if len(cleaned) < 2:
        return False, "too short"

    if len(cleaned) > MAX_NAME_LENGTH:
        return False, f"too long ({len(cleaned)} chars > {MAX_NAME_LENGTH})"

    if cleaned in GARBAGE_BLOCKLIST:
        return False, f"blocklisted placeholder: '{cleaned}'"

    if SALT_AND_PEPPER_RE.match(cleaned):
        return False, "seasoning instruction, not an ingredient"

    for phrase in GARBAGE_PHRASES:
        if phrase in cleaned:
            return False, f"placeholder phrase: '{phrase}'"

    # Digits in an ingredient name mean an un-parsed quantity slipped through
    # ("1 cup dried channa...", "7-up"). The rare legit exceptions (e.g.
    # "7 up") are not catalog-worthy base ingredients anyway.
    if re.search(r'\d', cleaned):
        return False, "contains digits (un-parsed quantity)"

    # Punctuation that only appears in raw recipe lines, never in clean names.
    if re.search(r'[(),;:/\\\[\]{}@#$%^*+=<>?!"]', cleaned):
        return False, "contains recipe-line punctuation"

    words = cleaned.split()
    if len(words) > MAX_WORD_COUNT:
        return False, f"too many words ({len(words)} > {MAX_WORD_COUNT})"

    # Multi-ingredient fragments: "salt or pepper", "channa or chickpeas".
    if cleaned not in LEGITIMATE_COMPOUND_NAMES:
        if ' or ' in f' {cleaned} ':
            return False, "multi-ingredient string (contains ' or ')"
        # "and" is riskier to reject outright (compound names exist), so only
        # reject when combined with another garbage signal: blocklist already
        # caught "salt and pepper"; here we catch "X and Y to taste" shapes.
        if ' and ' in f' {cleaned} ' and cleaned.endswith(' to taste'):
            return False, "multi-ingredient string with 'to taste'"

    # Measurement/packaging tokens signal an un-parsed recipe line.
    for word in words:
        if word in MEASUREMENT_TOKENS:
            return False, f"contains measurement/packaging token: '{word}'"

    return True, "ok"
