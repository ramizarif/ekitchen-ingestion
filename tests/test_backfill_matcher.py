"""
Tests for the row matcher in scripts/backfill_fractional_quantities.py.

Regression origin: the name check was
    all(tok in line for tok in name.split() if len(tok) > 3)
An ingredient whose name has no token longer than 3 characters ("msg", "oil")
produces all([]), which is vacuously True — so such a row matched ANY source
line. That wrote "1/4 tsp cayenne" onto a recipe's oil row in production.
"""
import importlib.util
import os

import pytest

_PATH = os.path.join(os.path.dirname(__file__), '..', 'scripts',
                     'backfill_fractional_quantities.py')
_spec = importlib.util.spec_from_file_location("backfill_fractional_quantities", _PATH)
backfill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backfill)

match_row = backfill.match_row


def row(name, quantity, unit):
    return {"name": name, "quantity": quantity, "unit": unit}


class TestShortIngredientNames:
    def test_short_name_does_not_match_unrelated_line(self):
        """The exact bad write: 'oil' must not claim a cayenne line."""
        rows = [row("oil", "1", "teaspoon")]
        assert match_row("1/4 tsp cayenne or chipotle powder", "1", "teaspoon",
                         {"quantity": "0.25", "unit": "teaspoon"}, rows, set()) is None

    def test_msg_does_not_match_sugar_line(self):
        rows = [row("msg", "1", "teaspoon")]
        assert match_row("1/4 teaspoon sugar", "1", "teaspoon",
                         {"quantity": "0.25", "unit": "teaspoon"}, rows, set()) is None

    def test_short_name_still_matches_its_own_line(self):
        rows = [row("oil", "1", "tablespoon")]
        assert match_row("1/2 tablespoon oil", "1", "tablespoon",
                         {"quantity": "0.5", "unit": "tablespoon"}, rows, set()) == 0


class TestNormalMatching:
    def test_matches_on_full_name(self):
        rows = [row("heavy cream", "1", "cup")]
        assert match_row("1/2 cup heavy cream", "1", "cup",
                         {"quantity": "0.5", "unit": "cup"}, rows, set()) == 0

    def test_ambiguous_rows_are_not_matched(self):
        rows = [row("maple syrup", "1", "cup"), row("maple syrup", "1", "cup")]
        assert match_row("1/2 cup maple syrup", "1", "cup",
                         {"quantity": "0.5", "unit": "cup"}, rows, set()) is None

    def test_claimed_rows_are_skipped(self):
        rows = [row("milk", "1", "cup")]
        assert match_row("1/2 cup milk", "1", "cup",
                         {"quantity": "0.5", "unit": "cup"}, rows, {0}) is None

    def test_wrong_unit_is_not_matched(self):
        rows = [row("milk", "1", "tablespoon")]
        assert match_row("1/2 cup milk", "1", "cup",
                         {"quantity": "0.5", "unit": "cup"}, rows, set()) is None

    def test_already_corrected_quantity_still_matches(self):
        """After the quantity pass, the row holds the corrected value."""
        rows = [row("milk", "0.5", "cup")]
        assert match_row("1/2 cup milk", "1", "cup",
                         {"quantity": "0.5", "unit": "cup"}, rows, set()) == 0

    def test_unit_alias_matches(self):
        rows = [row("salt", "1", "tsp")]
        assert match_row("1/2 teaspoon salt", "1", "teaspoon",
                         {"quantity": "0.5", "unit": "teaspoon"}, rows, set()) == 0


class TestHistoricParserReproduction:
    @pytest.mark.parametrize("text,expected", [
        ("1/2 cup heavy cream", "1"),
        ("2/3 cup sugar", "2"),
        ("3/4 cup lentils", "3"),
        ("½ cup cream", "1.0"),
        ("12 oz steak", "12"),
        ("tenderloin, trimmed", "10"),
    ])
    def test_historic_quantity(self, text, expected):
        """Must reproduce the buggy parser exactly, or the audit misidentifies rows."""
        assert backfill.historic_quantity(text) == expected

    def test_historic_unit_takes_longest_named(self):
        line = "1/2 cup fresh lemon juice, plus 2 tbsp, divided"
        assert backfill.historic_unit(line, backfill.historic_remaining(line)) == "tablespoon"
