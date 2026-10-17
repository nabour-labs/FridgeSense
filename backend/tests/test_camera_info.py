"""camera-info: status history, uptime and Ring device parsing."""

from datetime import UTC, datetime

import pytest

from fridgesense.camera_info import StatusChange, StatusHistory, parse_device, uptime
from fridgesense.table import FridgeTable
from tests.conftest import load_fixture

ACCOUNT = "ava1.ring.account.A1"
DEVICE = "ava1.ring.device.D1"


def ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).replace(tzinfo=UTC).timestamp() * 1000)


@pytest.fixture
def history(aws):
    return StatusHistory(FridgeTable())


# --- StatusHistory ---


def test_window_listed_newest_first(history):
    history.record(ACCOUNT, DEVICE, StatusChange(True, ms("2026-09-01T00:00"), "poll"))
    history.record(ACCOUNT, DEVICE, StatusChange(False, ms("2026-10-16T00:00"), "webhook"))
    history.record(ACCOUNT, DEVICE, StatusChange(True, ms("2026-10-16T06:00"), "webhook"))
    assert history.since(ACCOUNT, DEVICE, ms("2026-09-16T12:00")) == [
        StatusChange(True, ms("2026-10-16T06:00"), "webhook"),
        StatusChange(False, ms("2026-10-16T00:00"), "webhook"),
    ]


def test_status_before_the_window(history):
    history.record(ACCOUNT, DEVICE, StatusChange(False, ms("2026-08-01T00:00"), "poll"))
    history.record(ACCOUNT, DEVICE, StatusChange(True, ms("2026-09-01T00:00"), "poll"))
    history.record(ACCOUNT, DEVICE, StatusChange(False, ms("2026-10-16T00:00"), "webhook"))
    assert history.before(ACCOUNT, DEVICE, ms("2026-09-16T12:00")) == StatusChange(
        True, ms("2026-09-01T00:00"), "poll"
    )
    assert history.before(ACCOUNT, DEVICE, ms("2026-07-01T00:00")) is None


def test_latest_change(history):
    assert history.latest(ACCOUNT, DEVICE) is None
    history.record(ACCOUNT, DEVICE, StatusChange(True, ms("2026-10-16T06:00"), "webhook"))
    history.record(ACCOUNT, DEVICE, StatusChange(False, ms("2026-10-16T00:00"), "webhook"))
    assert history.latest(ACCOUNT, DEVICE) == StatusChange(True, ms("2026-10-16T06:00"), "webhook")


# Scenario: Other devices and accounts kept apart
def test_other_devices_and_accounts_kept_apart(history):
    offline = StatusChange(False, ms("2026-10-16T01:00"), "poll")
    history.record(ACCOUNT, "ava1.ring.device.D2", offline)
    history.record("ava1.ring.account.B2", DEVICE, offline)
    # D1 sorts before D10: the prefix must not match a longer device id.
    history.record(ACCOUNT, DEVICE + "0", StatusChange(False, ms("2026-10-16T03:00"), "poll"))
    assert history.since(ACCOUNT, DEVICE, 0) == []
    assert history.latest(ACCOUNT, DEVICE) is None
    assert history.before(ACCOUNT, DEVICE, ms("2026-10-17T00:00")) is None


# --- uptime ---


# Scenario: Uptime over the window
def test_uptime_over_the_window():
    changes = [
        StatusChange(True, ms("2026-10-16T06:00"), "webhook"),
        StatusChange(False, ms("2026-10-16T00:00"), "webhook"),
    ]
    before = StatusChange(True, ms("2026-09-01T00:00"), "poll")
    assert uptime(changes, before, ms("2026-10-16T12:00")) == {
        "window_days": 30,
        "percent": 99.2,
        "since": "2026-09-16T12:00:00.000Z",
    }


# Scenario: Short history
def test_uptime_short_history():
    changes = [
        StatusChange(False, ms("2026-10-16T09:00"), "poll"),
        StatusChange(True, ms("2026-10-16T00:00"), "poll"),
    ]
    assert uptime(changes, None, ms("2026-10-16T12:00")) == {
        "window_days": 30,
        "percent": 75.0,
        "since": "2026-10-16T00:00:00.000Z",
    }


