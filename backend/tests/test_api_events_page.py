"""inventory-api: door events by time range and page, and deleting a door event."""

import pytest

from fridgesense.door_events import iso_utc
from fridgesense.handlers import api
from fridgesense.store import load_app_config
from fridgesense.table import FridgeTable, account_pk
from tests.api_helpers import ACCOUNT, NOW, call, configure, link_account, sign_in

PK = account_pk(ACCOUNT)
HOUR_MS = 3600 * 1000
DAY_MS = 24 * HOUR_MS
# 04:00 UTC on the day before NOW: midnight in Toronto.
DAY_START = (int(NOW * 1000) // DAY_MS - 1) * DAY_MS + 4 * HOUR_MS


@pytest.fixture
def tokens(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    link_account()
    configure(demo_passcode="look-only")
    load_app_config(refresh=True)
    return {"owner": sign_in(), "viewer": sign_in("look-only")}


@pytest.fixture
def owner(tokens):
    return tokens["owner"]


def put_event(opened_ms, changes=None):
    opened = iso_utc(opened_ms)
    sk = f"DOOR#{opened}#ava1.ring.device.D1"
    FridgeTable().put(
        {
            "pk": PK,
            "sk": sk,
            "opened_at": opened,
            "closed_at": iso_utc(opened_ms + 25_000),
            "duration_s": 25,
            "status": "done",
            "still_keys": [],
            "pending_count": 0,
            "changes": changes or [],
        }
    )
    return api.encode_id(sk)


def day(start_ms=DAY_START, **extra):
    return {"from": iso_utc(start_ms), "to": iso_utc(start_ms + DAY_MS), **extra}


def listing(token, query):
    status, body = call("GET", "/api/events", token=token, query=query)
    assert status == 200, body
    return body


# One day
def test_one_day(owner):
    put_event(DAY_START - 60_000)
    first = put_event(DAY_START)
    noon = put_event(DAY_START + 8 * HOUR_MS)
    put_event(DAY_START + DAY_MS - 60_000 + DAY_MS)
    body = listing(owner, day())
    assert [e["id"] for e in body["events"]] == [noon, first]
    assert body["next"] is None


def test_from_ignores_days(owner):
    put_event(DAY_START + HOUR_MS)
    assert len(listing(owner, day(days="1"))["events"]) == 1


# Pages
def test_pages(owner):
    oldest = put_event(DAY_START + 1 * HOUR_MS)
    middle = put_event(DAY_START + 2 * HOUR_MS)
    newest = put_event(DAY_START + 3 * HOUR_MS)
    page1 = listing(owner, day(limit="2"))
    assert [e["id"] for e in page1["events"]] == [newest, middle]
    assert page1["next"] == middle
    page2 = listing(owner, day(limit="2", cursor=page1["next"]))
    assert [e["id"] for e in page2["events"]] == [oldest]
    assert page2["next"] is None


def test_cursor_of_deleted_event_still_pages(owner):
    oldest = put_event(DAY_START + 1 * HOUR_MS)
    gone = put_event(DAY_START + 2 * HOUR_MS)
    assert call("DELETE", f"/api/events/{gone}", token=owner)[0] == 200
    assert [e["id"] for e in listing(owner, day(limit="2", cursor=gone))["events"]] == [oldest]


# Last page exactly full
def test_last_page_exactly_full(owner):
    put_event(DAY_START + 1 * HOUR_MS)
    put_event(DAY_START + 2 * HOUR_MS)
    body = listing(owner, day(limit="2"))
    assert len(body["events"]) == 2
    assert body["next"] is None


# Bad range or page
@pytest.mark.parametrize(
    "query",
    [
        {"from": "yesterday", "to": iso_utc(DAY_START)},
        {"from": iso_utc(DAY_START)},
        {"from": iso_utc(DAY_START), "to": iso_utc(DAY_START - 1)},
        {"from": iso_utc(DAY_START), "to": iso_utc(DAY_START)},
        {"from": iso_utc(DAY_START), "to": iso_utc(DAY_START + 32 * DAY_MS)},
        day(limit="0"),
        day(limit="51"),
        day(limit="ten"),
        day(limit="2", cursor="nope"),
    ],
)
def test_bad_range_or_page(owner, query):
    status, body = call("GET", "/api/events", token=owner, query=query)
    assert status == 400, body


# Delete
def test_delete(owner):
    milk = [
        {
            "item": "milk",
            "name": "milk",
            "category": "dairy",
            "direction": "added",
            "quantity": 1,
            "confidence": 0.9,
            "applied": True,
        }
    ]
    gone = put_event(DAY_START + HOUR_MS, changes=milk)
    kept = put_event(DAY_START + 2 * HOUR_MS)
    gone_sk = api.decode_id(gone, "DOOR#")
    table = FridgeTable()
    table.put({"pk": PK, "sk": "ITEM#milk", "name": "milk", "category": "dairy", "quantity": 1})
    table.put(
        {"pk": PK, "sk": "PENDING#a#1", "door_sk": gone_sk, "item": "jam", "direction": "added"}
    )
    table.put(
        {
            "pk": PK,
            "sk": "PENDING#b#1",
            "door_sk": "DOOR#other",
            "item": "ham",
            "direction": "added",
        }
    )

    assert call("DELETE", f"/api/events/{gone}", token=owner) == (200, {"id": gone})

    assert [e["id"] for e in listing(owner, day())["events"]] == [kept]
    pending = call("GET", "/api/pending", token=owner)[1]["pending"]
    assert [p["item"] for p in pending] == ["ham"]
    items = call("GET", "/api/inventory", token=owner)[1]["items"]
    assert [(i["key"], i["quantity"]) for i in items] == [("milk", 1)]


# Unknown event
@pytest.mark.parametrize("which", ["unknown", "twice", "pending id"])
def test_unknown_event(owner, which):
    if which == "unknown":
        event_id = api.encode_id("DOOR#2020-01-01T00:00:00.000Z#ava1.ring.device.D1")
    elif which == "twice":
        event_id = put_event(DAY_START + HOUR_MS)
        call("DELETE", f"/api/events/{event_id}", token=owner)
    else:
        FridgeTable().put({"pk": PK, "sk": "PENDING#a#1", "item": "jam"})
        event_id = api.encode_id("PENDING#a#1")
    assert call("DELETE", f"/api/events/{event_id}", token=owner) == (404, {"error": "not found"})
    if which == "pending id":
        assert len(call("GET", "/api/pending", token=owner)[1]["pending"]) == 1


# Viewer delete refused
def test_viewer_delete_refused(tokens):
    event_id = put_event(DAY_START + HOUR_MS)
    assert call("DELETE", f"/api/events/{event_id}", token=tokens["viewer"]) == (
        403,
        {"error": "read-only"},
    )
    assert [e["id"] for e in listing(tokens["owner"], day())["events"]] == [event_id]
