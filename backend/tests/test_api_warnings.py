"""setup-warnings: GET /api/warnings."""

import httpx
import pytest
import respx

from fridgesense import alignment, door_calibration, fridge_area
from fridgesense.devices import Device, DeviceRepository
from fridgesense.door_events import iso_utc
from fridgesense.handlers import api
from fridgesense.ring import API_BASE
from fridgesense.store import load_app_config
from fridgesense.table import FridgeTable
from tests.api_helpers import ACCOUNT, NOW, call, configure, link_account, sign_in
from tests.conftest import color_jpeg, load_fixture

DEVICE = "ava1.ring.device.D1"
DETAIL = f"{API_BASE}/v1/devices/{DEVICE}"
INCLUDE = {"include": "status,capabilities,configurations,location"}
NOW_MS = int(NOW * 1000)
HOUR_MS = 3600 * 1000
GREY = (128, 128, 128)
LEFT = {"x": 0, "y": 0, "width": 0.5, "height": 1}
MOTION_OFF = {
    "code": "motion_detection_off",
    "message": "Motion detection is off on the camera, so no door openings are recorded. "
    "Turn it on in the Ring app.",
}
SETUP_MISSING = {
    "code": "door_setup_missing",
    "message": "Open/close detection is not set up, so the default zones are used and openings "
    "may be missed.",
}
MOVED_MESSAGE = (
    "The camera has moved or changed angle. Update the references so detection stays accurate."
)


@pytest.fixture
def tokens(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    link_account()
    configure(demo_passcode="look-only")
    load_app_config(refresh=True)
    DeviceRepository().replace(ACCOUNT, [Device(DEVICE, "Fridge")])
    return {"owner": sign_in(), "viewer": sign_in("look-only")}


def ring_motion(enabled="on", status=200):
    doc = load_fixture("ring/device_detail.json")
    conf = next(i for i in doc["included"] if i["type"] == "device-configurations")
    if enabled is None:
        del conf["attributes"]["motion_detection"]
    else:
        conf["attributes"]["motion_detection"]["enabled"] = enabled
    return respx.get(DETAIL, params=INCLUDE).respond(status, json=doc if status == 200 else {})


def set_up_door(at=NOW_MS - 10 * HOUR_MS):
    table = FridgeTable()
    lit = color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), (40, 90, 200))], size=(200, 100))
    z = door_calibration.add_zone(table, ACCOUNT, DEVICE, "Doors", LEFT, at, source="clip").sk
    door_calibration.add_reference(table, ACCOUNT, DEVICE, lit, z, "open", at, source="clip")
    closed = color_jpeg(GREY, size=(200, 100))
    door_calibration.add_reference(
        table, ACCOUNT, DEVICE, closed, z, "closed", at + 1, source="clip"
    )
    door_calibration.run(table, ACCOUNT, DEVICE, at + 2)


def camera_moves(at):
    moved = alignment.Alignment(True, 0.05, 0, 0.01, "first")
    alignment.record(FridgeTable(), ACCOUNT, DEVICE, moved, at)


def save_area(at):
    fridge_area.save(FridgeTable(), ACCOUNT, DEVICE, color_jpeg(size=(200, 100)), LEFT, now_ms=at)


def warnings(token):
    status, body = call("GET", "/api/warnings", token=token)
    assert status == 200
    assert body["checked_at"] == iso_utc(NOW_MS)
    return body["warnings"]


# All set up
@respx.mock
def test_all_set_up(tokens):
    ring_motion("on")
    set_up_door()
    assert warnings(tokens["owner"]) == []


# Several warnings in order
@respx.mock
def test_several_warnings_in_order(tokens):
    ring_motion("off")
    assert warnings(tokens["viewer"]) == [MOTION_OFF, SETUP_MISSING]


@respx.mock
def test_all_three_in_order(tokens):
    ring_motion("off")
    camera_moves(NOW_MS - HOUR_MS)  # alignment state without a setup result
    assert [w["code"] for w in warnings(tokens["owner"])] == [
        "motion_detection_off",
        "door_setup_missing",
        "camera_moved",
    ]


# No token
def test_no_token(aws):
    assert call("GET", "/api/warnings") == (401, {"error": "sign in"})


