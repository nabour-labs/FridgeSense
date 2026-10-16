"""What the app knows about the camera: Ring's device details, and its online/offline history."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from fridgesense.door_events import iso_utc
from fridgesense.logs import log_event
from fridgesense.oauth import OAuthRejected, OAuthUnavailable
from fridgesense.ring import RingAuthError, RingClient
from fridgesense.table import FridgeTable, account_pk

INCLUDE = "status,capabilities,configurations,location"
DETAIL_FIELDS = (
    "online",
    "video",
    "image_enhancements",
    "motion_detection",
    "e2e_encryption",
    "location",
)
WINDOW_DAYS = 30
DAY_MS = 24 * 3600 * 1000


@dataclass(frozen=True)
class StatusChange:
    online: bool
    at_ms: int
    source: str  # "webhook" or "poll"


def status_prefix(device_id: str) -> str:
    return f"STATUS#{device_id}#"


def status_sk(device_id: str, at_ms: int) -> str:
    return f"{status_prefix(device_id)}{at_ms:013d}"


def _change(item: dict) -> StatusChange:
    return StatusChange(bool(item["online"]), int(item["at_ms"]), item["source"])


class StatusHistory:
    """A device's online/offline changes, one item each, in time order by sort key."""

    def __init__(self, table: FridgeTable):
        self.table = table

    def record(self, account_id: str, device_id: str, change: StatusChange) -> None:
        self.table.put(
            {
                "pk": account_pk(account_id),
                "sk": status_sk(device_id, change.at_ms),
                "online": change.online,
                "at_ms": change.at_ms,
                "source": change.source,
            }
        )

    def since(self, account_id: str, device_id: str, from_ms: int) -> list[StatusChange]:
        """Changes at or after `from_ms`, newest first."""
        items = self.table.query_range(
            account_id,
            status_sk(device_id, max(from_ms, 0)),
            status_prefix(device_id) + "9" * 13,
            newest_first=True,
        )
        return [_change(i) for i in items]

    def before(self, account_id: str, device_id: str, at_ms: int) -> StatusChange | None:
        """The last change before `at_ms`."""
        items = self.table.query_range(
            account_id,
            status_sk(device_id, 0),
            status_sk(device_id, max(at_ms - 1, 0)),
            newest_first=True,
            limit=1,
        )
        return _change(items[0]) if items else None

    def latest(self, account_id: str, device_id: str) -> StatusChange | None:
        return self.before(account_id, device_id, 10**13)


def uptime(
    changes: list[StatusChange],
    before: StatusChange | None,
    now_ms: int,
    window_days: int = WINDOW_DAYS,
) -> dict:
    """Share of time online from the window start (or the first change, if later) until now.

    `changes` are the window's changes, newest first; `before` is the last change before it."""
    window_start = now_ms - window_days * DAY_MS
    ordered = sorted(changes, key=lambda c: c.at_ms)
    if before is not None:
        start, state = window_start, before.online
    elif ordered:
        start, state = ordered[0].at_ms, ordered[0].online
    else:
        return {"window_days": window_days, "percent": None, "since": None}

    online_ms, at = 0, start
    for c in ordered:
        if c.at_ms > at:
            online_ms += (c.at_ms - at) if state else 0
            at = c.at_ms
        state = c.online
    online_ms += (now_ms - at) if state else 0
    total = now_ms - start
    percent = round(online_ms / total * 100, 1) if total > 0 else (100.0 if state else 0.0)
    return {"window_days": window_days, "percent": percent, "since": iso_utc(start)}


def _on_off(value: Any) -> bool | None:
    return {"on": True, "off": False}.get(value) if isinstance(value, str) else None


