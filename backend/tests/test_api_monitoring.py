"""fridge-monitoring: PUT /api/camera/monitoring."""

import pytest

from fridgesense import monitoring
from fridgesense.devices import Device, DeviceRepository
from fridgesense.handlers import api
from fridgesense.store import load_app_config
from fridgesense.table import FridgeTable
from tests.api_helpers import ACCOUNT, call, configure, link_account, sign_in

DEVICE = "ava1.ring.device.D1"
PAUSED_AT = 1792332300.0  # 2026-10-18T14:05:00Z
RESUMED_AT = 1792341000.0  # 2026-10-18T16:30:00Z
PATH = "/api/camera/monitoring"


@pytest.fixture
def clock(monkeypatch):
    at = {"now": PAUSED_AT}
    monkeypatch.setattr(api, "now", lambda: at["now"])
    return at


@pytest.fixture
def tokens(aws, clock):
    link_account()
    configure(demo_passcode="look-only", user_passcode="come-in")
    load_app_config(refresh=True)
    DeviceRepository().replace(ACCOUNT, [Device(DEVICE, "Fridge")])
    return {"owner": sign_in(), "user": sign_in("come-in"), "viewer": sign_in("look-only")}


def stored():
    return monitoring.load(FridgeTable(), ACCOUNT, DEVICE).to_body()


# Scenario: Pause
def test_pause(tokens):
    assert call("PUT", PATH, {"paused": True}, token=tokens["owner"]) == (
        200,
        {"paused": True, "since": "2026-10-18T14:05:00.000Z"},
    )
    assert stored() == {"paused": True, "since": "2026-10-18T14:05:00.000Z"}


# Scenario: Resume
def test_resume(tokens, clock):
    call("PUT", PATH, {"paused": True}, token=tokens["owner"])
    clock["now"] = RESUMED_AT
    assert call("PUT", PATH, {"paused": False}, token=tokens["owner"]) == (
        200,
        {"paused": False, "since": "2026-10-18T16:30:00.000Z"},
    )


# Scenario: Pause twice
def test_pause_twice(tokens, clock):
    call("PUT", PATH, {"paused": True}, token=tokens["owner"])
    clock["now"] = PAUSED_AT + 3300
    status, body = call("PUT", PATH, {"paused": True}, token=tokens["owner"])
    assert status == 200 and body["since"] == "2026-10-18T14:05:00.000Z"


# Scenario: Bad body
@pytest.mark.parametrize("body", [{"paused": "yes"}, {}, {"paused": 1}])
def test_bad_body(tokens, body):
    assert call("PUT", PATH, body, token=tokens["owner"]) == (
        400,
        {"error": "paused must be true or false"},
    )
    assert stored() == {"paused": False, "since": None}


def test_body_not_json(tokens):
    from tests.conftest import api_event

    headers = {"content-type": "application/json", "Authorization": f"Bearer {tokens['owner']}"}
    resp = api.handler(api_event("PUT", PATH, "not json", headers, None), None)
    assert resp["statusCode"] == 400
    assert stored() == {"paused": False, "since": None}


# Scenario: Viewer cannot pause
def test_viewer_cannot_pause(tokens):
    assert call("PUT", PATH, {"paused": True}, token=tokens["viewer"]) == (
        403,
        {"error": "read-only"},
    )
    assert stored()["paused"] is False


# Scenario: User role can pause
def test_user_role_can_pause(tokens):
    status, body = call("PUT", PATH, {"paused": True}, token=tokens["user"])
    assert status == 200 and body["paused"] is True


# Scenario: No token
def test_no_token(tokens):
    assert call("PUT", PATH, {"paused": True}) == (401, {"error": "sign in"})


# Scenario: No camera
def test_no_camera(tokens):
    DeviceRepository().replace(ACCOUNT, [])
    assert call("PUT", PATH, {"paused": True}, token=tokens["owner"]) == (
        409,
        {"error": "no camera found"},
    )
