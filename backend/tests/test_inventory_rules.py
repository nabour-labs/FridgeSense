"""fridge-inventory: shared quantity rule and pending change bookkeeping."""

from fridgesense.inventory import quantity_put, save_task
from fridgesense.table import FridgeTable, account_pk

PK = account_pk("ava1.ring.account.A1")
WHEN = "2026-08-14T13:53:41.000Z"


def test_quantity_put_creates_new_item():
    item = quantity_put(None, PK, "whole milk", "Whole Milk", "dairy", 2, WHEN)
    assert item == {
        "pk": PK,
        "sk": "ITEM#whole milk",
        "name": "Whole Milk",
        "category": "dairy",
        "quantity": 2,
        "first_seen_at": WHEN,
        "last_changed_at": WHEN,
        "stocked_at": WHEN,
        "peak_quantity": 2,
    }


def test_quantity_put_keeps_existing_name_category_and_first_seen():
    current = {"name": "Eggs", "category": "dairy", "quantity": 6, "first_seen_at": "2026-08-01"}
    item = quantity_put(current, PK, "eggs", "eggs", "other", 12, WHEN)
    assert (item["name"], item["category"], item["quantity"], item["first_seen_at"]) == (
        "Eggs",
        "dairy",
        18,
        "2026-08-01",
    )


def test_quantity_put_never_negative():
    assert (
        quantity_put({"quantity": 1}, PK, "soda can", "soda can", "beverage", -3, WHEN)["quantity"]
        == 0
    )


def test_quantity_put_ignores_removal_of_unknown_item():
    assert quantity_put(None, PK, "yogurt", "yogurt", "dairy", -1, WHEN) is None


# Low-confidence item (extended): pending items remember their change's position
def test_pending_items_store_change_index(aws):
    table = FridgeTable()
    door_sk = "DOOR#2026-08-14T13:53:16.000Z#ava1.ring.device.D1"
    table.put(
        {
            "pk": PK,
            "sk": door_sk,
            "status": "analyzing",
            "opened_at": "2026-08-14T13:53:16.000Z",
            "closed_at": WHEN,
        }
    )
    save_task(
        table,
        {
            "account_id": "ava1.ring.account.A1",
            "door_sk": door_sk,
            "analysis": {
                "added": [{"item": "milk", "category": "dairy", "quantity": 1, "confidence": 0.9}],
                "removed": [
                    {"item": "eggs", "category": "dairy", "quantity": 2, "confidence": 0.5},
                    {"item": "jam", "category": "condiment", "quantity": 1, "confidence": 0.4},
                ],
            },
        },
    )
    pending = sorted(table.query("ava1.ring.account.A1", "PENDING#"), key=lambda p: p["sk"])
    assert [(p["item"], p["change_index"]) for p in pending] == [("eggs", 1), ("jam", 2)]
