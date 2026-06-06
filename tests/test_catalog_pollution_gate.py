"""
Tests for the catalog-pollution gate (docs/CATALOG_POLLUTION_HANDOFF.md):

1. ingredient name validation — the real garbage that reached prod must be
   rejected; real ingredients (including the Caribbean gap names) must pass.
2. catalog-wide match candidate generation — the misses and false matches
   observed in prod must behave correctly:
   - 'escallion' must surface 'scallion' as a candidate (old ILIKE never could)
   - 'olive juice' must NOT surface 'ice' (old substring matcher did)
   - 'corned beef brisket' may surface 'corn' only as a low-trust candidate
     (the GPT arbiter rejects it; what matters is no AUTO-merge path exists)
"""
import pytest

from services.ingredient_validator import validate_ingredient_name
from services.ingredient_processor import DirectIngredientProcessor


# ── Validation gate ──────────────────────────────────────────────────────

# Garbage observed in prod on 2026-06-06 (must all be rejected)
PROD_GARBAGE = [
    "ingredient needed",
    "seasoning ingredient",
    "salt and pepper",
    "salt and black pepper",
    "1 cup dried channa (chickpeas) or 1 can of chickpeas (drained and rinsed)3 medium potato",
]

# Genuinely-missing ingredients from the same batch (must all pass)
PROD_LEGIT = [
    "callaloo", "ackee", "plantain", "culantro", "escallion",
    "pimento seed", "red snapper", "codfish", "pork loin chop",
    "corned beef brisket",
]


@pytest.mark.parametrize("name", PROD_GARBAGE)
def test_rejects_prod_garbage(name):
    ok, reason = validate_ingredient_name(name)
    assert not ok, f"'{name}' should be rejected but passed"
    assert reason


@pytest.mark.parametrize("name", PROD_LEGIT)
def test_accepts_prod_legit_ingredients(name):
    ok, reason = validate_ingredient_name(name)
    assert ok, f"'{name}' should pass but was rejected: {reason}"


@pytest.mark.parametrize("name,why", [
    ("", "empty"),
    ("   ", "whitespace only"),
    ("x", "single char"),
    ("2 cups flour", "embedded quantity"),
    ("chickpeas (drained and rinsed)", "recipe-line punctuation"),
    ("channa or chickpeas", "multi-ingredient 'or'"),
    ("1 can of chickpeas", "quantity + packaging"),
    ("butter, softened", "comma fragment"),
    ("salt and pepper to taste", "to-taste fragment"),
    ("a very long ingredient name that cannot possibly be real food", "too long"),
    # Slipped through the first prod triage run (2026-06-06):
    ("salt and white pepper", "seasoning instruction variant"),
    ("salt and ground pepper", "seasoning instruction variant"),
    ("any other topping of choice", "placeholder phrase"),
    ("cheese of your choice", "placeholder phrase"),
    ("chopped veggy", "vague placeholder"),
])
def test_rejects_garbage_shapes(name, why):
    ok, _ = validate_ingredient_name(name)
    assert not ok, f"should reject ({why}): '{name}'"


@pytest.mark.parametrize("name", [
    "scallion", "flour", "extra virgin olive oil", "half and half",
    "red bell pepper", "boneless skinless chicken thigh", "egg",
])
def test_accepts_normal_ingredients(name):
    ok, reason = validate_ingredient_name(name)
    assert ok, f"'{name}' should pass but was rejected: {reason}"


# ── Candidate generation ─────────────────────────────────────────────────

CATALOG = [
    {"id": "id-scallion", "name": "scallion"},
    {"id": "id-cod", "name": "cod"},
    {"id": "id-ice", "name": "ice"},
    {"id": "id-corn", "name": "corn"},
    {"id": "id-pork-loin", "name": "pork loin"},
    {"id": "id-olive", "name": "olive"},
    {"id": "id-basil", "name": "basil"},
    {"id": "id-almond", "name": "almond"},
]


@pytest.fixture(scope="module")
def processor():
    return DirectIngredientProcessor(log_to_file=False)


def candidate_names(processor, query):
    return [c["name"] for c in processor._find_match_candidates(query, catalog=CATALOG)]


def test_exact_match_short_circuits(processor):
    cands = processor._find_match_candidates("scallion", catalog=CATALOG)
    assert len(cands) == 1
    assert cands[0]["match_type"] == "exact"
    assert cands[0]["id"] == "id-scallion"


def test_escallion_surfaces_scallion(processor):
    # The prod miss: ILIKE '%escallion%' never returned 'scallion'.
    assert "scallion" in candidate_names(processor, "escallion")


def test_codfish_surfaces_cod(processor):
    assert "cod" in candidate_names(processor, "codfish")


def test_pork_loin_chop_surfaces_pork_loin(processor):
    assert "pork loin" in candidate_names(processor, "pork loin chop")


def test_olive_juice_does_not_surface_ice(processor):
    # The prod false-match: substring 'ice' ⊂ 'olive ju-ice'.
    assert "ice" not in candidate_names(processor, "olive juice")


def test_no_arbiter_means_no_fuzzy_merge(processor):
    # Without OpenAI available, only an exact match may resolve — a fuzzy
    # candidate must never silently merge (that's how olive juice→ice landed).
    saved = processor.openai_client
    processor.openai_client = None
    try:
        cands = processor._find_match_candidates("corned beef brisket", catalog=CATALOG)
        resolution = processor._resolve_to_catalog("corned beef brisket", cands)
        assert resolution["match"] is None
    finally:
        processor.openai_client = saved


def test_exact_resolves_without_gpt(processor):
    saved = processor.openai_client
    processor.openai_client = None
    try:
        cands = processor._find_match_candidates("cod", catalog=CATALOG)
        resolution = processor._resolve_to_catalog("cod", cands)
        assert resolution["match"] is not None
        assert resolution["match"]["id"] == "id-cod"
    finally:
        processor.openai_client = saved


def test_create_refuses_invalid_name(processor):
    """The hard gate: no code path may create a garbage-named ingredient."""
    from services.ingredient_processor import IngredientData
    bad = IngredientData(name="1 cup dried channa (chickpeas) or 1 can of chickpeas")
    assert processor.create_ekitchen_ingredient(bad) is None
