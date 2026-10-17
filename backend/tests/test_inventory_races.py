"""fridge-inventory: concurrent inventory writes keep every change."""

import pytest

from fridgesense.inventory import (
    ItemNotFound,
    add_item,
    confirm_pending,
    delete_item,
    edit_item,
    save_task,
    set_quantity,
)
from fridgesense.table import FridgeTable, account_pk

ACCOUNT = "ava1.ring.account.A1"
PK = account_pk(ACCOUNT)
NOW = "2026-10-17T09:00:00.000Z"


class RacingTable(FridgeTable):
    """Runs `race` once, right after the next read of `race_sk`: the competing write lands
    between the racing write's read and its write."""

    race_sk: str | None = None
    race = None

    def get(self, pk: str, sk: str) -> dict | None:
        row = super().get(pk, sk)
        if sk == self.race_sk and self.race is not None:
            race, self.race = self.race, None
            race()
        return row

    def after_reading(self, key: str, race) -> None:
        self.race_sk, self.race = f"ITEM#{key}", race


@pytest.fixture
def table(aws):
    return RacingTable()


def put_stock(table, key, quantity, category="dairy", **extra):
    table.put(
        {
            "pk": PK,
            "sk": f"ITEM#{key}",
            "name": key,
            "category": category,
            "quantity": quantity,
            "first_seen_at": "2026-10-01T00:00:00.000Z",
            "last_changed_at": "2026-10-01T00:00:00.000Z",
            **extra,
        }
    )


def door_event(table, n: int, added=(), removed=(), confidence=0.9) -> dict:
    """A door event waiting to be saved; returns the save step's state."""
    opened = f"2026-10-17T08:0{n}:00.000Z"
    door_sk = f"DOOR#{opened}#ava1.ring.device.D1"
    table.put(
        {
            "pk": PK,
            "sk": door_sk,
            "status": "analyzing",
            "opened_at": opened,
            "closed_at": f"2026-10-17T08:0{n}:30.000Z",
        }
    )

    def changes(items):
        return [
            {"item": item, "category": "dairy", "quantity": q, "confidence": confidence}
            for item, q in items
        ]

    return {
        "account_id": ACCOUNT,
        "door_sk": door_sk,
        "analysis": {"added": changes(added), "removed": changes(removed)},
    }


def item(table, key):
    return table.get(PK, f"ITEM#{key}")


# Two concurrent deltas both applied
def test_two_concurrent_deltas_both_applied(table):
    put_stock(table, "milk", 2)
    a = door_event(table, 1, added=[("milk", 1)])
    b = door_event(table, 2, added=[("milk", 2)])
    table.after_reading("milk", lambda: save_task(table, b))
    assert save_task(table, a)["outcome"] == "saved"
    assert item(table, "milk")["quantity"] == 5
    assert table.get(PK, a["door_sk"])["status"] == "done"
    assert table.get(PK, b["door_sk"])["status"] == "done"


# Door event saved while a pending change is confirmed
def test_door_event_saved_while_pending_change_confirmed(table):
    put_stock(table, "eggs", 6)
    unsure = door_event(table, 1, removed=[("eggs", 2)], confidence=0.5)
    save_task(table, unsure)
    [pending] = table.query(ACCOUNT, "PENDING#")
    sure = door_event(table, 2, added=[("eggs", 6)])
    table.after_reading("eggs", lambda: save_task(table, sure))
    confirm_pending(table, ACCOUNT, pending["sk"], now=NOW)
    assert item(table, "eggs")["quantity"] == 10
    assert table.query(ACCOUNT, "PENDING#") == []


# Adding by hand while a door event is saved
def test_adding_by_hand_while_door_event_saved(table):
    put_stock(table, "butter", 1)
    event = door_event(table, 1, added=[("butter", 1)])
    table.after_reading("butter", lambda: save_task(table, event))
    add_item(table, ACCOUNT, "butter", "dairy", 2, now=NOW)
    assert item(table, "butter")["quantity"] == 4


# An edit racing a delete
def test_edit_racing_delete(table):
    put_stock(table, "yogurt", 3)
    table.after_reading("yogurt", lambda: delete_item(table, ACCOUNT, "yogurt"))
    with pytest.raises(ItemNotFound):
        edit_item(table, ACCOUNT, "yogurt", quantity=5, now=NOW)
    assert item(table, "yogurt") is None


# A rename racing a delete
def test_rename_racing_delete(table):
    put_stock(table, "bottle", 1, category="other")
    table.after_reading("bottle", lambda: delete_item(table, ACCOUNT, "bottle"))
    with pytest.raises(ItemNotFound):
        edit_item(table, ACCOUNT, "bottle", name="Oat Milk", now=NOW)
    assert item(table, "bottle") is None
    assert item(table, "oat milk") is None


# Setting a count racing a door event
def test_setting_count_racing_door_event(table):
    put_stock(table, "cheese", 1, stocked_at="2026-10-01T00:00:00.000Z", peak_quantity=1)
    event = door_event(table, 1, added=[("cheese", 5)])
    table.after_reading("cheese", lambda: save_task(table, event))
    set_quantity(table, ACCOUNT, "cheese", 4, now=NOW)
    cheese = item(table, "cheese")
    assert cheese["quantity"] == 4
    assert cheese["peak_quantity"] == 6
