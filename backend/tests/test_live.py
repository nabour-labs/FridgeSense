"""camera-live-view: WHEP sessions at Ring for the live view."""

import httpx
import pytest
import respx

from fridgesense import live
from fridgesense.oauth import OAUTH_URL, OAuthClient
from fridgesense.ring import API_BASE, RingClient
from fridgesense.store import Tokens
from tests.conftest import MemoryTokenStore, load_fixture

NOW = 1_792_092_010
DEVICE = "ava1.ring.device.D1"
SESSIONS = f"{API_BASE}/v1/devices/{DEVICE}/media/streaming/whep/sessions"
OFFER = "v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\n"
ANSWER = "v=0\r\nanswer\r\n"


@pytest.fixture
def http():
    with httpx.Client() as c:
        yield c


def ring(http, expires_in: int = 3600) -> RingClient:
    tokens = Tokens(
        account_id="ava1.ring.account.A1",
        access_token="at1",
        refresh_token="rt1",
        expires_at=NOW + expires_in,
        link_status="linked",
    )
    return RingClient(
        http, MemoryTokenStore(tokens), OAuthClient(http, "cid", "cs"), now=lambda: NOW
    )


# RingClient extra headers


@respx.mock
def test_caller_headers_are_sent(http):
    route = respx.post(f"{API_BASE}/v1/x").respond(200)
    ring(http).post("/v1/x", content=b"a", headers={"Content-Type": "application/sdp"})
    sent = route.calls.last.request
    assert sent.headers["content-type"] == "application/sdp"
    assert sent.headers["authorization"] == "Bearer at1"


@respx.mock
def test_caller_cannot_override_authorization(http):
    route = respx.get(f"{API_BASE}/v1/x").respond(200)
    ring(http).get("/v1/x", headers={"Authorization": "Bearer other"})
    assert route.calls.last.request.headers["authorization"] == "Bearer at1"


# Scenario: Live view opened


@respx.mock
def test_live_view_opened(http):
    route = respx.post(SESSIONS).respond(
        201,
        text=ANSWER,
        headers={"Location": f"/v1/devices/{DEVICE}/media/streaming/whep/sessions/S1"},
    )
    assert live.start(ring(http), DEVICE, OFFER) == (ANSWER, "S1")
    sent = route.calls.last.request
    assert sent.content.decode() == OFFER
    assert sent.headers["content-type"] == "application/sdp"
    assert sent.headers["authorization"] == "Bearer at1"


# Scenario: Absolute Location


@respx.mock
def test_absolute_location(http):
    respx.post(SESSIONS).respond(201, text=ANSWER, headers={"Location": f"{SESSIONS}/S9"})
    assert live.start(ring(http), DEVICE, OFFER) == (ANSWER, "S9")


# Scenario: Ring refuses the session


@pytest.mark.parametrize("status", [400, 403, 404, 429, 500])
@respx.mock
def test_ring_refuses_the_session(http, status):
    respx.post(SESSIONS).respond(status, text="nope")
    with pytest.raises(live.LiveFailed):
        live.start(ring(http), DEVICE, OFFER)


@respx.mock
def test_answer_without_location_fails(http):
    respx.post(SESSIONS).respond(201, text=ANSWER)
    with pytest.raises(live.LiveFailed):
        live.start(ring(http), DEVICE, OFFER)


# Scenario: Ring unreachable or unlinked


@respx.mock
def test_ring_timeout(http):
    respx.post(SESSIONS).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(live.LiveFailed):
        live.start(ring(http), DEVICE, OFFER)


@respx.mock
def test_ring_401_after_refresh(http):
    respx.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_refresh.json"))
    respx.post(SESSIONS).respond(401)
    with pytest.raises(live.LiveFailed):
        live.start(ring(http), DEVICE, OFFER)


@respx.mock
def test_nothing_linked(http):
    client = RingClient(http, MemoryTokenStore(None), OAuthClient(http, "c", "s"), now=lambda: NOW)
    with pytest.raises(live.LiveFailed):
        live.start(client, DEVICE, OFFER)


# Scenario: Live view closed


@pytest.mark.parametrize("status", [200, 204])
@respx.mock
def test_live_view_closed(http, status):
    route = respx.delete(f"{SESSIONS}/S123").respond(status)
    live.stop(ring(http), DEVICE, "S123")
    assert route.calls.last.request.headers["authorization"] == "Bearer at1"


# Scenario: Session already gone


@respx.mock
def test_session_already_gone(http):
    respx.delete(f"{SESSIONS}/S123").respond(404)
    live.stop(ring(http), DEVICE, "S123")


# Scenario: Ring fails the delete


@respx.mock
def test_ring_fails_the_delete(http):
    respx.delete(f"{SESSIONS}/S123").respond(500)
    with pytest.raises(live.LiveFailed):
        live.stop(ring(http), DEVICE, "S123")


@respx.mock
def test_delete_timeout(http):
    respx.delete(f"{SESSIONS}/S123").mock(side_effect=httpx.ConnectTimeout("slow"))
    with pytest.raises(live.LiveFailed):
        live.stop(ring(http), DEVICE, "S123")
