"""fridge-inventory: confirming, rejecting and correcting by hand."""

import pytest

from fridgesense.inventory import (
    PendingNotFound,
    confirm_pending,
    reject_pending,
    save_task,
    set_quantity,
)
from fridgesense.table import FridgeTable, account_pk

ACCOUNT = "ava1.ring.account.A1"
PK = account_pk(ACCOUNT)
OPENED = "2026-08-14T13:53:16.000Z"
CLOSED = "2026-08-14T13:53:41.000Z"
DOOR_SK = f"DOOR#{OPENED}#ava1.ring.device.D1"
NOW = "2026-10-15T09:00:00.000Z"


@pytest.fixture
def table(aws):
    return FridgeTable()


def pending_from(table, direction, item, quantity=1, confidence=0.6, category="snack"):
    """Run the real save step with one unsure change; returns its pending item."""
    table.put(
        {"pk": PK, "sk": DOOR_SK, "status": "analyzing", "opened_at": OPENED, "closed_at": CLOSED}
    )
    change = {"item": item, "category": category, "quantity": quantity, "confidence": confidence}
    analysis = {"added": [], "removed": []}
    analysis[direction].append(change)
    save_task(table, {"account_id": ACCOUNT, "door_sk": DOOR_SK, "analysis": analysis})
    [pending] = table.query(ACCOUNT, "PENDING#")
    return pending


def put_stock(table, key, quantity, category="snack"):
    table.put(
        {
            "pk": PK,
            "sk": f"ITEM#{key}",
            "name": key,
            "category": category,
            "quantity": quantity,
            "first_seen_at": OPENED,
            "last_changed_at": OPENED,
        }
    )


def door(table):
    return table.get(PK, DOOR_SK)


# Confirm as reported
def test_confirm_as_reported(table):
    put_stock(table, "chocolate bar", 2)
    pending = pending_from(table, "removed", "chocolate bar")
    assert door(table)["pending_count"] == 1
    confirm_pending(table, ACCOUNT, pending["sk"], now=NOW)
    assert table.get(PK, "ITEM#chocolate bar")["quantity"] == 1
    assert table.query(ACCOUNT, "PENDING#") == []
    event = door(table)
    assert event["changes"][0]["applied"] is True
    assert event["pending_count"] == 0


# Confirm with a correction
def test_confirm_with_a_correction(table):
    pending = pending_from(table, "added", "bottle", category="beverage")
    confirm_pending(table, ACCOUNT, pending["sk"], item="Oat Milk", quantity=2, now=NOW)
    item = table.get(PK, "ITEM#oat milk")
    assert (item["quantity"], item["name"]) == (2, "Oat Milk")
    assert table.get(PK, "ITEM#bottle") is None
    change = door(table)["changes"][0]
    assert (change["item"], change["quantity"], change["applied"]) == ("oat milk", 2, True)


# Confirm a removal of an unknown item
def test_confirm_a_removal_of_an_unknown_item(table):
    pending = pending_from(table, "removed", "yogurt", category="dairy")
    confirm_pending(table, ACCOUNT, pending["sk"], now=NOW)
    assert table.get(PK, "ITEM#yogurt") is None
    assert table.query(ACCOUNT, "PENDING#") == []
    assert door(table)["changes"][0]["applied"] is True


def test_confirm_twice_applies_once(table):
    put_stock(table, "chocolate bar", 2)
    pending = pending_from(table, "removed", "chocolate bar")
    confirm_pending(table, ACCOUNT, pending["sk"], now=NOW)
    with pytest.raises(PendingNotFound):
        confirm_pending(table, ACCOUNT, pending["sk"], now=NOW)
    assert table.get(PK, "ITEM#chocolate bar")["quantity"] == 1
    assert door(table)["pending_count"] == 0


def test_confirm_uses_now_as_last_changed(table):
    pending = pending_from(table, "added", "chocolate bar")
    confirm_pending(table, ACCOUNT, pending["sk"], now=NOW)
    assert table.get(PK, "ITEM#chocolate bar")["last_changed_at"] == NOW


# Reject
def test_reject(table):
    put_stock(table, "chocolate bar", 2)
    pending = pending_from(table, "added", "chocolate bar")
    reject_pending(table, ACCOUNT, pending["sk"])
    assert table.get(PK, "ITEM#chocolate bar")["quantity"] == 2
    assert table.query(ACCOUNT, "PENDING#") == []
    event = door(table)
    assert event["changes"][0]["rejected"] is True
    assert event["pending_count"] == 0


def test_unknown_pending_change(table):
    with pytest.raises(PendingNotFound):
        reject_pending(table, ACCOUNT, f"PENDING#{OPENED}#9")


def test_pending_without_change_index_still_confirms(table):
    """Pending items written before change_index existed: apply and delete only."""
    table.put(
        {
            "pk": PK,
            "sk": f"PENDING#{OPENED}#1",
            "door_sk": DOOR_SK,
            "item": "jam",
            "category": "condiment",
            "direction": "added",
            "quantity": 1,
            "confidence": 0.5,
        }
    )
    confirm_pending(table, ACCOUNT, f"PENDING#{OPENED}#1", now=NOW)
    assert table.get(PK, "ITEM#jam")["quantity"] == 1
    assert table.query(ACCOUNT, "PENDING#") == []


# Correct a count
def test_correct_a_count(table):
    put_stock(table, "eggs", 18, category="dairy")
    set_quantity(table, ACCOUNT, "eggs", 12, now=NOW)
    item = table.get(PK, "ITEM#eggs")
    assert (item["quantity"], item["last_changed_at"], item["category"]) == (12, NOW, "dairy")


# Add an item by hand
def test_add_an_item_by_hand(table):
    set_quantity(table, ACCOUNT, "Butter", 1, now=NOW)
    item = table.get(PK, "ITEM#butter")
    assert (item["quantity"], item["category"], item["name"]) == (1, "other", "Butter")


def test_set_quantity_rejects_negative(table):
    with pytest.raises(ValueError):
        set_quantity(table, ACCOUNT, "eggs", -1, now=NOW)
