"""
Receipt price reading: amount parsing, receipt-level normalization, and the check
that line prices add up to the receipt's own totals. No OpenAI calls.
"""
import pytest

from services.receipt_processor import ReceiptProcessor, _money, check_prices


def item(line_total, discount=0.0, is_food=True):
    return {"line_total": line_total, "discount": discount, "is_food": is_food}


# The lines of a real receipt in the spike set (grocery_receipt_3): a natural foods
# store, including detergent, napkins and a bottle deposit. 47.99 + 1.31 tax = 49.30.
RECEIPT_3_LINES = [3.49, 3.49, 10.99, 5.49, 0.10, 2.49, 2.99, 2.99, 4.49, 2.99, 3.49, 4.99]


@pytest.mark.parametrize("raw,expected", [
    ("$3.49", 3.49),
    ("1.00-", -1.0),
    ("-1.00", -1.0),
    ("1,234.50", 1234.5),
    (2.5, 2.5),
    (None, None),
    ("", None),
    ("n/a", None),
    (True, None),
])
def test_money_parses_receipt_amounts(raw, expected):
    assert _money(raw) == expected


def test_lines_matching_total_minus_tax_is_matched():
    receipt = {"subtotal": None, "tax": 1.31, "total": 49.30}
    check = check_prices([item(p) for p in RECEIPT_3_LINES], receipt)
    assert check["status"] == "matched"
    assert check["items_sum"] == 47.99
    assert check["expected"] == 47.99


def test_subtotal_wins_over_total():
    receipt = {"subtotal": 10.00, "tax": 0.70, "total": 10.70}
    assert check_prices([item(6.00), item(4.00)], receipt)["status"] == "matched"


def test_cropped_receipt_is_partial_not_wrong():
    # grocery_receipt_2 shows only the bottom of a $100.00 Publix receipt.
    receipt = {"subtotal": None, "tax": 0.0, "total": 100.00}
    check = check_prices([item(0.67), item(0.75), item(4.49), item(12.18)], receipt)
    assert check["status"] == "partial"


def test_lines_adding_to_more_than_the_receipt_is_a_mismatch():
    # One misread digit: 2.99 read as 7.99.
    lines = list(RECEIPT_3_LINES)
    lines[6] = 7.99
    receipt = {"subtotal": None, "tax": 1.31, "total": 49.30}
    assert check_prices([item(p) for p in lines], receipt)["status"] == "mismatch"


def test_discounts_reduce_what_was_paid():
    receipt = {"subtotal": 5.00, "tax": None, "total": None}
    check = check_prices([item(4.00, discount=1.00), item(2.00)], receipt)
    assert check["items_sum"] == 5.00
    assert check["status"] == "matched"


def test_no_totals_visible_is_unverified():
    receipt = {"subtotal": None, "tax": None, "total": None}
    assert check_prices([item(3.49)], receipt)["status"] == "unverified"


def test_missing_prices_are_counted():
    receipt = {"subtotal": 3.49, "tax": None, "total": None}
    check = check_prices([item(3.49), item(None)], receipt)
    assert check["missing_prices"] == 1
    assert check["status"] == "matched"


def test_normalize_receipt_drops_what_cannot_be_trusted():
    r = ReceiptProcessor._normalize_receipt({
        "store_name": " Publix Super Market ",
        "store_chain": "Publix",
        "store_zip": "33602-1234",
        "purchased_on": "10/26/2026",  # not ISO: dropped rather than guessed
        "subtotal": "$98.10",
        "tax": None,
        "total": "100.00",
    })
    assert r == {
        "store_name": "Publix Super Market",
        "store_chain": "Publix",
        "store_zip": "33602",
        "purchased_on": "",
        "subtotal": 98.10,
        "tax": None,
        "total": 100.00,
        "items_sold": None,
    }


def test_normalize_receipt_handles_a_missing_block():
    r = ReceiptProcessor._normalize_receipt(None)
    assert r["store_chain"] == "" and r["total"] is None


def test_normalize_item_keeps_discount_positive():
    it = ReceiptProcessor._normalize_item({"raw": "X", "line_total": "2.00", "discount": "-0.50"})
    assert it["line_total"] == 2.00
    assert it["discount"] == 0.50
    assert it["unit_price"] is None


def test_more_lines_than_the_store_sold_is_a_mismatch():
    # A sideways photo the model couldn't read: no totals, and a padded list.
    receipt = {"subtotal": None, "tax": None, "total": None, "items_sold": 7}
    check = check_prices([item(2.98) for _ in range(12)], receipt)
    assert check["status"] == "mismatch"
    assert check["items_sold"] == 7


def test_fewer_lines_than_the_store_sold_is_still_fine():
    receipt = {"subtotal": None, "tax": None, "total": None, "items_sold": 7}
    assert check_prices([item(2.98), item(1.00)], receipt)["status"] == "unverified"


@pytest.mark.parametrize("raw,expected", [(7, 7), ("12", 12), ("7.0", 7), (None, None), ("", None), (0, None), (True, None), ("seven", None)])
def test_items_sold_parses_counts(raw, expected):
    r = ReceiptProcessor._normalize_receipt({"items_sold": raw})
    assert r["items_sold"] == expected
