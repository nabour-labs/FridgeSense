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
    assert body["expires_at"] == "2026-08-07T07:06:40.000Z"  # NOW + 24 hours


# Demo passcode
def test_demo_passcode(app):
    configure(demo_passcode="look-only")
    fresh_config()
    status, body = call("POST", "/api/session", {"passcode": "look-only"})
    assert status == 200 and body["role"] == "viewer" and body["token"]
    assert body["expires_at"] == "2026-08-07T07:06:40.000Z"  # NOW + 24 hours


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


# Token one day old
def test_token_one_day_old(app, monkeypatch):
    token = sign_in()
    monkeypatch.setattr(api, "now", lambda: NOW + 24 * 3600)
    assert call("GET", "/api/inventory", token=token)[0] == 200
    monkeypatch.setattr(api, "now", lambda: NOW + 24 * 3600 + 1)
    assert call("GET", "/api/inventory", token=token) == (401, {"error": "sign in"})


@pytest.fixture
def with_user(app):
    configure(user_passcode="come-in")
    fresh_config()


# User passcode
def test_user_passcode(with_user):
    status, body = call("POST", "/api/session", {"passcode": "come-in"})
    assert status == 200 and body["role"] == "user" and body["token"]
    assert body["expires_at"] == "2026-08-07T07:06:40.000Z"  # NOW + 24 hours


# No user passcode configured
def test_no_user_passcode_configured(app):
    assert call("POST", "/api/session", {"passcode": "come-in"}) == (
        401,
        {"error": "wrong passcode"},
    )


# Equal passcodes
def test_equal_passcodes(app):
    configure(user_passcode="come-in", demo_passcode="come-in")
    fresh_config()
    assert call("POST", "/api/session", {"passcode": "come-in"})[1]["role"] == "user"


# User passcode changed
def test_user_passcode_changed(with_user):
    user, owner = sign_in("come-in"), sign_in()
    configure(user_passcode="other")
    fresh_config()
    assert call("GET", "/api/inventory", token=user)[0] == 401
    assert call("GET", "/api/inventory", token=owner)[0] == 200


# User writes
def test_user_writes(with_user):
    user = sign_in("come-in")
    added = {"name": "Milk", "category": "dairy", "quantity": 1}
    assert call("POST", "/api/items", added, token=user)[0] == 200
    assert call("PUT", "/api/items/milk", {"quantity": 2}, token=user)[0] == 200
    status, body = call("GET", "/api/inventory", token=user)
    assert status == 200
    assert [(i["key"], i["quantity"]) for i in body["items"]] == [("milk", 2)]


# User refused debug traces
@pytest.mark.parametrize("path", ["/api/debug/motions", "/api/debug/motions/abc"])
def test_user_refused_debug_traces(with_user, path):
    user = sign_in("come-in")
    assert call("GET", path, token=user) == (403, {"error": "admin only"})