# No camera yet
def test_no_camera_yet(tokens):
    DeviceRepository().replace(ACCOUNT, [])
    assert warnings(tokens["owner"]) == []


# Motion detection off
@respx.mock
def test_motion_detection_off(tokens):
    ring_motion("off")
    set_up_door()
    assert warnings(tokens["owner"]) == [MOTION_OFF]


# Ring unreachable
@respx.mock
@pytest.mark.parametrize("failure", ["timeout", 500])
def test_ring_unreachable(tokens, failure):
    if failure == "timeout":
        respx.get(DETAIL, params=INCLUDE).mock(side_effect=httpx.ReadTimeout("slow"))
    else:
        ring_motion(status=500)
    assert warnings(tokens["owner"]) == [SETUP_MISSING]


@respx.mock
def test_motion_setting_not_reported(tokens):
    ring_motion(enabled=None)
    set_up_door()
    assert warnings(tokens["owner"]) == []


# Setup never run
@respx.mock
def test_setup_never_run(tokens):
    ring_motion("on")
    closed = color_jpeg(GREY, size=(200, 100))
    z = door_calibration.add_zone(
        FridgeTable(), ACCOUNT, DEVICE, "Doors", LEFT, NOW_MS, source="clip"
    ).sk
    door_calibration.add_reference(
        FridgeTable(), ACCOUNT, DEVICE, closed, z, "closed", NOW_MS, source="clip"
    )
    assert warnings(tokens["owner"]) == [SETUP_MISSING]


# Setup run
@respx.mock
def test_setup_run(tokens):
    ring_motion("on")
    set_up_door()
    assert "door_setup_missing" not in [w["code"] for w in warnings(tokens["owner"])]


# Both need updating
@respx.mock
def test_both_need_updating(tokens):
    ring_motion("on")
    set_up_door()
    save_area(NOW_MS - 24 * HOUR_MS)
    moved_at = NOW_MS - 2 * HOUR_MS
    camera_moves(moved_at)
    assert warnings(tokens["owner"]) == [
        {
            "code": "camera_moved",
            "message": MOVED_MESSAGE,
            "since": iso_utc(moved_at),
            "update": ["door_references", "fridge_area"],
        }
    ]


# Fridge area already updated
@respx.mock
def test_fridge_area_already_updated(tokens):
    ring_motion("on")
    set_up_door()
    camera_moves(NOW_MS - 2 * HOUR_MS)
    save_area(NOW_MS - HOUR_MS)
    [moved] = warnings(tokens["owner"])
    assert moved["update"] == ["door_references"]


# No fridge area
@respx.mock
def test_no_fridge_area(tokens):
    ring_motion("on")
    set_up_door()
    camera_moves(NOW_MS - 2 * HOUR_MS)
    [moved] = warnings(tokens["owner"])
    assert moved["update"] == ["door_references"]


# Setup run but fridge area not updated
@respx.mock
def test_setup_run_but_fridge_area_not_updated(tokens):
    ring_motion("on")
    set_up_door()
    save_area(NOW_MS - 24 * HOUR_MS)
    moved_at = NOW_MS - 2 * HOUR_MS
    camera_moves(moved_at)
    set_up_door(at=NOW_MS - HOUR_MS)  # the owner re-runs setup
    [moved] = warnings(tokens["owner"])
    assert moved["code"] == "camera_moved"
    assert moved["since"] == iso_utc(moved_at)
    assert moved["update"] == ["fridge_area"]


# Both updated
@respx.mock
def test_both_updated(tokens):
    ring_motion("on")
    set_up_door()
    save_area(NOW_MS - 24 * HOUR_MS)
    camera_moves(NOW_MS - 2 * HOUR_MS)
    set_up_door(at=NOW_MS - HOUR_MS)
    save_area(NOW_MS - HOUR_MS + 5)
    assert warnings(tokens["owner"]) == []


# --- monitoring paused (fridge-monitoring) ---

PAUSED_MS = 1792332300000  # 2026-10-18T14:05:00Z
PAUSED = {
    "code": "monitoring_paused",
    "message": "FridgeSense is paused, so door openings are not recorded.",
    "since": "2026-10-18T14:05:00.000Z",
}


def pause():
    from fridgesense import monitoring

    monitoring.set_paused(FridgeTable(), ACCOUNT, DEVICE, True, PAUSED_MS)


