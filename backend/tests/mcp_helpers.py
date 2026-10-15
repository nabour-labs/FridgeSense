"""Seed helpers for the fridge-mcp tests."""

from datetime import UTC, datetime, timedelta

from fridgesense.door_events import iso_utc
from fridgesense.table import FridgeTable, account_pk

ACCOUNT = "ava1.ring.account.A1"
PK = account_pk(ACCOUNT)
NOW = datetime(2026, 10, 16, 0, 0, tzinfo=UTC)  # 20:00 on Oct 15 in Toronto (EDT)


def iso(dt: datetime) -> str:
    return iso_utc(int(dt.timestamp() * 1000))


def put_item(
    key,
    quantity,
    category="dairy",
    minutes_ago=60,
    name=None,
    first_seen_at=None,
    stocked_at=None,
    peak_quantity=None,
):
    FridgeTable().put(
        {
            "pk": PK,
            "sk": f"ITEM#{key}",
            "name": name or key,
            "category": category,
            "quantity": quantity,
            "first_seen_at": first_seen_at or iso(NOW - timedelta(days=3)),
            "last_changed_at": iso(NOW - timedelta(minutes=minutes_ago)),
            **({"stocked_at": stocked_at} if stocked_at else {}),
            **({"peak_quantity": peak_quantity} if peak_quantity is not None else {}),
        }
    )


def put_door(opened: datetime, duration_s=20, changes=(), pending_count=0, status="done"):
    sk = f"DOOR#{iso(opened)}#ava1.ring.device.D1"
    FridgeTable().put(
        {
            "pk": PK,
            "sk": sk,
            "opened_at": iso(opened),
            "closed_at": iso(opened + timedelta(seconds=duration_s)),
            "duration_s": duration_s,
            "status": status,
            "changes": list(changes),
            "pending_count": pending_count,
            "still_keys": [],
        }
    )
    return sk


def change(item, direction="added", quantity=1, applied=True, rejected=False):
    return {
        "item": item,
        "name": item,
        "category": "dairy",
        "direction": direction,
        "quantity": quantity,
        "confidence": 0.9 if applied else 0.6,
        "applied": applied,
        **({"rejected": True} if rejected else {}),
    }
