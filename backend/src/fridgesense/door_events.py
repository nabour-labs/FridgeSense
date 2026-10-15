"""Door-event workflow steps: event window, stills and the door-open check."""

import logging
from typing import Any

import httpx

from fridgesense.logs import log_event
from fridgesense.oauth import OAuthRejected, OAuthUnavailable
from fridgesense.ring import RingAuthError, RingClient

MATCH_TOLERANCE_MS = 10_000
MAX_WINDOW_CHECKS = 6
FALLBACK_DURATION_MS = 30_000


def _ms(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def find_window(ring: RingClient, state: dict) -> dict:
    """Find the motion event's start and end in Ring's history.

    Returns the run state with `window` set to ready or pending; after
    MAX_WINDOW_CHECKS pending checks it falls back to timestamp + 30 s.
    """
    attempt = int(state.get("attempt", 1))
    ts = int(state["timestamp_ms"])
    match = _matching_event(ring, state["device_id"], ts)
    if match is not None:
        window = {"status": "ready", **match}
    elif attempt >= MAX_WINDOW_CHECKS:
        log_event("window_fallback", logging.WARNING, device_id=state["device_id"], timestamp_ms=ts)
        window = {
            "status": "ready",
            "start_ms": ts,
            "end_ms": ts + FALLBACK_DURATION_MS,
            "ring_event_id": None,
        }
    else:
        window = {"status": "pending"}
    return {**state, "window": window, "attempt": attempt + 1}


def _matching_event(ring: RingClient, device_id: str, ts: int) -> dict | None:
    try:
        resp = ring.get(f"/v1/history/devices/{device_id}/events", params={"event_types": "motion"})
    except (httpx.HTTPError, RingAuthError, OAuthRejected, OAuthUnavailable) as e:
        log_event("history_unavailable", logging.WARNING, error=type(e).__name__)
        return None
    if resp.status_code != 200:
        log_event("history_unavailable", logging.WARNING, status=resp.status_code)
        return None
    best = None
    for event in resp.json().get("data", []):
        attrs = event.get("attributes", {})
        start = _ms(attrs.get("start"))
        if start is None or abs(start - ts) > MATCH_TOLERANCE_MS:
            continue
        if best is None or abs(start - ts) < abs(best[0] - ts):
            best = (start, _ms(attrs.get("end")), event.get("id"))
    if best is None or best[1] is None:
        return None
    return {"start_ms": best[0], "end_ms": best[1], "ring_event_id": best[2]}