def parse_device(doc: dict, device_id: str) -> dict[str, Any]:
    """The camera's details from a Ring JSON:API compound document (one device, or the list).

    Ring reports no model or firmware; every Partner API device is made by Ring. Anything
    Ring did not include is None."""
    data = doc["data"]
    device = next(d for d in data if d["id"] == device_id) if isinstance(data, list) else data
    attrs = device.get("attributes", {})
    included = {
        (i.get("type"), i.get("id")): i.get("attributes", {}) for i in doc.get("included", [])
    }

    def related(name: str) -> dict | None:
        link = (device.get("relationships", {}).get(name) or {}).get("data") or {}
        return included.get((link.get("type"), link.get("id")))

    status, caps = related("status"), related("capabilities")
    conf, location = related("configurations"), related("location")

    video = None
    if caps and isinstance(caps.get("video"), dict):
        v = caps["video"]
        video = {
            "codecs": list(v.get("codecs") or []),
            "ratio": v.get("ratio"),
            "max_resolution": v.get("max_resolution"),
            "supported_resolutions": list(v.get("supported_resolutions") or []),
        }

    enhancements = None
    if caps and isinstance(caps.get("image_enhancements"), dict):
        settings = (conf or {}).get("image_enhancements") or {}
        enhancements = [
            {"name": name, "on": _on_off(settings.get(name))}
            for name in caps["image_enhancements"].get("configurations") or []
            if not name.endswith("_zones")  # zones are polygons, not an on/off setting
        ]

    e2e = ((conf or {}).get("e2e_encryption") or {}).get("enabled")
    online = (status or {}).get("online")
    return {
        "device_id": device["id"],
        "name": attrs.get("name", device["id"]),
        "image_url": attrs.get("image_url"),
        "manufacturer": "Ring",
        "online": online if isinstance(online, bool) else None,
        "video": video,
        "image_enhancements": enhancements,
        "motion_detection": _on_off(((conf or {}).get("motion_detection") or {}).get("enabled")),
        "e2e_encryption": e2e if isinstance(e2e, bool) else None,
        "location": {k: v for k, v in location.items() if isinstance(v, str)} if location else None,
    }


def fetch_device(ring: RingClient, device_id: str) -> dict[str, Any] | None:
    """The camera's details from Ring in one call, or None if Ring could not answer."""
    try:
        resp = ring.get(f"/v1/devices/{device_id}", params={"include": INCLUDE})
    except (httpx.HTTPError, RingAuthError, OAuthRejected, OAuthUnavailable) as e:
        log_event("camera_info_unavailable", logging.WARNING, error=type(e).__name__)
        return None
    if resp.status_code != 200:
        log_event("camera_info_unavailable", logging.WARNING, status=resp.status_code)
        return None
    try:
        return parse_device(resp.json(), device_id)
    except (ValueError, KeyError, TypeError, StopIteration) as e:
        log_event("camera_info_unavailable", logging.WARNING, error=type(e).__name__)
        return None


def camera_body(
    ring: RingClient,
    history: StatusHistory,
    account_id: str,
    device_id: str,
    stored_name: str,
    now_ms: int,
) -> dict[str, Any]:
    """`GET /api/camera`: Ring's details, plus the recorded history; a status Ring reports
    that differs from the newest recorded one is recorded first."""
    details = fetch_device(ring, device_id)
    if details is None:
        body: dict[str, Any] = {
            "device_id": device_id,
            "name": stored_name,
            "image_url": None,
            "manufacturer": "Ring",
            **dict.fromkeys(DETAIL_FIELDS),
            "ring": "unavailable",
        }
    else:
        body = details
        online = details["online"]
        latest = history.latest(account_id, device_id)
        if online is not None and (latest is None or latest.online != online):
            history.record(account_id, device_id, StatusChange(online, now_ms, "poll"))

    window_start = now_ms - WINDOW_DAYS * DAY_MS
    changes = history.since(account_id, device_id, window_start)
    before = history.before(account_id, device_id, window_start)
    return {
        **body,
        "history": [
            {"online": c.online, "at": iso_utc(c.at_ms), "source": c.source} for c in changes
        ],
        "uptime": uptime(changes, before, now_ms),
        "checked_at": iso_utc(now_ms),
    }
