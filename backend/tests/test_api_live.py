"""camera-live-view: the live view routes on the app API."""

import json

import httpx
import pytest
import respx

from fridgesense.devices import Device, DeviceRepository
from fridgesense.handlers import api
from fridgesense.ring import API_BASE
from fridgesense.store import load_app_config
from tests.api_helpers import ACCOUNT, NOW, call, configure, link_account, sign_in
from tests.conftest import api_event

DEVICE = "ava1.ring.device.D1"
SESSIONS = f"{API_BASE}/v1/devices/{DEVICE}/media/streaming/whep/sessions"
OFFER = "v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\n"
ANSWER = "v=0\r\nanswer\r\n"
UNAVAILABLE = (502, {"error": "camera unavailable"})


@pytest.fixture
def tokens(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    link_account()
    configure(demo_passcode="look-only", user_passcode="family")
    load_app_config(refresh=True)
    DeviceRepository().replace(ACCOUNT, [Device(DEVICE, "Fridge")])
    return {"owner": sign_in(), "user": sign_in("family"), "viewer": sign_in("look-only")}


def opened(location=f"/v1/devices/{DEVICE}/media/streaming/whep/sessions/S123"):
    return respx.post(SESSIONS).respond(201, text=ANSWER, headers={"Location": location})


# Scenario: Live view opened
@respx.mock
def test_live_view_opened(tokens):
    route = opened()
    assert call("POST", "/api/camera/live", {"offer": OFFER}, tokens["owner"]) == (
        200,
        {"answer": ANSWER, "session_id": "S123", "max_seconds": 60},
    )
    sent = route.calls.last.request
    assert sent.content.decode() == OFFER
    assert sent.headers["content-type"] == "application/sdp"
    assert sent.headers["authorization"] == "Bearer at1"


# Scenario: User opens a live view
@respx.mock
def test_user_opens_a_live_view(tokens):
    route = opened()
    assert call("POST", "/api/camera/live", {"offer": OFFER}, tokens["user"]) == (
        403,
        {"error": "admin only"},
    )
    assert not route.called


# Scenario: Viewer opens a live view
@respx.mock
def test_viewer_opens_a_live_view(tokens):
    route = opened()
    assert call("POST", "/api/camera/live", {"offer": OFFER}, tokens["viewer"]) == (
        403,
        {"error": "read-only"},
    )
    assert not route.called


# Scenario: Bad offer
@pytest.mark.parametrize(
    "body",
    [{}, {"offer": 5}, {"offer": ""}, {"offer": "hello"}, {"offer": "v=0" + "a" * 20_000}, ["v=0"]],
)
@respx.mock
def test_bad_offer(tokens, body):
    route = opened()
    assert call("POST", "/api/camera/live", body, tokens["owner"]) == (400, {"error": "bad offer"})
    assert not route.called


@respx.mock
def test_offer_not_json(tokens):
    route = opened()
    headers = {"content-type": "application/json", "Authorization": f"Bearer {tokens['owner']}"}
    resp = api.handler(api_event("POST", "/api/camera/live", "v=0 not json", headers), None)
    assert (resp["statusCode"], json.loads(resp["body"])) == (400, {"error": "bad offer"})
    assert not route.called


# Scenario: No camera
@respx.mock
def test_no_camera(tokens):
    DeviceRepository().replace(ACCOUNT, [])
    route = opened()
    assert call("POST", "/api/camera/live", {"offer": OFFER}, tokens["owner"]) == (
        409,
        {"error": "no camera found"},
    )
    assert not route.called


# Scenario: Ring refuses the session
@pytest.mark.parametrize("status", [400, 403, 404, 429, 500])
@respx.mock
def test_ring_refuses_the_session(tokens, status):
    respx.post(SESSIONS).respond(status, text="nope")
    assert call("POST", "/api/camera/live", {"offer": OFFER}, tokens["owner"]) == UNAVAILABLE


@respx.mock
def test_ring_answer_without_location(tokens):
    respx.post(SESSIONS).respond(201, text=ANSWER)
    assert call("POST", "/api/camera/live", {"offer": OFFER}, tokens["owner"]) == UNAVAILABLE


# Scenario: Ring unreachable or unlinked
@respx.mock
def test_ring_unreachable(tokens):
    respx.post(SESSIONS).mock(side_effect=httpx.ReadTimeout("slow"))
    assert call("POST", "/api/camera/live", {"offer": OFFER}, tokens["owner"]) == UNAVAILABLE


# Scenario: Not signed in
@respx.mock
def test_not_signed_in(tokens):
    route = opened()
    assert call("POST", "/api/camera/live", {"offer": OFFER}) == (401, {"error": "sign in"})
    assert not route.called


# Scenario: Live view closed
@pytest.mark.parametrize("status", [200, 204])
@respx.mock
def test_live_view_closed(tokens, status):
    route = respx.delete(f"{SESSIONS}/S123").respond(status)
    assert call("DELETE", "/api/camera/live/S123", token=tokens["owner"]) == (200, {"ok": True})
    assert route.called


# Scenario: User refused a close
@respx.mock
def test_user_refused_a_close(tokens):
    route = respx.delete(f"{SESSIONS}/S123").respond(204)
    assert call("DELETE", "/api/camera/live/S123", token=tokens["user"]) == (
        403,
        {"error": "admin only"},
    )
    assert not route.called


# Scenario: Viewer refused a close
@respx.mock
def test_viewer_refused_a_close(tokens):
    route = respx.delete(f"{SESSIONS}/S123").respond(204)
    assert call("DELETE", "/api/camera/live/S123", token=tokens["viewer"]) == (
        403,
        {"error": "read-only"},
    )
    assert not route.called


# Scenario: Session already gone
@respx.mock
def test_session_already_gone(tokens):
    respx.delete(f"{SESSIONS}/S123").respond(404)
    assert call("DELETE", "/api/camera/live/S123", token=tokens["owner"]) == (200, {"ok": True})


# Scenario: Bad session id
@pytest.mark.parametrize("session_id", ["..%2F..%2Fdevices", "a" * 129, "S1%3Fx"])
@respx.mock
def test_bad_session_id(tokens, session_id):
    route = respx.route(host="api.amazonvision.com").respond(200)
    assert call("DELETE", f"/api/camera/live/{session_id}", token=tokens["owner"]) == (
        404,
        {"error": "not found"},
    )
    assert not route.called


# Scenario: Ring fails the delete
@respx.mock
def test_ring_fails_the_delete(tokens):
    respx.delete(f"{SESSIONS}/S123").respond(500)
    assert call("DELETE", "/api/camera/live/S123", token=tokens["owner"]) == UNAVAILABLE


@respx.mock
def test_delete_times_out(tokens):
    respx.delete(f"{SESSIONS}/S123").mock(side_effect=httpx.ConnectTimeout("slow"))
    assert call("DELETE", "/api/camera/live/S123", token=tokens["owner"]) == UNAVAILABLE
