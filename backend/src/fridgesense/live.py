"""Live view: WHEP sessions at Ring. The browser streams from Ring; only SDP passes through here."""

import logging

import httpx

from fridgesense.logs import log_event
from fridgesense.ring import RingAuthError, RingClient

MAX_SECONDS = 60  # Ring's limit per session on plug-in cameras


class LiveFailed(Exception):
    """Ring refused, failed or could not be reached; the live view cannot start or stop."""


def _sessions(device_id: str) -> str:
    return f"/v1/devices/{device_id}/media/streaming/whep/sessions"


def _call(ring: RingClient, method: str, path: str, device_id: str, **kwargs) -> httpx.Response:
    try:
        return ring.request(method, path, **kwargs)
    except (httpx.HTTPError, RingAuthError) as e:
        log_event("live_failed", logging.WARNING, device_id=device_id, error=type(e).__name__)
        raise LiveFailed() from e


def start(ring: RingClient, device_id: str, offer: str) -> tuple[str, str]:
    """(SDP answer, session id) for a new live session on the camera."""
    resp = _call(
        ring,
        "POST",
        _sessions(device_id),
        device_id,
        content=offer.encode(),
        headers={"Content-Type": "application/sdp"},
    )
    session_id = resp.headers.get("location", "").rstrip("/").rsplit("/", 1)[-1]
    if not resp.is_success or not session_id:
        log_event("live_failed", logging.WARNING, device_id=device_id, status=resp.status_code)
        raise LiveFailed()
    return resp.text, session_id


def stop(ring: RingClient, device_id: str, session_id: str) -> None:
    """End the session at Ring; one that is already gone counts as ended."""
    resp = _call(ring, "DELETE", f"{_sessions(device_id)}/{session_id}", device_id)
    if not resp.is_success and resp.status_code != 404:
        log_event("live_failed", logging.WARNING, device_id=device_id, status=resp.status_code)
        raise LiveFailed()
