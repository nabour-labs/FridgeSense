"""fridge-mcp: Find an item."""

from fridgesense.fridge_answers import find_item
from fridgesense.table import FridgeTable
from tests.mcp_helpers import ACCOUNT, NOW, put_item


def find(query):
    return find_item(FridgeTable(), ACCOUNT, query, now=NOW)


# Do I have milk?
def test_do_i_have_milk(aws):
    put_item("milk", 1, minutes_ago=12)
    result = find("Milk")
    assert result.in_fridge is True and result.total_count == 1 and result.query == "Milk"
    [match] = result.matches
    assert (match.name, match.count, match.minutes_ago) == ("milk", 1, 12)
    assert match.last_changed_at == "2026-10-15T23:48:00.000Z"


# Plural and partial names
def test_plural_and_partial_names(aws):
    put_item("egg", 6)
    put_item("whole milk", 1)
    eggs = find("eggs")
    assert [m.name for m in eggs.matches] == ["egg"] and eggs.total_count == 6
    assert [m.name for m in find("milk").matches] == ["whole milk"]


# Several matches
def test_several_matches(aws):
    put_item("whole milk", 1)
    put_item("oat milk", 2)
    result = find("milk")
    assert sorted(m.name for m in result.matches) == ["oat milk", "whole milk"]
    assert result.total_count == 3 and result.in_fridge is True


# Run out
def test_run_out(aws):
    put_item("soda can", 0, category="beverage")
    result = find("soda")
    assert result.in_fridge is False and result.total_count == 0
    assert [(m.name, m.count) for m in result.matches] == [("soda can", 0)]


# Never seen
def test_never_seen(aws):
    put_item("milk", 1)
    result = find("caviar")
    assert (result.in_fridge, result.total_count, result.matches) == (False, 0, [])


def test_display_name_is_used(aws):
    put_item("greek yogurt", 4, name="Greek yogurt")
    assert find("yogurt").matches[0].name == "Greek yogurt"