# Scenario: No history
def test_uptime_no_history():
    assert uptime([], None, ms("2026-10-16T12:00")) == {
        "window_days": 30,
        "percent": None,
        "since": None,
    }


def test_uptime_only_status_before_the_window():
    before = StatusChange(False, ms("2026-09-01T00:00"), "poll")
    assert uptime([], before, ms("2026-10-16T12:00"))["percent"] == 0.0


def test_uptime_change_just_now_counts_as_full_window_of_its_state():
    # The first read records "online" at now: no time has passed yet, so 100%, not a division by 0.
    now = ms("2026-10-16T12:00")
    assert uptime([StatusChange(True, now, "poll")], None, now)["percent"] == 100.0


# --- parse_device ---


def detail():
    return load_fixture("ring/device_detail.json")


# Scenario: Camera details
def test_camera_details():
    d = parse_device(detail(), DEVICE)
    assert d["device_id"] == DEVICE
    assert d["name"] == "Fridge Cam"
    assert d["manufacturer"] == "Ring"
    assert d["online"] is True
    assert d["image_url"] == detail()["data"]["attributes"]["image_url"]
    assert d["video"] == {
        "codecs": ["AVC"],
        "ratio": "16:9",
        "max_resolution": 1080,
        "supported_resolutions": [1080],
    }


def test_camera_details_from_the_device_list():
    doc = detail()
    doc["data"] = [{**doc["data"], "id": "ava1.ring.device.OTHER"}, doc["data"]]
    assert parse_device(doc, DEVICE)["name"] == "Fridge Cam"


# Scenario: Image enhancements supported and on
def test_image_enhancements_supported_and_on():
    assert parse_device(detail(), DEVICE)["image_enhancements"] == [
        {"name": "color_night_vision", "on": False},
        {"name": "hdr", "on": True},
        {"name": "ir_led_night_vision", "on": False},
    ]


# Scenario: Motion detection and encryption
def test_motion_detection_and_encryption():
    d = parse_device(detail(), DEVICE)
    assert d["motion_detection"] is True
    assert d["e2e_encryption"] is False


def test_motion_detection_off_and_encryption_on():
    doc = detail()
    conf = next(i for i in doc["included"] if i["type"] == "device-configurations")
    conf["attributes"]["motion_detection"]["enabled"] = "off"
    conf["attributes"]["e2e_encryption"]["enabled"] = True
    d = parse_device(doc, DEVICE)
    assert d["motion_detection"] is False
    assert d["e2e_encryption"] is True


# Scenario: Coarse location
def test_coarse_location():
    assert parse_device(detail(), DEVICE)["location"] == {"country": "US", "state": "WA"}
    doc = detail()
    doc["included"] = [i for i in doc["included"] if i["type"] != "locations"]
    assert parse_device(doc, DEVICE)["location"] is None


def test_missing_included_resources_give_null_fields():
    doc = detail()
    del doc["included"]
    d = parse_device(doc, DEVICE)
    assert d["name"] == "Fridge Cam"
    for field in (
        "online",
        "video",
        "image_enhancements",
        "motion_detection",
        "e2e_encryption",
        "location",
    ):
        assert d[field] is None, field


def test_enhancements_without_configurations_are_unknown():
    doc = detail()
    doc["included"] = [i for i in doc["included"] if i["type"] != "device-configurations"]
    d = parse_device(doc, DEVICE)
    assert d["image_enhancements"] == [
        {"name": "color_night_vision", "on": None},
        {"name": "hdr", "on": None},
        {"name": "ir_led_night_vision", "on": None},
    ]
    assert d["motion_detection"] is None and d["e2e_encryption"] is None


# Scenario: Supported capability without an on/off setting
def test_recorded_device_response():
    d = parse_device(load_fixture("ring/device_detail_recorded.json"), DEVICE)
    assert d["name"] == "Fridge"
    assert d["online"] is False
    assert d["video"] == {
        "codecs": ["AVC"],
        "ratio": "16:9",
        "max_resolution": 1440,
        "supported_resolutions": [1440],
    }
    assert d["image_enhancements"] == [{"name": "ir_led_night_vision", "on": False}]
    assert d["motion_detection"] is True and d["e2e_encryption"] is False
    assert d["location"] == {"country": "US", "state": "Washington"}