# Scenario: Paused
@respx.mock
def test_monitoring_paused(tokens):
    ring_motion("on")
    set_up_door()
    pause()
    assert warnings(tokens["viewer"]) == [PAUSED]


# Scenario: Paused with other problems
@respx.mock
def test_paused_with_other_problems(tokens):
    ring_motion("on")
    pause()
    assert warnings(tokens["owner"]) == [PAUSED, SETUP_MISSING]


@respx.mock
def test_paused_listed_when_ring_unreachable(tokens):
    ring_motion(status=500)
    set_up_door()
    pause()
    assert warnings(tokens["owner"]) == [PAUSED]


# Scenario: Active
@respx.mock
def test_active_has_no_paused_warning(tokens):
    from fridgesense import monitoring

    ring_motion("on")
    set_up_door()
    pause()
    monitoring.set_paused(FridgeTable(), ACCOUNT, DEVICE, False, PAUSED_MS + 1000)
    assert warnings(tokens["owner"]) == []


# --- Ring account needs re-linking (failure-alerting) ---

RELINK = {
    "code": "needs_relink",
    "message": "The Ring account link has expired, so door openings are not recorded. "
    "Re-link the Ring account in the Ring app.",
}


def needs_relink():
    from fridgesense.store import TokenStore

    store = TokenStore()
    store.save(store.load().model_copy(update={"link_status": "needs_relink"}))


# Scenario: Link expired
@respx.mock
def test_link_expired(tokens):
    ring_motion("on")
    set_up_door()
    needs_relink()
    assert warnings(tokens["viewer"]) == [RELINK]


# Scenario: Link expired with other problems
@respx.mock
def test_link_expired_with_other_problems(tokens):
    ring_motion("on")
    needs_relink()
    assert warnings(tokens["owner"]) == [RELINK, SETUP_MISSING]


# Scenario: Link expired before any camera
def test_link_expired_before_any_camera(tokens):
    DeviceRepository().replace(ACCOUNT, [])
    needs_relink()
    assert warnings(tokens["owner"]) == [RELINK]


# Scenario: Linked
@respx.mock
def test_linked_has_no_relink_warning(tokens):
    ring_motion("off")
    assert "needs_relink" not in [w["code"] for w in warnings(tokens["owner"])]


# --- Door setup mismatch warning ---

MISMATCH = {
    "code": "door_setup_mismatch",
    "message": "Open/close detection doesn't match the camera's recordings, so the fridge light "
    "is used instead. Replace the door references with frames from recent clips and run setup "
    "again.",
}


def suspect_events(n: int) -> None:
    for _ in range(n):
        alignment.record_suspect(FridgeTable(), ACCOUNT, DEVICE, True)


# Three suspect events
@respx.mock
def test_three_suspect_events(tokens):
    ring_motion("on")
    set_up_door()
    suspect_events(3)
    assert warnings(tokens["owner"]) == [MISMATCH]


# Two suspect events
@respx.mock
def test_two_suspect_events(tokens):
    ring_motion("on")
    set_up_door()
    suspect_events(2)
    assert warnings(tokens["owner"]) == []


# Listed last
@respx.mock
def test_mismatch_listed_last(tokens):
    ring_motion("on")
    suspect_events(4)  # no setup result
    assert warnings(tokens["owner"]) == [SETUP_MISSING, MISMATCH]


# Cleared by setup
@respx.mock
def test_mismatch_cleared_by_setup(tokens):
    ring_motion("on")
    set_up_door(NOW_MS - 10 * HOUR_MS)
    suspect_events(3)
    set_up_door(NOW_MS - HOUR_MS)
    assert warnings(tokens["owner"]) == []


# Streak unreadable
@respx.mock
def test_streak_unreadable(tokens, monkeypatch):
    ring_motion("on")
    set_up_door()
    suspect_events(3)
    real = alignment.load_alignment
    calls = {"n": 0}

    def flaky(*args):
        calls["n"] += 1
        if calls["n"] == 2:  # camera_moved reads first; the streak read fails
            raise RuntimeError("table down")
        return real(*args)

    monkeypatch.setattr(alignment, "load_alignment", flaky)
    assert warnings(tokens["owner"]) == []
