"""pipeline-debug-traces: listing motions and reading one trace over HTTP."""

import boto3
import pytest

from fridgesense.door_events import iso_utc
from fridgesense.handlers import api
from fridgesense.store import load_app_config
from fridgesense.table import FridgeTable, account_pk
from fridgesense.traces import TraceWriter, debug_prefix
from fridgesense.usage import Tokens
from tests.api_helpers import ACCOUNT, NOW, call, configure, link_account, sign_in
from tests.conftest import BUCKET
from tests.test_traces import (
    CLOSED,
    DEVICE,
    OPEN,
    REFERENCES,
    four,
    trace_of,
)
from tests.test_traces import call as nova_call

HOUR_MS = 3600 * 1000
NOW_MS = int(NOW * 1000)


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


def state_at(start_ms: int) -> dict:
    return {
        "account_id": ACCOUNT,
        "device_id": DEVICE,
        "timestamp_ms": start_ms + 500,
        "window": {
            "status": "ready",
            "start_ms": start_ms,
            "end_ms": start_ms + 25_000,
            "ring_event_id": f"evt_{start_ms}",
        },
    }


def events_prefix(start_ms: int) -> str:
    return f"accounts/{ACCOUNT}/devices/{DEVICE}/events/{start_ms}/"


def door_sk(start_ms: int) -> str:
    return f"DOOR#{iso_utc(start_ms)}#{DEVICE}"


def motion(start_ms: int, outcome: str = "not_door", calls=()) -> dict:
    """A traced motion written by the real writer; door openings get their Nova calls."""
    writer = TraceWriter(boto3.client("s3"), FridgeTable(), BUCKET)
    state = state_at(start_ms)
    is_door = outcome == "door_open"
    images = four(CLOSED, OPEN, OPEN, CLOSED) if is_door else four(CLOSED, CLOSED, CLOSED, None)
    writer.door(
        state,
        trace_of(
            images,
            outcome=outcome,
            open_span=[2, 3, 4] if is_door else [],
            picked=[2, 3, 4] if is_door else [],
            stored_keys=[f"{events_prefix(start_ms)}still-{n}.jpg" for n in (1, 2, 3)]
            if is_door
            else [],
            door_sk=door_sk(start_ms) if is_door else None,
        ),
    )
    for record in calls:
        still_keys = [f"{events_prefix(start_ms)}still-{n}.jpg" for n in (1, 2, 3, 4)]
        writer.nova(state, start_ms + 60_000, record, REFERENCES, still_keys)
    return state


def listing(token, query):
    status, body = call("GET", "/api/debug/motions", token=token, query=query)
    assert status == 200, body
    return body


def detail(token, motion_id):
    return call("GET", f"/api/debug/motions/{motion_id}", token=token)


def recent(hours_ago: float) -> int:
    return NOW_MS - int(hours_ago * HOUR_MS)


TWO_CALLS = (
    nova_call(
        attempt=1,
        outcome="invalid",
        tokens=Tokens(input=1180, output=96),
        usd=0.000653,
        latency_ms=2140,
        wall_ms=2300,
    ),
    nova_call(
        attempt=2,
        tokens=Tokens(input=1200, output=90),
        usd=0.000644,
        latency_ms=1900,
        wall_ms=2000,
    ),
)


# Listing
def test_listing(owner):
    opening = recent(2)
    motion(opening, "door_open", TWO_CALLS)
    motion(recent(1))
    body = listing(owner, {"days": "1"})
    first, second = body["motions"]
    assert body["next"] is None
    assert first["at"] == iso_utc(recent(1))
    assert first["outcome"] == "not_door"
    assert first["door_event_id"] is None
    assert first["nova"] == {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "usd": 0,
        "latency_ms": 0,
    }
    assert first["stills_downloaded"] == 3
    assert second["outcome"] == "door_open"
    assert second["device_id"] == DEVICE
    assert second["door_event_id"] == api.encode_id(door_sk(opening))
    assert second["nova"] == {
        "calls": 2,
        "input_tokens": 2380,
        "output_tokens": 186,
        "usd": 0.001297,
        "latency_ms": 4040,
    }
    assert second["best"]["zone"] == 2
    assert api.decode_id(second["id"], "TRACE#") == f"TRACE#{iso_utc(opening)}#{DEVICE}"


def test_listing_pages(owner):
    for hours in (3, 2, 1):
        motion(recent(hours))
    page = listing(owner, {"days": "1", "limit": "2"})
    assert [m["at"] for m in page["motions"]] == [iso_utc(recent(1)), iso_utc(recent(2))]
    assert page["next"] == page["motions"][1]["id"]
    rest = listing(owner, {"days": "1", "limit": "2", "cursor": page["next"]})
    assert [m["at"] for m in rest["motions"]] == [iso_utc(recent(3))]
    assert rest["next"] is None


def test_listing_range(owner):
    motion(recent(30))
    motion(recent(1))
    body = listing(owner, {"from": iso_utc(recent(26)), "to": iso_utc(NOW_MS)})
    assert [m["at"] for m in body["motions"]] == [iso_utc(recent(1))]


def test_door_events_are_not_listed(owner):
    FridgeTable().put({"pk": account_pk(ACCOUNT), "sk": door_sk(recent(1)), "status": "done"})
    assert listing(owner, {"days": "1"})["motions"] == []


# Bad range
@pytest.mark.parametrize(
    "query", [{"days": "0"}, {"limit": "51"}, {"cursor": "nope"}, {"from": "yesterday"}]
)
def test_bad_range(owner, query):
    status, _ = call("GET", "/api/debug/motions", token=owner, query=query)
    assert status == 400


