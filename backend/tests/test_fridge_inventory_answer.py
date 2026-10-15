"""fridge-mcp: What is in the fridge."""

from fridgesense.fridge_answers import inventory
from fridgesense.table import FridgeTable
from tests.mcp_helpers import PK, put_item


# Whole fridge
def test_whole_fridge(aws):
    put_item("eggs", 6, "dairy", name="Eggs")
    put_item("apple", 3, "produce")
    put_item("soda can", 0, "beverage")
    FridgeTable().put({"pk": PK, "sk": "PENDING#x#1", "item": "jam"})
    result = inventory(FridgeTable(), "ava1.ring.account.A1")
    assert [(i.name, i.category, i.count) for i in result.items] == [
        ("Eggs", "dairy", 6),
        ("apple", "produce", 3),
    ]
    assert result.total_items == 2 and result.pending_count == 1


# One category
def test_one_category(aws):
    put_item("eggs", 6, "dairy")
    put_item("milk", 1, "dairy")
    put_item("apple", 3, "produce")
    result = inventory(FridgeTable(), "ava1.ring.account.A1", category="Dairy")
    assert [i.name for i in result.items] == ["eggs", "milk"] and result.total_items == 2


def test_empty_fridge(aws):
    result = inventory(FridgeTable(), "ava1.ring.account.A1")
    assert (result.total_items, result.items, result.pending_count) == (0, [], 0)
