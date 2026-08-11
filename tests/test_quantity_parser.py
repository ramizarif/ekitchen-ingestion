"""
Tests for services.quantity_parser — ingredient quantity/unit parsing.

Regression origin: every fractional quantity silently parsed as 1, because the
decimal pattern was tried before the fraction pattern and matched the "1" of
"1/2". Recipes ingested with "1/2 cup heavy cream" landed in prod as 1 cup.
"""
import pytest

from services.quantity_parser import (
    DEFAULT_QUANTITY,
    DEFAULT_UNIT,
    format_quantity,
    parse_quantity_and_unit,
)


class TestAsciiFractions:
    """The original bug: "1/2" must not parse as 1."""

    @pytest.mark.parametrize("text,quantity,unit", [
        ("1/2 cup heavy cream", "0.5", "cup"),
        ("1/3 cup red wine", "0.3333", "cup"),
        ("1/2 cup freshly grated Parmesan cheese", "0.5", "cup"),
        ("1/2 tsp freshly cracked black pepper", "0.5", "teaspoon"),
        ("3/4 cup milk", "0.75", "cup"),
        ("2/3 cup sugar", "0.6667", "cup"),
        ("1/4 teaspoon salt", "0.25", "teaspoon"),
        ("1/8 tsp cayenne", "0.125", "teaspoon"),
    ])
    def test_simple_fractions(self, text, quantity, unit):
        assert parse_quantity_and_unit(text) == {"quantity": quantity, "unit": unit}

    def test_fraction_with_spaces_around_slash(self):
        assert parse_quantity_and_unit("1 / 2 cup water")["quantity"] == "0.5"

    def test_fraction_never_rounds_up_to_one(self):
        """The exact failure mode that shipped to prod."""
        for text in ("1/2 cup cream", "1/3 cup wine", "1/4 cup stock"):
            assert parse_quantity_and_unit(text)["quantity"] != "1"


class TestMixedNumbers:
    @pytest.mark.parametrize("text,quantity", [
        ("1 1/2 cups flour", "1.5"),
        ("2 1/4 cups water", "2.25"),
        ("1 1/3 cup rice", "1.3333"),
        ("3 3/4 pounds pork shoulder", "3.75"),
    ])
    def test_ascii_mixed_numbers(self, text, quantity):
        assert parse_quantity_and_unit(text)["quantity"] == quantity

    def test_mixed_number_keeps_unit(self):
        assert parse_quantity_and_unit("1 1/2 cups flour")["unit"] == "cup"


class TestUnicodeFractions:
    """Vulgar fractions are what recipe sites and pasted recipes actually use."""

    @pytest.mark.parametrize("text,quantity,unit", [
        ("½ cup heavy cream", "0.5", "cup"),
        ("¼ tsp salt", "0.25", "teaspoon"),
        ("¾ cup sugar", "0.75", "cup"),
        ("⅓ cup red wine", "0.3333", "cup"),
        ("⅔ cup broth", "0.6667", "cup"),
        ("⅛ tsp nutmeg", "0.125", "teaspoon"),
    ])
    def test_bare_vulgar_fraction(self, text, quantity, unit):
        assert parse_quantity_and_unit(text) == {"quantity": quantity, "unit": unit}

    @pytest.mark.parametrize("text,quantity", [
        ("1½ cups flour", "1.5"),
        ("1 ½ cups flour", "1.5"),
        ("2¼ cups water", "2.25"),
        ("2 ¾ pounds chicken", "2.75"),
    ])
    def test_mixed_vulgar_fraction(self, text, quantity):
        assert parse_quantity_and_unit(text)["quantity"] == quantity

    def test_vulgar_fraction_is_not_silently_dropped(self):
        """Before the fix these matched no pattern and defaulted to 1.0."""
        assert parse_quantity_and_unit("½ cup cream")["quantity"] != DEFAULT_QUANTITY


class TestWholeNumbersAndDecimals:
    @pytest.mark.parametrize("text,quantity,unit", [
        ("12 oz ribeye steak", "12", "ounce"),
        ("8 oz rigatoni pasta", "8", "ounce"),
        ("6 cloves garlic, finely minced", "6", "clove"),
        ("2 tbsp butter", "2", "tablespoon"),
        ("1 tbsp olive oil", "1", "tablespoon"),
        ("0.5 cup cream", "0.5", "cup"),
        ("1.25 pounds beef", "1.25", "pound"),
    ])
    def test_plain_quantities(self, text, quantity, unit):
        assert parse_quantity_and_unit(text) == {"quantity": quantity, "unit": unit}


