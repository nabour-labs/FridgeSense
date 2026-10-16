"""door-event-detection: still sampling across the window, and the open span."""

import json

import httpx
import pytest
import respx

from fridgesense.door_events import (
    download_stills,
    open_span,
    parse_interval,
    pick,
    still_count,
    still_times,
)
from fridgesense.oauth import OAuthClient
from fridgesense.ring import API_BASE, RingClient
from fridgesense.store import Tokens
from tests.conftest import MemoryTokenStore, jpeg

NOW = 1_786_715_700.0
DOWNLOAD = f"{API_BASE}/v1/devices/ava1.ring.device.D1/media/image/download"
START = 1786715596000


def state(end_ms: int) -> dict:
    return {
        "account_id": "ava1.ring.account.A1",
        "device_id": "ava1.ring.device.D1",
        "window": {"status": "ready", "start_ms": START, "end_ms": end_ms},
    }


@pytest.fixture
def clients():
    tokens = Tokens(
        account_id="ava1.ring.account.A1",
        access_token="at1",
        refresh_token="rt1",
        expires_at=int(NOW) + 3600,
        link_status="linked",
    )
    with httpx.Client() as http:
        ring = RingClient(http, MemoryTokenStore(tokens), OAuthClient(http, "c", "s"), lambda: NOW)
        yield ring, http


def requested_timestamps(clients, end_ms: int, interval_ms: int = 1000) -> list[int]:
    post = respx.post(DOWNLOAD).mock(
        side_effect=lambda r: httpx.Response(
            303,
            headers={"Location": f"https://dl.example.com/{json.loads(r.content)['timestamp']}"},
        )
    )
    respx.get(url__startswith="https://dl.example.com/").respond(200, content=jpeg(0.5))
    ring, http = clients
    raw = download_stills(ring, http, state(end_ms), lambda s: None, interval_ms=interval_ms)
    assert [n for n, _ in raw] == list(range(1, len(raw) + 1))
    return sorted(json.loads(c.request.content)["timestamp"] for c in post.calls)


# One still per second
@respx.mock
def test_one_still_per_second(aws, clients):
    times = requested_timestamps(clients, START + 25_000)
    assert len(times) == 25
    assert times[0] == 1786715596961
    assert times[-1] == 1786715620038


# Long window capped at 30 stills
@respx.mock
def test_long_window_capped_at_30_stills(aws, clients):
    times = requested_timestamps(clients, START + 60_000)
    assert len(times) == 30
    assert times == still_times(START, START + 60_000, 30)


# Short window keeps 4 stills
@respx.mock
def test_short_window_keeps_4_stills(aws, clients):
    times = requested_timestamps(clients, START + 2_000)
    assert times == [1786715596400, 1786715596800, 1786715597200, 1786715597600]


@pytest.mark.parametrize(
    "span_ms, interval_ms, count",
    [(25_000, 1000, 25), (60_000, 1000, 30), (2_000, 1000, 4), (25_000, 10_000, 4), (0, 1000, 4)],
)
def test_still_count(span_ms, interval_ms, count):
    assert still_count(span_ms, interval_ms) == count


# Invalid interval config
@pytest.mark.parametrize("value", ["0", "-500", "fast", "1.5"])
def test_invalid_interval_config(value):
    with pytest.raises(ValueError, match="STILL_INTERVAL_MS"):
        parse_interval(value)


@pytest.mark.parametrize("value, expected", [(None, 1000), ("", 1000), ("2000", 2000)])
def test_interval_config(value, expected):
    assert parse_interval(value) == expected


def scores_open(count: int, open_numbers: set[int]) -> list[float]:
    """Scores for stills 1..count where the given still numbers are open (threshold 0.02)."""
    return [0.1 if n in open_numbers else 0.0 for n in range(1, count + 1)]


# Four stills saved (open stills 6-15 of 25 -> stills 6, 9, 13, 16)
def test_open_span_and_four_picks():
    span = open_span(scores_open(25, set(range(6, 16))), 0.02)
    assert [i + 1 for i in span] == list(range(6, 17))
    assert [i + 1 for i in pick(span)] == [6, 9, 13, 16]


# Short open span (only still 10 open -> stills 10, 11)
def test_short_open_span():
    span = open_span(scores_open(25, {10}), 0.02)
    assert [i + 1 for i in pick(span)] == [10, 11]


# Door still open at the end of the window: the span ends at the last still
def test_open_span_until_the_last_still():
    span = open_span(scores_open(25, {23, 24, 25}), 0.02)
    assert [i + 1 for i in span] == [23, 24, 25]


def test_open_span_includes_closed_stills_between_open_ones():
    span = open_span(scores_open(10, {2, 5}), 0.02)
    assert [i + 1 for i in span] == [2, 3, 4, 5, 6]


def test_no_open_still_has_no_span():
    assert open_span(scores_open(25, set()), 0.02) is None


def test_threshold_is_inclusive_per_still():
    assert open_span([0.0, 0.02, 0.0], 0.02) == [1, 2]
