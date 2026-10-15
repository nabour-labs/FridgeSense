"""fridge-mcp: Oldest items first."""

from datetime import timedelta

from fridgesense.fridge_answers import oldest_items
from fridgesense.table import FridgeTable
from tests.mcp_helpers import ACCOUNT, NOW, iso, put_item

LONG_LIFE = ["condiment", "frozen", "beverage"]


def oldest(category=None, limit=5):
    return oldest_items(FridgeTable(), ACCOUNT, now=NOW, category=category, limit=limit)


def days_ago(n, hours=0):
    return iso(NOW - timedelta(days=n, hours=hours))


# What should I eat first?
def test_what_should_i_eat_first(aws):
    put_item("milk", 1, "dairy", stocked_at=days_ago(8, hours=16))
    put_item("apple", 3, "produce", stocked_at=days_ago(5, hours=16))
    put_item("leftovers", 1, "leftovers", stocked_at=iso(NOW - timedelta(hours=3)))
    result = oldest()
    assert [(i.name, i.count, i.category, i.days_in_fridge) for i in result.items] == [
        ("milk", 1, "dairy", 8),
        ("apple", 3, "produce", 5),
        ("leftovers", 1, "leftovers", 0),
    ]
    assert result.items[0].in_fridge_since == days_ago(8, hours=16)


def test_ties_sorted_by_name(aws):
    put_item("yogurt", 1, stocked_at=days_ago(2))
    put_item("butter", 1, stocked_at=days_ago(2))
    assert [i.name for i in oldest().items] == ["butter", "yogurt"]


# Long-life items left out
def test_long_life_items_left_out(aws):
    put_item("ketchup", 1, "condiment", stocked_at=days_ago(40))
    put_item("soda can", 6, "beverage", stocked_at=days_ago(20))
    put_item("peas", 1, "frozen", stocked_at=days_ago(30))
    put_item("eggs", 6, "dairy", stocked_at=days_ago(5))
    result = oldest()
    assert [i.name for i in result.items] == ["eggs"]
    assert result.skipped_categories == LONG_LIFE


# One category, even a long-life one
def test_one_category_even_a_long_life_one(aws):
    put_item("ketchup", 1, "condiment", stocked_at=days_ago(40))
    put_item("eggs", 6, "dairy", stocked_at=days_ago(5))
    result = oldest(category="Condiment")
    assert [i.name for i in result.items] == ["ketchup"]
    assert result.skipped_categories == []


# Out-of-stock items are not listed
def test_out_of_stock_items_are_not_listed(aws):
    put_item("butter", 0)
    put_item("eggs", 6, stocked_at=days_ago(1))
    assert [i.name for i in oldest().items] == ["eggs"]


# Limit
def test_limit(aws):
    for n in range(8):
        put_item(f"item {n}", 1, stocked_at=days_ago(10 - n))
    assert [i.name for i in oldest(limit=3).items] == ["item 0", "item 1", "item 2"]


def test_default_limit_is_five(aws):
    for n in range(8):
        put_item(f"item {n}", 1, stocked_at=days_ago(10 - n))
    assert len(oldest().items) == 5


# Item saved before stock tracking (fridge-inventory: Item saved before this change)
def test_item_saved_before_stock_tracking(aws):
    put_item("cheese", 2, first_seen_at="2026-10-12T09:00:00.000Z")
    [cheese] = oldest().items
    assert cheese.in_fridge_since == "2026-10-12T09:00:00.000Z"
    assert cheese.days_in_fridge == 3


# Nothing perishable
def test_nothing_perishable(aws):
    put_item("ketchup", 1, "condiment", stocked_at=days_ago(40))
    put_item("milk", 0)
    assert oldest().items == []
