"""Setup problems that silently stop door openings from being recorded or detected well, each
with what fixes it."""

from fridgesense import alignment, camera_info, door_calibration, fridge_area, monitoring
from fridgesense.door_events import iso_utc
from fridgesense.ring import RingClient
from fridgesense.table import FridgeTable

NEEDS_RELINK = (
    "The Ring account link has expired, so door openings are not recorded. "
    "Re-link the Ring account in the Ring app."
)
PAUSED = "FridgeSense is paused, so door openings are not recorded."
MOTION_OFF = (
    "Motion detection is off on the camera, so no door openings are recorded. "
    "Turn it on in the Ring app."
)
SETUP_MISSING = (
    "Open/close detection is not set up, so the default zones are used and openings may be missed."
)
CAMERA_MOVED = (
    "The camera has moved or changed angle. Update the references so detection stays accurate."
)


def camera_moved(table: FridgeTable, account_id: str, device_id: str) -> dict | None:
    """The camera-moved warning, listing what still needs updating since it last moved."""
    state = alignment.load_alignment(table, account_id, device_id)
    if state is None or state.last_moved_at_ms is None:
        return None
    since = iso_utc(state.last_moved_at_ms)
    update = []
    if state.moved:
        update.append("door_references")
    area = fridge_area.load(table, account_id, device_id)
    if area is not None and area.updated_at < since:
        update.append("fridge_area")
    if not update:
        return None
    return {"code": "camera_moved", "message": CAMERA_MOVED, "since": since, "update": update}


def warnings_body(
    ring: RingClient,
    table: FridgeTable,
    account_id: str,
    device_id: str | None,
    now_ms: int,
    link_status: str = "linked",
) -> dict:
    """`GET /api/warnings`. A Ring failure only leaves out the motion-detection check."""
    found: list[dict] = []
    if link_status == "needs_relink":
        found.append({"code": "needs_relink", "message": NEEDS_RELINK})
    if device_id is not None:
        state = monitoring.load(table, account_id, device_id)
        if state.paused:
            found.append({"code": "monitoring_paused", "message": PAUSED, "since": state.since})
        details = camera_info.fetch_device(ring, device_id)
        if details is not None and details["motion_detection"] is False:
            found.append({"code": "motion_detection_off", "message": MOTION_OFF})
        if door_calibration.load_setup(table, account_id, device_id) is None:
            found.append({"code": "door_setup_missing", "message": SETUP_MISSING})
        moved = camera_moved(table, account_id, device_id)
        if moved is not None:
            found.append(moved)
    return {"warnings": found, "checked_at": iso_utc(now_ms)}