class NoLinks:
    def __getattr__(self, name):
        raise AssertionError("no link may be generated for a viewer")


# Viewer refused
@pytest.mark.parametrize("path", ["/api/debug/motions", "/api/debug/motions/abc"])
def test_viewer_refused(tokens, monkeypatch, path):
    monkeypatch.setattr(api, "_s3", lambda: NoLinks())
    assert call("GET", path, token=tokens["viewer"]) == (403, {"error": "read-only"})


def test_needs_a_token(tokens):
    assert call("GET", "/api/debug/motions")[0] == 401


def assert_link(url: str | None, key: str):
    assert url is not None
    assert key in url
    assert "X-Amz-Signature" in url


# Trace by door event id
def test_trace_by_door_event_id(owner):
    start = recent(1)
    motion(start, "door_open", TWO_CALLS)
    status, body = detail(owner, api.encode_id(door_sk(start)))
    assert status == 200, body
    prefix = debug_prefix(ACCOUNT, DEVICE, start)
    assert body["outcome"] == "door_open"
    assert body["nova"][0]["attempt"] == 1 and body["nova"][1]["attempt"] == 2
    door = body["door"]
    assert door["outcome"] == "door_open"
    stills = door["stills"]
    assert [s["n"] for s in stills] == [1, 2, 3, 4]
    for s in stills:
        assert "key" not in s
        assert_link(s["url"], f"raw-{s['n']}.jpg")
    assert [z["value"] for z in stills[1]["zones"]][0] == 0.0
    assert all("key" not in k for k in door["rule"]["zones"][0])
    assert door["rule"]["zones"][0]["baseline_url"] is None  # default rule: no baseline
    assert "stored_keys" not in door
    assert len(door["stored_urls"]) == 3
    content = body["nova"][1]["request"]["content"]
    images = [b for b in content if b["type"] == "image"]
    assert len(images) == 6
    for b in images:
        assert "key" not in b
    refs = [b for b in images if b["role"] == "reference"]
    assert_link(refs[0]["url"], f"{prefix}nova-{start + 60_000}-ref-1.jpg")
    assert body["nova"][1]["outcome"] == "ok"
    assert body["nova"][0]["outcome"] == "invalid"
    assert body["id"] == api.encode_id(f"TRACE#{iso_utc(start)}#{DEVICE}")
    assert body["nova_totals"]["calls"] == 2


# Trace by a later opening's id
def test_trace_by_a_later_openings_id(owner):
    start = recent(1)
    motion(start, "door_open", TWO_CALLS)
    status, body = detail(owner, api.encode_id(f"{door_sk(start)}#2"))
    assert status == 200, body
    assert body["id"] == api.encode_id(f"TRACE#{iso_utc(start)}#{DEVICE}")
    assert body["door"]["outcome"] == "door_open"


def test_trace_by_motion_id(owner):
    start = recent(1)
    motion(start)
    [m] = listing(owner, {"days": "1"})["motions"]
    status, body = detail(owner, m["id"])
    assert status == 200
    assert body["door"]["outcome"] == "not_door"
    assert body["nova"] == []
    missing = body["door"]["stills"][3]
    assert missing["url"] is None
    assert missing["missing_status"] == 403


def test_setup_rule_links(owner):
    from fridgesense import door_calibration as dc
    from fridgesense.door_events import DoorCheck, ZoneRule, baseline_of

    whole = (0.0, 0.0, 1.0, 1.0)
    whole_box = {"x": 0, "y": 0, "width": 1, "height": 1}
    z = dc.add_zone(FridgeTable(), ACCOUNT, DEVICE, "Doors", whole_box, now_ms=1, source="clip").sk
    dc.add_reference(FridgeTable(), ACCOUNT, DEVICE, CLOSED, z, "closed", now_ms=1, source="clip")
    rule = ZoneRule(whole, "change", "above", 0.1, baseline_of([CLOSED], whole), margin=0.05)
    check = DoorCheck(rules=(rule,), source="setup", ran_at="2026-08-01T00:00:00.000Z")
    start = recent(1)
    TraceWriter(boto3.client("s3"), FridgeTable(), BUCKET).door(
        state_at(start), trace_of(four(CLOSED, CLOSED, CLOSED, CLOSED), check, outcome="not_door")
    )
    _, body = detail(owner, api.encode_id(f"TRACE#{iso_utc(start)}#{DEVICE}"))
    zone = body["door"]["rule"]["zones"][0]
    assert "baseline_key" not in zone
    assert_link(zone["baseline_url"], "baseline-1.png")
    [ref] = body["door"]["rule"]["references"]
    assert "key" not in ref
    assert_link(ref["url"], "door-ref-")


# Untraced event
def test_untraced_event(owner):
    FridgeTable().put({"pk": account_pk(ACCOUNT), "sk": door_sk(recent(1)), "status": "done"})
    assert detail(owner, api.encode_id(door_sk(recent(1)))) == (404, {"error": "no trace"})


# Files expired
def test_files_expired(owner):
    start = recent(1)
    motion(start)
    boto3.client("s3").delete_object(
        Bucket=BUCKET, Key=debug_prefix(ACCOUNT, DEVICE, start) + "door.json"
    )
    assert detail(owner, api.encode_id(f"TRACE#{iso_utc(start)}#{DEVICE}")) == (
        404,
        {"error": "no trace"},
    )


# Bad id
@pytest.mark.parametrize("bad", ["nope!", api.encode_id("ITEM#milk")])
def test_bad_id(owner, bad):
    assert detail(owner, bad)[0] == 400
