"""fridge-inventory: saving an analysis to the inventory."""

import pytest

from fridgesense.inventory import normalize_name, save_task
from fridgesense.table import FridgeTable, account_pk

ACCOUNT = "ava1.ring.account.A1"
PK = account_pk(ACCOUNT)
OPENED = "2026-08-14T13:53:16.000Z"
CLOSED = "2026-08-14T13:53:41.000Z"
DOOR_SK = f"DOOR#{OPENED}#ava1.ring.device.D1"


@pytest.fixture
def table(aws):
    t = FridgeTable()
    t.put(
        {"pk": PK, "sk": DOOR_SK, "status": "analyzing", "opened_at": OPENED, "closed_at": CLOSED}
    )
    return t


def change(item, quantity=1, confidence=0.9, category="dairy"):
    return {"item": item, "category": category, "quantity": quantity, "confidence": confidence}


def save(table, added=(), removed=()):
    state = {
        "account_id": ACCOUNT,
        "door_sk": DOOR_SK,
        "analysis": {"added": list(added), "removed": list(removed)},
    }
    return save_task(table, state)


def stock(table, item):
    return table.get(PK, f"ITEM#{item}")


def put_stock(table, key, quantity, name=None, category="dairy"):
    table.put(
        {
            "pk": PK,
            "sk": f"ITEM#{key}",
            "name": name or key,
            "category": category,
            "quantity": quantity,
            "first_seen_at": "2026-08-01T00:00:00.000Z",
            "last_changed_at": "2026-08-01T00:00:00.000Z",
        }
    )


def door(table):
    return table.get(PK, DOOR_SK)


def test_normalize_name():
    assert normalize_name(" Whole  Milk ") == ("whole milk", "Whole Milk")


# New item added
def test_new_item_added(table):
    save(table, added=[change(" Whole  Milk ")])
    item = stock(table, "whole milk")
    assert item["quantity"] == 1
    assert item["category"] == "dairy"
    assert item["name"] == "Whole Milk"
    assert item["last_changed_at"] == CLOSED
    assert item["first_seen_at"] == CLOSED


# Existing item added again
def test_existing_item_added_again(table):
    put_stock(table, "eggs", 6)
    save(table, added=[change("eggs", 12, 0.86)])
    item = stock(table, "eggs")
    assert item["quantity"] == 18
    assert item["first_seen_at"] == "2026-08-01T00:00:00.000Z"


# Item removed
def test_item_removed(table):
    put_stock(table, "chocolate bar", 2, category="snack")
    save(table, removed=[change("Chocolate bar", 1, 0.8, "snack")])
    assert stock(table, "chocolate bar")["quantity"] == 1


# Removing more than is known
def test_removing_more_than_is_known(table):
    put_stock(table, "soda can", 1, category="beverage")
    save(table, removed=[change("soda can", 3, 0.9, "beverage")])
    item = stock(table, "soda can")
    assert item is not None and item["quantity"] == 0


# Removing an unknown item
def test_removing_an_unknown_item(table):
    save(table, removed=[change("yogurt", 1, 0.9)])
    assert stock(table, "yogurt") is None
    [recorded] = door(table)["changes"]
    assert recorded["item"] == "yogurt" and recorded["direction"] == "removed"


# Low-confidence item
def test_low_confidence_item(table):
    put_stock(table, "chocolate bar", 2, category="snack")
    save(table, removed=[change("chocolate bar", 1, 0.62, "snack")])
    assert stock(table, "chocolate bar")["quantity"] == 2
    [pending] = table.query(ACCOUNT, "PENDING#")
    assert pending["sk"].startswith(f"PENDING#{OPENED}#")
    assert {k: pending[k] for k in ("door_sk", "item", "direction", "quantity", "confidence")} == {
        "door_sk": DOOR_SK,
        "item": "chocolate bar",
        "direction": "removed",
        "quantity": 1,
        "confidence": 0.62,
    }
    assert pending["category"] == "snack"


# Exactly at the cutoff
def test_exactly_at_the_cutoff(table):
    save(table, added=[change("milk", 1, 0.7)])
    assert stock(table, "milk")["quantity"] == 1
    assert table.query(ACCOUNT, "PENDING#") == []


# Door event completed
def test_door_event_completed(table):
    out = save(table, added=[change("milk", 1, 0.92)], removed=[change("eggs", 2, 0.62)])
    assert out["outcome"] == "saved"
    event = door(table)
    assert event["status"] == "done"
    assert event["pending_count"] == 1
    assert [(c["item"], c["direction"], c["applied"]) for c in event["changes"]] == [
        ("milk", "added", True),
        ("eggs", "removed", False),
    ]


# Save step retried
def test_save_step_retried(table):
    put_stock(table, "eggs", 6)
    save(table, added=[change("eggs", 12, 0.86)])
    again = save(table, added=[change("eggs", 12, 0.86)])
    assert again["outcome"] == "already_saved"
    assert stock(table, "eggs")["quantity"] == 18


def test_save_skipped_for_failed_event(table):
    table.update(PK, DOOR_SK, {"status": "analysis_failed"})
    assert save(table, added=[change("milk")])["outcome"] == "already_saved"
    assert stock(table, "milk") is None


# Nothing changed
def test_nothing_changed(table):
    put_stock(table, "milk", 1)
    out = save(table)
    assert out["outcome"] == "saved"
    event = door(table)
    assert event["status"] == "done"
    assert event["changes"] == []
    assert event["pending_count"] == 0
    assert stock(table, "milk")["quantity"] == 1


def test_same_item_added_and_removed_in_one_opening(table):
    put_stock(table, "milk", 1)
    save(table, added=[change("milk", 2)], removed=[change("milk", 1)])
    assert stock(table, "milk")["quantity"] == 2
