"""camera-info: GET /api/camera."""

import httpx
import pytest
import respx

from fridgesense import deps
from fridgesense.camera_info import StatusChange, StatusHistory
from fridgesense.devices import Device, DeviceRepository
from fridgesense.handlers import api
from fridgesense.ring import API_BASE, RingAuthError
from fridgesense.store import load_app_config
from fridgesense.table import FridgeTable
from tests.api_helpers import ACCOUNT, NOW, call, configure, link_account, sign_in
from tests.conftest import load_fixture

DEVICE = "ava1.ring.device.D1"
DETAIL = f"{API_BASE}/v1/devices/{DEVICE}"
INCLUDE = {"include": "status,capabilities,configurations,location"}
NOW_MS = int(NOW * 1000)
HOUR_MS = 3600 * 1000


@pytest.fixture
def tokens(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    link_account()
    configure(demo_passcode="look-only")
    load_app_config(refresh=True)
    DeviceRepository().replace(ACCOUNT, [Device(DEVICE, "Fridge")])
    return {"owner": sign_in(), "viewer": sign_in("look-only")}


def history():
    return StatusHistory(FridgeTable())


def ring_answers(online=True, status=200):
    doc = load_fixture("ring/device_detail.json")
    next(i for i in doc["included"] if i["type"] == "device-status")["attributes"]["online"] = (
        online
    )
    return respx.get(DETAIL, params=INCLUDE).respond(status, json=doc if status == 200 else {})


# Scenario: Camera details
@respx.mock
def test_camera_details(tokens):
    route = ring_answers()
    status, body = call("GET", "/api/camera", token=tokens["viewer"])
    assert status == 200
    assert route.calls.last.request.headers["authorization"] == "Bearer at1"
    assert body["name"] == "Fridge Cam"
    assert body["manufacturer"] == "Ring"
    assert body["online"] is True
    assert body["video"] == {
        "codecs": ["AVC"],
        "ratio": "16:9",
        "max_resolution": 1080,
        "supported_resolutions": [1080],
    }
    assert body["image_url"].endswith("device_3x.png")
    assert body["motion_detection"] is True and body["e2e_encryption"] is False
    assert body["location"] == {"country": "US", "state": "WA"}
    assert body["checked_at"] == "2026-08-06T07:06:40.000Z"
    assert "ring" not in body


# Scenario: No camera linked
@respx.mock
def test_no_camera_linked(tokens):
    DeviceRepository().replace(ACCOUNT, [])
    route = ring_answers()
    assert call("GET", "/api/camera", token=tokens["owner"]) == (
        409,
        {"error": "no camera linked"},
    )
    assert not route.called


def test_not_signed_in(tokens):
    assert call("GET", "/api/camera") == (401, {"error": "sign in"})


# Scenario: Ring down
@respx.mock
def test_ring_down(tokens):
    history().record(ACCOUNT, DEVICE, StatusChange(True, NOW_MS - HOUR_MS, "webhook"))
    ring_answers(status=503)
    status, body = call("GET", "/api/camera", token=tokens["owner"])
    assert status == 200
    assert body["ring"] == "unavailable"
    assert body["name"] == "Fridge"
    for field in (
        "online",
        "video",
        "image_enhancements",
        "motion_detection",
        "e2e_encryption",
        "location",
    ):
        assert body[field] is None, field
    assert body["manufacturer"] == "Ring"
    assert body["history"] == [
        {"online": True, "at": "2026-08-06T06:06:40.000Z", "source": "webhook"}
    ]
    assert len(history().since(ACCOUNT, DEVICE, 0)) == 1


@respx.mock
def test_ring_timeout(tokens):
    respx.get(DETAIL, params=INCLUDE).mock(side_effect=httpx.ReadTimeout("slow"))
    status, body = call("GET", "/api/camera", token=tokens["owner"])
    assert status == 200 and body["ring"] == "unavailable"


# Scenario: Ring token rejected
def test_ring_token_rejected(tokens, monkeypatch):
    class Rejected:
        def get(self, *args, **kwargs):
            raise RingAuthError("refresh rejected")

    monkeypatch.setattr(deps, "ring_client", lambda now=None: Rejected())
    status, body = call("GET", "/api/camera", token=tokens["owner"])
    assert status == 200 and body["ring"] == "unavailable"
    assert history().since(ACCOUNT, DEVICE, 0) == []


# Scenario: First read records the status
@respx.mock
def test_first_read_records_the_status(tokens):
    ring_answers(online=True)
    _, body = call("GET", "/api/camera", token=tokens["viewer"])
    assert history().since(ACCOUNT, DEVICE, 0) == [StatusChange(True, NOW_MS, "poll")]
    assert body["history"][0] == {
        "online": True,
        "at": "2026-08-06T07:06:40.000Z",
        "source": "poll",
    }
    assert body["uptime"] == {
        "window_days": 30,
        "percent": 100.0,
        "since": "2026-08-06T07:06:40.000Z",
    }


# Scenario: Unchanged status is not recorded again
@respx.mock
def test_unchanged_status_is_not_recorded_again(tokens):
    history().record(ACCOUNT, DEVICE, StatusChange(True, NOW_MS - HOUR_MS, "webhook"))
    ring_answers(online=True)
    call("GET", "/api/camera", token=tokens["owner"])
    assert len(history().since(ACCOUNT, DEVICE, 0)) == 1


# Scenario: Missed webhook is caught up
@respx.mock
def test_missed_webhook_is_caught_up(tokens):
    history().record(ACCOUNT, DEVICE, StatusChange(False, NOW_MS - HOUR_MS, "webhook"))
    ring_answers(online=True)
    _, body = call("GET", "/api/camera", token=tokens["owner"])
    assert history().latest(ACCOUNT, DEVICE) == StatusChange(True, NOW_MS, "poll")
    assert [h["online"] for h in body["history"]] == [True, False]


@respx.mock
def test_history_and_uptime_in_the_body(tokens):
    day = 24 * HOUR_MS
    h = history()
    h.record(ACCOUNT, DEVICE, StatusChange(True, NOW_MS - 45 * day, "poll"))
    h.record(ACCOUNT, DEVICE, StatusChange(False, NOW_MS - 12 * HOUR_MS, "webhook"))
    h.record(ACCOUNT, DEVICE, StatusChange(True, NOW_MS - 6 * HOUR_MS, "webhook"))
    ring_answers(online=True)
    _, body = call("GET", "/api/camera", token=tokens["owner"])
    assert [h["source"] for h in body["history"]] == ["webhook", "webhook"]
    assert body["uptime"]["percent"] == 99.2
    assert body["uptime"]["since"] == "2026-07-07T07:06:40.000Z"
