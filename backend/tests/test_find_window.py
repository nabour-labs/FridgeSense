"""door-event-detection: Event window from Ring's history."""

import httpx
import pytest
import respx

from fridgesense.door_events import MAX_WINDOW_CHECKS, find_window
from fridgesense.oauth import OAuthClient
from fridgesense.ring import API_BASE, RingClient
from fridgesense.store import Tokens
from tests.conftest import MemoryTokenStore, load_fixture

NOW = 1_786_715_700.0
HISTORY = f"{API_BASE}/v1/history/devices/ava1.ring.device.D1/events"
RUN = {
    "account_id": "ava1.ring.account.A1",
    "device_id": "ava1.ring.device.D1",
    "timestamp_ms": 1786715596787,
    "request_id": "R1",
}


@pytest.fixture
def ring():
    tokens = Tokens(
        account_id="ava1.ring.account.A1",
        access_token="at1",
        refresh_token="rt1",
        expires_at=int(NOW) + 3600,
        link_status="linked",
    )
    with httpx.Client() as http:
        yield RingClient(http, MemoryTokenStore(tokens), OAuthClient(http, "c", "s"), lambda: NOW)


def run(ring, attempt=None, **overrides):
    state = {**RUN, **overrides}
    if attempt is not None:
        state["attempt"] = attempt
    return find_window(ring, state)


# Recording finished
@respx.mock
def test_recording_finished(ring):
    route = respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events.json"))
    out = run(ring)
    assert route.calls.last.request.url.params["event_types"] == "motion"
    assert out["window"] == {
        "status": "ready",
        "start_ms": 1786715596000,
        "end_ms": 1786715621000,
        "ring_event_id": "evt_1786715596000",
    }
    assert out["account_id"] == RUN["account_id"]  # run input is carried forward


# Timestamps as strings
@respx.mock
def test_timestamps_as_strings(ring):
    respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events_string_ts.json"))
    w = run(ring)["window"]
    assert (w["start_ms"], w["end_ms"]) == (1786715596000, 1786715621000)


# Recording not finished yet
@respx.mock
def test_recording_not_finished_yet(ring):
    respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events_pending.json"))
    out = run(ring)
    assert out["window"] == {"status": "pending"}
    assert out["attempt"] == 2


@respx.mock
def test_no_event_within_ten_seconds_is_pending(ring):
    respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events.json"))
    out = run(ring, timestamp_ms=1786715596000 + 10_001)
    assert out["window"] == {"status": "pending"}


@respx.mock
def test_event_just_within_ten_seconds_matches(ring):
    respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events.json"))
    out = run(ring, timestamp_ms=1786715596000 - 10_000)
    assert out["window"]["ring_event_id"] == "evt_1786715596000"


@respx.mock
def test_ring_error_counts_as_pending(ring):
    respx.get(HISTORY).respond(503)
    assert run(ring)["window"] == {"status": "pending"}


# Recording never finishes
@respx.mock
def test_recording_never_finishes(ring):
    respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events_pending.json"))
    assert MAX_WINDOW_CHECKS == 6
    assert run(ring, attempt=5)["window"]["status"] == "pending"
    out = run(ring, attempt=6)
    assert out["window"] == {
        "status": "ready",
        "start_ms": 1786715596787,
        "end_ms": 1786715596787 + 30_000,
        "ring_event_id": None,
    }
