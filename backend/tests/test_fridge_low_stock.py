"""fridge-mcp: Shopping list from what ran out or is low."""

from fridgesense.fridge_answers import low_stock
from fridgesense.table import FridgeTable
from tests.mcp_helpers import ACCOUNT, NOW, put_item

DAY = 24 * 60


def shopping():
    return low_stock(FridgeTable(), ACCOUNT, now=NOW)


# What do I need to buy?
def test_what_do_i_need_to_buy(aws):
    put_item("milk", 0, minutes_ago=DAY + 60)
    put_item("butter", 0, minutes_ago=3 * DAY + 60)
    put_item("eggs", 2, peak_quantity=12)
    result = shopping()
    assert [(i.name, i.category, i.days_ago) for i in result.ran_out] == [
        ("milk", "dairy", 1),
        ("butter", "dairy", 3),
    ]
    assert result.ran_out[0].ran_out_at == "2026-10-14T23:00:00.000Z"
    assert [i.model_dump() for i in result.running_low] == [
        {"name": "eggs", "category": "dairy", "count": 2, "usual_count": 12}
    ]


# Old run-outs are dropped
def test_old_run_outs_are_dropped(aws):
    put_item("caviar", 0, minutes_ago=31 * DAY)
    put_item("milk", 0, minutes_ago=29 * DAY)
    assert [i.name for i in shopping().ran_out] == ["milk"]


# At most ten run-outs
def test_at_most_ten_run_outs(aws):
    for n in range(12):
        put_item(f"item {n:02}", 0, minutes_ago=(n + 1) * 60)
    assert [i.name for i in shopping().ran_out] == [f"item {n:02}" for n in range(10)]


# Not low yet
def test_not_low_yet(aws):
    put_item("yogurt", 2, peak_quantity=4)
    put_item("apple", 3, "produce", peak_quantity=12)
    assert [i.name for i in shopping().running_low] == ["apple"]


def test_running_low_sorted_by_name(aws):
    put_item("yogurt", 1, peak_quantity=8)
    put_item("apple", 1, "produce", peak_quantity=8)
    assert [i.name for i in shopping().running_low] == ["apple", "yogurt"]


# Single item never counts as low
def test_single_item_never_counts_as_low(aws):
    put_item("milk", 1, peak_quantity=1)
    put_item("cheese", 1)  # saved before peak tracking: peak reads as its count
    assert shopping().running_low == []


# Nothing to buy
def test_nothing_to_buy(aws):
    put_item("eggs", 12, peak_quantity=12)
    result = shopping()
    assert (result.ran_out, result.running_low) == ([], [])
