"""inventory-api: inventory and door event listings."""

import base64
from urllib.parse import parse_qs, urlparse

import boto3
import pytest

from fridgesense.door_events import iso_utc
from fridgesense.handlers import api
from fridgesense.table import FridgeTable, account_pk
from tests.api_helpers import ACCOUNT, NOW, call, link_account, sign_in
from tests.conftest import BUCKET

PK = account_pk(ACCOUNT)
HOUR_MS = 3600 * 1000
DAY_MS = 24 * HOUR_MS


@pytest.fixture
def owner(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    link_account()
    return sign_in()


def put_item(key, quantity, category, name=None):
    FridgeTable().put(
        {
            "pk": PK,
            "sk": f"ITEM#{key}",
            "name": name or key,
            "category": category,
            "quantity": quantity,
            "first_seen_at": "x",
            "last_changed_at": "2026-08-14T13:53:41.000Z",
        }
    )


def put_event(opened_ms, stills=0, status="done"):
    opened = iso_utc(opened_ms)
    sk = f"DOOR#{opened}#ava1.ring.device.D1"
    keys = []
    for n in range(1, stills + 1):
        key = f"accounts/{ACCOUNT}/devices/D1/events/{opened_ms}/still-{n}.jpg"
        boto3.client("s3").put_object(Bucket=BUCKET, Key=key, Body=b"jpeg")
        keys.append(key)
    FridgeTable().put(
        {
            "pk": PK,
            "sk": sk,
            "opened_at": opened,
            "closed_at": iso_utc(opened_ms + 25_000),
            "duration_s": 25,
            "status": status,
            "still_keys": keys,
            "pending_count": 0,
            "changes": [
                {
                    "item": "milk",
                    "name": "milk",
                    "category": "dairy",
                    "direction": "added",
                    "quantity": 1,
                    "confidence": 0.9,
                    "applied": True,
                }
            ],
        }
    )
    return sk


# Inventory with items
def test_inventory_with_items(owner):
    put_item("eggs", 6, "dairy", "Eggs")
    put_item("apple", 3, "produce")
    put_item("soda can", 0, "beverage")
    FridgeTable().put({"pk": PK, "sk": "PENDING#x#1", "item": "jam"})
    status, body = call("GET", "/api/inventory", token=owner)
    assert status == 200
    assert [(i["category"], i["key"], i["quantity"]) for i in body["items"]] == [
        ("beverage", "soda can", 0),
        ("dairy", "eggs", 6),
        ("produce", "apple", 3),
    ]
    assert body["items"][1] == {
        "key": "eggs",
        "name": "Eggs",
        "category": "dairy",
        "quantity": 6,
        "last_changed_at": "2026-08-14T13:53:41.000Z",
    }
    assert body["pending_count"] == 1


# Empty inventory
def test_empty_inventory(owner):
    assert call("GET", "/api/inventory", token=owner) == (200, {"items": [], "pending_count": 0})


# Recent event with stills
def test_recent_event_with_stills(owner):
    sk = put_event(int(NOW * 1000) - HOUR_MS, stills=4)
    status, body = call("GET", "/api/events", token=owner)
    assert status == 200
    [event] = body["events"]
    assert base64.urlsafe_b64decode(event["id"] + "==").decode() == sk
    assert event["duration_s"] == 25 and event["status"] == "done"
    assert event["changes"][0]["item"] == "milk"
    assert len(event["stills"]) == 4
    url = urlparse(event["stills"][0])
    q = parse_qs(url.query)
    assert url.path.endswith("/still-1.jpg")
    assert q["X-Amz-Expires"] == ["900"] and "X-Amz-Signature" in q


# Old event
def test_old_event(owner):
    put_event(int(NOW * 1000) - 8 * DAY_MS, stills=4)
    [event] = call("GET", "/api/events", token=owner, query={"days": "30"})[1]["events"]
    assert event["stills"] == []


# Range limit
def test_range_limit(owner):
    recent = put_event(int(NOW * 1000) - 2 * DAY_MS)
    put_event(int(NOW * 1000) - 10 * DAY_MS)
    events = call("GET", "/api/events", token=owner)[1]["events"]
    assert [base64.urlsafe_b64decode(e["id"] + "==").decode() for e in events] == [recent]


def test_events_newest_first(owner):
    put_event(int(NOW * 1000) - 3 * HOUR_MS)
    put_event(int(NOW * 1000) - 1 * HOUR_MS)
    events = call("GET", "/api/events", token=owner)[1]["events"]
    assert events[0]["opened_at"] > events[1]["opened_at"]


# Days out of range
@pytest.mark.parametrize("days", ["0", "31", "abc"])
def test_days_out_of_range(owner, days):
    assert call("GET", "/api/events", token=owner, query={"days": days})[0] == 400
