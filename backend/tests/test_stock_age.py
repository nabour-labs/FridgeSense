"""fridge-inventory: stock age (stocked_at) and peak count (peak_quantity) on items."""

import pytest

from fridgesense.inventory import add_item, confirm_pending, save_task, set_quantity
from fridgesense.table import FridgeTable, account_pk

ACCOUNT = "ava1.ring.account.A1"
PK = account_pk(ACCOUNT)
OPENED = "2026-10-16T18:02:11.000Z"
CLOSED = "2026-10-16T18:02:40.000Z"
DOOR_SK = f"DOOR#{OPENED}#ava1.ring.device.D1"
EARLIER = "2026-10-10T08:00:00.000Z"


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
    analysis = {"added": list(added), "removed": list(removed)}
    return save_task(table, {"account_id": ACCOUNT, "door_sk": DOOR_SK, "analysis": analysis})


def put_stock(table, key, quantity, **extra):
    table.put(
        {
            "pk": PK,
            "sk": f"ITEM#{key}",
            "name": key,
            "category": "dairy",
            "quantity": quantity,
            "first_seen_at": "2026-10-01T00:00:00.000Z",
            "last_changed_at": EARLIER,
            **extra,
        }
    )


def item(table, key):
    return table.get(PK, f"ITEM#{key}")


# New item
def test_new_item(table):
    save(table, added=[change("eggs", 12)])
    eggs = item(table, "eggs")
    assert (eggs["quantity"], eggs["stocked_at"], eggs["peak_quantity"]) == (12, CLOSED, 12)


# Adding more keeps the stock age
def test_adding_more_keeps_the_stock_age(table):
    put_stock(table, "eggs", 2, stocked_at=EARLIER, peak_quantity=12)
    save(table, added=[change("eggs", 6)])
    eggs = item(table, "eggs")
    assert (eggs["quantity"], eggs["stocked_at"], eggs["peak_quantity"]) == (8, EARLIER, 12)


# Peak rises above the old peak
def test_peak_rises_above_the_old_peak(table):
    put_stock(table, "yogurt", 3, stocked_at=EARLIER, peak_quantity=4)
    save(table, added=[change("yogurt", 2)])
    yogurt = item(table, "yogurt")
    assert (yogurt["quantity"], yogurt["peak_quantity"]) == (5, 5)


# Running out clears both
def test_running_out_clears_both(table):
    put_stock(table, "milk", 1, stocked_at=EARLIER, peak_quantity=1)
    save(table, removed=[change("milk", 1)])
    milk = item(table, "milk")
    assert milk["quantity"] == 0
    assert "stocked_at" not in milk
    assert "peak_quantity" not in milk


# Restock after running out
def test_restock_after_running_out(table):
    put_stock(table, "milk", 0)
    save(table, added=[change("milk", 2)])
    milk = item(table, "milk")
    assert (milk["quantity"], milk["stocked_at"], milk["peak_quantity"]) == (2, CLOSED, 2)


# Confirmed pending change
def test_confirmed_pending_change(table):
    save(table, added=[change("butter", 1, confidence=0.6)])
    [pending] = table.query(ACCOUNT, "PENDING#")
    confirm_pending(table, ACCOUNT, pending["sk"], now="2026-10-16T19:00:00.000Z")
    butter = item(table, "butter")
    assert (butter["stocked_at"], butter["peak_quantity"]) == ("2026-10-16T19:00:00.000Z", 1)


# Count set by hand
def test_count_set_by_hand(table):
    put_stock(table, "eggs", 12, stocked_at=EARLIER, peak_quantity=12)
    set_quantity(table, ACCOUNT, "eggs", 0, now="2026-10-17T10:00:00.000Z")
    eggs = item(table, "eggs")
    assert "stocked_at" not in eggs
    assert "peak_quantity" not in eggs
    set_quantity(table, ACCOUNT, "eggs", 6, now="2026-10-18T10:00:00.000Z")
    eggs = item(table, "eggs")
    assert (eggs["stocked_at"], eggs["peak_quantity"]) == ("2026-10-18T10:00:00.000Z", 6)


def test_count_set_by_hand_keeps_age_while_in_stock(table):
    put_stock(table, "eggs", 12, stocked_at=EARLIER, peak_quantity=12)
    set_quantity(table, ACCOUNT, "eggs", 4, now="2026-10-17T10:00:00.000Z")
    eggs = item(table, "eggs")
    assert (eggs["stocked_at"], eggs["peak_quantity"]) == (EARLIER, 12)


# Item added by hand
def test_item_added_by_hand(table):
    add_item(table, ACCOUNT, "cheese", "dairy", 2, now="2026-10-16T09:00:00.000Z")
    add_item(table, ACCOUNT, "cheese", "dairy", 3, now="2026-10-17T09:00:00.000Z")
    cheese = item(table, "cheese")
    assert (cheese["quantity"], cheese["stocked_at"], cheese["peak_quantity"]) == (
        5,
        "2026-10-16T09:00:00.000Z",
        5,
    )
