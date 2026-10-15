"""fridge-inventory: adding, editing and deleting items by hand."""

import pytest

from fridgesense.inventory import (
    InvalidItem,
    ItemExists,
    ItemNotFound,
    add_item,
    check_category,
    clean_name,
    delete_item,
    edit_item,
    save_task,
)
from fridgesense.table import FridgeTable, account_pk


# Blank or long name
@pytest.mark.parametrize("name", ["", "   ", "x" * 61, 5, None])
def test_blank_or_long_name(name):
    with pytest.raises(InvalidItem, match="name must be 1 to 60 characters"):
        clean_name(name)


# Name at the limit
def test_name_at_the_limit():
    assert clean_name("x" * 60) == ("x" * 60, "x" * 60)
    assert clean_name(" Salted  Butter ") == ("salted butter", "Salted Butter")


# Unknown category
@pytest.mark.parametrize("category", ["sweets", "Dairy ", "", None, 3])
def test_unknown_category(category):
    with pytest.raises(InvalidItem, match="unknown category"):
        check_category(category)


def test_known_category():
    assert check_category("dairy") == "dairy"


ACCOUNT = "ava1.ring.account.A1"
PK = account_pk(ACCOUNT)
NOW = "2026-10-16T09:00:00.000Z"
LATER = "2026-10-17T09:00:00.000Z"
EARLIER = "2026-10-12T09:00:00.000Z"


@pytest.fixture
def table(aws):
    return FridgeTable()


def put_item(table, key, quantity, name=None, category="other", **extra):
    table.put(
        {
            "pk": PK,
            "sk": f"ITEM#{key}",
            "name": name or key,
            "category": category,
            "quantity": quantity,
            "first_seen_at": EARLIER,
            "last_changed_at": EARLIER,
            **extra,
        }
    )


def get(table, key):
    return table.get(PK, f"ITEM#{key}")


# Add a new item
def test_add_a_new_item(table):
    add_item(table, ACCOUNT, " Salted  Butter ", "dairy", 2, now=NOW)
    assert get(table, "salted butter") == {
        "pk": PK,
        "sk": "ITEM#salted butter",
        "name": "Salted Butter",
        "category": "dairy",
        "quantity": 2,
        "first_seen_at": NOW,
        "last_changed_at": NOW,
        "stocked_at": NOW,
        "peak_quantity": 2,
    }


# Add to an existing item
def test_add_to_an_existing_item(table):
    put_item(table, "eggs", 4, name="Eggs", category="other")
    add_item(table, ACCOUNT, "EGGS", "dairy", 6, now=NOW)
    eggs = get(table, "eggs")
    assert (eggs["quantity"], eggs["category"], eggs["name"]) == (10, "dairy", "Eggs")
    assert (eggs["first_seen_at"], eggs["last_changed_at"]) == (EARLIER, NOW)


# Add to an item that ran out
def test_add_to_an_item_that_ran_out(table):
    put_item(table, "milk", 0, category="dairy")
    add_item(table, ACCOUNT, "milk", "dairy", 1, now=NOW)
    milk = get(table, "milk")
    assert (milk["quantity"], milk["stocked_at"], milk["peak_quantity"]) == (1, NOW, 1)


@pytest.mark.parametrize("quantity", [0, -1, "2", 1.5, True])
def test_add_needs_a_whole_quantity_of_one_or_more(table, quantity):
    with pytest.raises(InvalidItem, match="quantity must be a whole number of 1 or more"):
        add_item(table, ACCOUNT, "Butter", "dairy", quantity, now=NOW)
    assert get(table, "butter") is None


def test_add_with_bad_name_or_category_changes_nothing(table):
    with pytest.raises(InvalidItem):
        add_item(table, ACCOUNT, "   ", "dairy", 1, now=NOW)
    with pytest.raises(InvalidItem):
        add_item(table, ACCOUNT, "Butter", "sweets", 1, now=NOW)
    assert table.query(ACCOUNT, "ITEM#") == []


# Rename an item
def test_rename_an_item(table):
    put_item(table, "bottle", 1, stocked_at=EARLIER, peak_quantity=1)
    edit_item(table, ACCOUNT, "bottle", name="Oat Milk", category="dairy", now=NOW)
    assert get(table, "bottle") is None
    assert get(table, "oat milk") == {
        "pk": PK,
        "sk": "ITEM#oat milk",
        "name": "Oat Milk",
        "category": "dairy",
        "quantity": 1,
        "first_seen_at": EARLIER,
        "last_changed_at": NOW,
        "stocked_at": EARLIER,
        "peak_quantity": 1,
    }


# Change only the capitalization
def test_change_only_the_capitalization(table):
    put_item(table, "oat milk", 2, name="oat milk", category="dairy")
    edit_item(table, ACCOUNT, "oat milk", name="Oat Milk", now=NOW)
    milk = get(table, "oat milk")
    assert (milk["name"], milk["quantity"], milk["category"]) == ("Oat Milk", 2, "dairy")
    assert milk["last_changed_at"] == NOW


