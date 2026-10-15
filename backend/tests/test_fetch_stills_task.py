"""door-event-detection: fetch_stills task (door check, door event record, duplicates)."""

import logging

import boto3
import httpx
import pytest
import respx

from fridgesense.door_events import DoorCheck, fetch_stills, iso_utc
from fridgesense.oauth import OAuthClient
from fridgesense.ring import API_BASE, RingClient
from fridgesense.store import Tokens
from fridgesense.table import FridgeTable
from tests.conftest import BUCKET, MemoryTokenStore, jpeg

NOW = 1_786_715_700.0
DOWNLOAD = f"{API_BASE}/v1/devices/ava1.ring.device.D1/media/image/download"
ACCOUNT = "ava1.ring.account.A1"
STATE = {
    "account_id": ACCOUNT,
    "device_id": "ava1.ring.device.D1",
    "timestamp_ms": 1786715596787,
    "request_id": "R1",
    "window": {
        "status": "ready",
        "start_ms": 1786715596000,
        "end_ms": 1786715621000,
        "ring_event_id": "evt_1786715596000",
    },
}
DOOR_SK = "DOOR#2026-08-14T13:53:16.000Z#ava1.ring.device.D1"
CHECK = DoorCheck(box=(0.0, 0.0, 1.0, 1.0), threshold=0.5)


@pytest.fixture
def ring_http():
    tokens = Tokens(
        account_id=ACCOUNT,
        access_token="at1",
        refresh_token="rt1",
        expires_at=int(NOW) + 3600,
        link_status="linked",
    )
    with httpx.Client() as http:
        ring = RingClient(http, MemoryTokenStore(tokens), OAuthClient(http, "c", "s"), lambda: NOW)
        yield ring, http


def ring_serves(images: list[bytes] | None, status: int = 200):
    """Mock Ring so the n-th still request returns images[n]; None means 403 for all."""
    if images is None:
        respx.post(DOWNLOAD).respond(403)
        return
    counter = iter(range(100))
    respx.post(DOWNLOAD).mock(
        side_effect=lambda request: httpx.Response(
            303, headers={"Location": f"https://dl.example.com/{next(counter)}"}
        )
    )
    respx.get(url__regex=r"https://dl\.example\.com/(\d+)").mock(
        side_effect=lambda request: httpx.Response(
            status, content=images[int(request.url.path.strip("/")) % len(images)]
        )
    )


def run(ring_http, state=STATE):
    ring, http = ring_http
    return fetch_stills(
        ring, http, boto3.client("s3"), FridgeTable(), BUCKET, CHECK, state, sleep=lambda s: None
    )


def door_events():
    return [i for i in FridgeTable().query(ACCOUNT, "DOOR#")]


def test_iso_utc():
    assert iso_utc(1786715596000) == "2026-08-14T13:53:16.000Z"
    assert iso_utc(1786715596787) == "2026-08-14T13:53:16.787Z"


# Door event saved
@respx.mock
def test_door_event_saved(aws, ring_http):
    ring_serves([jpeg(0.1), jpeg(0.8), jpeg(0.8), jpeg(0.2)])
    out = run(ring_http)
    assert out["outcome"] == "door_open"
    assert out["door_sk"] == DOOR_SK
    assert len(out["still_keys"]) == 4
    [event] = door_events()
    assert event["sk"] == DOOR_SK
    assert event["device_id"] == "ava1.ring.device.D1"
    assert event["ring_event_id"] == "evt_1786715596000"
    assert event["opened_at"] == "2026-08-14T13:53:16.000Z"
    assert event["closed_at"] == "2026-08-14T13:53:41.000Z"
    assert event["duration_s"] == 25
    assert event["status"] == "analyzing"
    assert event["still_keys"] == out["still_keys"]


# Same Ring event in two runs
@respx.mock
def test_same_ring_event_in_two_runs(aws, ring_http):
    ring_serves([jpeg(0.8)])
    assert run(ring_http)["outcome"] == "door_open"
    second = run(ring_http, {**STATE, "timestamp_ms": 1786715597500, "request_id": "R2"})
    assert second["outcome"] == "duplicate"
    assert len(door_events()) == 1


# Door stayed closed
@respx.mock
def test_door_stayed_closed(aws, ring_http, caplog):
    caplog.set_level(logging.INFO)
    ring_serves([jpeg(0.1), jpeg(0.3)])
    out = run(ring_http)
    assert out["outcome"] == "not_door"
    assert door_events() == []
    [line] = [r.getMessage() for r in caplog.records if "motion_not_door" in r.getMessage()]
    assert '"brightest": 0.3' in line or '"brightest": 0.29' in line or '"brightest": 0.31' in line


# Too few stills
@respx.mock
def test_too_few_stills_records_no_media(aws, ring_http):
    ring_serves(None)
    out = run(ring_http)
    assert out["outcome"] == "no_media"
    [event] = door_events()
    assert event["status"] == "no_media"
    assert event["still_keys"] == []


@respx.mock
def test_fallback_window_claims_by_timestamp(aws, ring_http):
    ring_serves([jpeg(0.8)])
    state = {**STATE, "window": {**STATE["window"], "ring_event_id": None}}
    assert run(ring_http, state)["outcome"] == "door_open"
    assert run(ring_http, state)["outcome"] == "duplicate"


@respx.mock
def test_one_still_is_too_few(aws, ring_http):
    answers = iter([httpx.Response(303, headers={"Location": "https://dl.example.com/0"})])
    respx.post(DOWNLOAD).mock(side_effect=lambda request: next(answers, httpx.Response(403)))
    respx.get("https://dl.example.com/0").respond(200, content=jpeg(0.9))
    out = run(ring_http)
    assert out["outcome"] == "no_media"
    [event] = door_events()
    assert event["status"] == "no_media"
    assert len(event["still_keys"]) == 1
