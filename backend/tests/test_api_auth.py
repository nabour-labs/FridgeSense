"""inventory-api: sign-in, auth gating and routing."""

import pytest

from fridgesense.handlers import api
from fridgesense.store import load_app_config
from tests.api_helpers import NOW, call, configure, link_account, sign_in


@pytest.fixture
def app(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    link_account()


def fresh_config():
    load_app_config(refresh=True)


# Correct passcode
def test_correct_passcode(app):
    status, body = call("POST", "/api/session", {"passcode": "open-sesame"})
    assert status == 200
    assert body["token"]
    assert body["role"] == "owner"
    assert body["expires_at"] == "2026-09-05T07:06:40.000Z"  # NOW + 30 days


# Demo passcode
def test_demo_passcode(app):
    configure(demo_passcode="look-only")
    fresh_config()
    status, body = call("POST", "/api/session", {"passcode": "look-only"})
    assert status == 200 and body["role"] == "viewer" and body["token"]


# No demo passcode configured
@pytest.mark.parametrize("passcode", ["", "look-only"])
def test_no_demo_passcode_configured(app, passcode):
    assert call("POST", "/api/session", {"passcode": passcode}) == (
        401,
        {"error": "wrong passcode"},
    )


# Wrong passcode
@pytest.mark.parametrize("body", [{"passcode": "guess"}, {}, None])
def test_wrong_passcode(app, body):
    assert call("POST", "/api/session", body) == (401, {"error": "wrong passcode"})


# Passcode changed
def test_passcode_changed(app):
    token = sign_in()
    configure(passcode="new-pass")
    fresh_config()
    assert call("GET", "/api/inventory", token=token)[0] == 401


# Demo passcode changed
def test_demo_passcode_changed(app):
    configure(demo_passcode="look-only")
    fresh_config()
    viewer, owner = sign_in("look-only"), sign_in()
    configure(demo_passcode="other")
    fresh_config()
    assert call("GET", "/api/inventory", token=viewer)[0] == 401
    assert call("GET", "/api/inventory", token=owner)[0] == 200


# No token
def test_no_token(app):
    assert call("GET", "/api/inventory") == (401, {"error": "sign in"})


# Tampered or expired token
def test_tampered_or_expired_token(app, monkeypatch):
    token = sign_in()
    assert (
        call("GET", "/api/inventory", token=token[:-1] + ("0" if token[-1] != "0" else "1"))[0]
        == 401
    )
    monkeypatch.setattr(api, "now", lambda: NOW + 31 * 24 * 3600)
    assert call("GET", "/api/inventory", token=token)[0] == 401


# Unknown route
def test_unknown_route(app):
    assert call("GET", "/api/nope", token=sign_in())[0] == 404


# No linked Ring account
def test_no_linked_ring_account(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    token = sign_in()
    assert call("GET", "/api/inventory", token=token) == (409, {"error": "no camera linked"})