# Change only the category
def test_change_only_the_category(table):
    put_item(table, "kefir", 3, name="Kefir", category="other")
    edit_item(table, ACCOUNT, "kefir", category="dairy", now=NOW)
    kefir = get(table, "kefir")
    assert (kefir["category"], kefir["quantity"], kefir["name"]) == ("dairy", 3, "Kefir")


# Rename and recount together
def test_rename_and_recount_together(table):
    put_item(table, "bottle", 1, stocked_at=EARLIER, peak_quantity=1)
    edit_item(table, ACCOUNT, "bottle", name="Oat Milk", quantity=3, now=NOW)
    milk = get(table, "oat milk")
    assert (milk["quantity"], milk["peak_quantity"], milk["stocked_at"]) == (3, 3, EARLIER)
    assert get(table, "bottle") is None


def test_edit_with_bad_fields_changes_nothing(table):
    put_item(table, "eggs", 6, category="dairy")
    for fields in ({"name": "   "}, {"category": "sweets"}, {"quantity": -1}):
        with pytest.raises(InvalidItem):
            edit_item(table, ACCOUNT, "eggs", now=NOW, **fields)
    eggs = get(table, "eggs")
    assert (eggs["quantity"], eggs["category"], eggs["last_changed_at"]) == (6, "dairy", EARLIER)


# Rename onto another item
def test_rename_onto_another_item(table):
    put_item(table, "bottle", 1)
    put_item(table, "oat milk", 2, name="Oat Milk", category="dairy")
    before = (get(table, "bottle"), get(table, "oat milk"))
    with pytest.raises(ItemExists):
        edit_item(table, ACCOUNT, "bottle", name="Oat Milk", now=NOW)
    assert (get(table, "bottle"), get(table, "oat milk")) == before


# Edit an unknown item
def test_edit_an_unknown_item(table):
    with pytest.raises(ItemNotFound):
        edit_item(table, ACCOUNT, "yogurt", name="Greek Yogurt", now=NOW)
    assert table.query(ACCOUNT, "ITEM#") == []


# Delete an item
def test_delete_an_item(table):
    put_item(table, "mystery jar", 1)
    delete_item(table, ACCOUNT, "mystery jar")
    assert get(table, "mystery jar") is None


# Delete an out-of-stock item
def test_delete_an_out_of_stock_item(table):
    put_item(table, "soda can", 0, category="beverage")
    delete_item(table, ACCOUNT, "soda can")
    assert table.query(ACCOUNT, "ITEM#") == []


# Delete an unknown item
def test_delete_an_unknown_item(table):
    put_item(table, "eggs", 6)
    with pytest.raises(ItemNotFound):
        delete_item(table, ACCOUNT, "yogurt")
    assert [i["sk"] for i in table.query(ACCOUNT, "ITEM#")] == ["ITEM#eggs"]


DOOR_SK = "DOOR#2026-10-16T08:00:00.000Z#ava1.ring.device.D1"


def save_door_event(table, *changes):
    table.put(
        {
            "pk": PK,
            "sk": DOOR_SK,
            "status": "analyzing",
            "opened_at": "2026-10-16T08:00:00.000Z",
            "closed_at": "2026-10-17T07:30:00.000Z",
        }
    )
    save_task(
        table,
        {
            "account_id": ACCOUNT,
            "door_sk": DOOR_SK,
            "analysis": {"added": list(changes), "removed": []},
        },
    )


# Delete leaves history alone
def test_delete_leaves_history_alone(table):
    put_item(table, "chocolate bar", 2, category="snack")
    chocolate = {"item": "chocolate bar", "category": "snack", "quantity": 1}
    save_door_event(table, chocolate | {"confidence": 0.9}, chocolate | {"confidence": 0.5})
    door = table.get(PK, DOOR_SK)
    pending = table.query(ACCOUNT, "PENDING#")
    assert len(pending) == 1
    delete_item(table, ACCOUNT, "chocolate bar")
    assert table.get(PK, DOOR_SK) == door
    assert table.query(ACCOUNT, "PENDING#") == pending


# Item comes back after delete
def test_item_comes_back_after_delete(table):
    put_item(table, "milk", 3, category="dairy", stocked_at=EARLIER, peak_quantity=3)
    delete_item(table, ACCOUNT, "milk")
    save_door_event(table, {"item": "milk", "category": "dairy", "quantity": 1, "confidence": 0.9})
    when = "2026-10-17T07:30:00.000Z"
    milk = get(table, "milk")
    assert (milk["quantity"], milk["first_seen_at"], milk["stocked_at"], milk["peak_quantity"]) == (
        1,
        when,
        when,
        1,
    )