class TestWrittenNumbers:
    @pytest.mark.parametrize("text,quantity", [
        ("two tablespoons butter", "2"),
        ("three cloves garlic", "3"),
        ("ten grams yeast", "10"),
    ])
    def test_written_numbers(self, text, quantity):
        assert parse_quantity_and_unit(text)["quantity"] == quantity

    @pytest.mark.parametrize("text", [
        "tenderloin, trimmed",
        "onion, finely diced",
        "sixteen-bean soup mix",
    ])
    def test_word_prefix_is_not_a_quantity(self, text):
        """Without a word boundary, "tenderloin" parsed as 10."""
        assert parse_quantity_and_unit(text)["quantity"] == DEFAULT_QUANTITY


class TestUnits:
    @pytest.mark.parametrize("text,unit", [
        ("2 fl oz vanilla", "fluid ounce"),
        ("2 oz chocolate", "ounce"),
        ("500 ml stock", "milliliter"),
        ("2 liters water", "liter"),
        ("1 kg potatoes", "kilogram"),
        ("200 g flour", "gram"),
        ("1 lb ground beef", "pound"),
        ("1 head cabbage", "head"),
        ("2 stalks celery", "stalk"),
        ("1 pinch saffron", "pinch"),
    ])
    def test_unit_extraction(self, text, unit):
        assert parse_quantity_and_unit(text)["unit"] == unit

    def test_unknown_unit_falls_back_to_serving(self):
        assert parse_quantity_and_unit("2 large eggs")["unit"] == DEFAULT_UNIT


class TestEdgeCases:
    @pytest.mark.parametrize("text", ["salt, to taste", "freshly cracked black pepper", "", "   "])
    def test_no_quantity_uses_default(self, text):
        assert parse_quantity_and_unit(text)["quantity"] == DEFAULT_QUANTITY

    def test_none_input_does_not_raise(self):
        assert parse_quantity_and_unit(None)["quantity"] == DEFAULT_QUANTITY

    def test_zero_denominator_does_not_raise(self):
        """Nonsense input must degrade, not kill an ingestion run."""
        result = parse_quantity_and_unit("1/0 cup water")
        assert result["unit"] == "cup"
        assert result["quantity"] == "1"

    @pytest.mark.parametrize("text,quantity", [
        ("10-12 oz steak", "10"),
        ("1-2 tbsp chili paste", "1"),
        ("5-7 cloves garlic", "5"),
    ])
    def test_ranges_resolve_to_low_end(self, text, quantity):
        assert parse_quantity_and_unit(text)["quantity"] == quantity


class TestFormatQuantity:
    @pytest.mark.parametrize("value,expected", [
        (1.0, "1"), (12.0, "12"), (0.5, "0.5"), (1.5, "1.5"),
        (0.25, "0.25"), (1 / 3, "0.3333"), (5 / 6, "0.8333"),
    ])
    def test_formatting(self, value, expected):
        assert format_quantity(value) == expected

    def test_no_float_noise(self):
        assert "0000" not in format_quantity(0.1 + 0.2)


class TestAllIngestionPathsShareOneImplementation:
    """The bug survived because this logic was copy-pasted into three classes."""

    def test_services_processor_delegates(self):
        from services.recipe_processor import DirectRecipeProcessor

        parsed = DirectRecipeProcessor.parse_ingredient_quantity_and_unit(
            None, "1/2 cup heavy cream"
        )
        assert parsed == parse_quantity_and_unit("1/2 cup heavy cream")
        assert parsed["quantity"] == "0.5"

    def test_no_inlined_copies_remain(self):
        """Guard against the pattern list being pasted back into a caller."""
        import pathlib

        repo_root = pathlib.Path(__file__).resolve().parent.parent
        offenders = [
            path
            for path in repo_root.rglob("*.py")
            if "quantity_parser" not in path.name
            and "test_" not in path.name
            and "venv" not in path.parts
            and "quantity_patterns" in path.read_text(errors="ignore")
        ]
        assert offenders == [], f"quantity parsing re-inlined in: {offenders}"
