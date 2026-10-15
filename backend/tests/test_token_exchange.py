"""ring-account-link: Token exchange stores tokens as unclaimed."""

import json
import logging

import pytest
import respx

from fridgesense.handlers import http
from fridgesense.oauth import OAUTH_URL
from fridgesense.ring import API_BASE
from fridgesense.store import TokenStore
from tests.conftest import api_event, load_fixture

NOW = 1_771_131_000.0


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(http, "now", lambda: NOW)


@pytest.fixture
def ring_ok():
    with respx.mock(assert_all_called=False) as mock:
        mock.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_token.json"))
        mock.get(f"{API_BASE}/v1/users/me").respond(200, json=load_fixture("ring/users_me.json"))
        yield mock


def call(event):
    return http.handler(event, None)


JSON = {"content-type": "application/json"}
FORM = {"content-type": "application/x-www-form-urlencoded"}


# Valid authorization code
def test_valid_authorization_code(aws, ring_ok):
    resp = call(api_event("POST", "/ring/token", json.dumps({"code": "abc123"}), JSON))
    assert resp["statusCode"] == 200
    tokens = TokenStore().load()
    assert tokens.model_dump() == {
        "account_id": "ava1.ring.account.A1",
        "access_token": "at1",
        "refresh_token": "rt1",
        "expires_at": int(NOW) + 14400,
        "link_status": "unclaimed",
    }
    me = ring_ok.calls[-1].request
    assert me.headers["authorization"] == "Bearer at1"


# Code sent as a form field or query parameter
@pytest.mark.parametrize(
    "event",
    [
        api_event("POST", "/ring/token", "code=abc123", FORM),
        api_event("POST", "/ring/token", "code=abc123", FORM, base64=True),
        api_event("POST", "/ring/token", query={"code": "abc123"}),
    ],
    ids=["form", "form-base64", "query"],
)
def test_code_as_form_or_query(aws, ring_ok, event):
    assert call(event)["statusCode"] == 200
    assert b"code=abc123" in ring_ok.calls[0].request.content
    assert TokenStore().load().link_status == "unclaimed"


# Missing code
def test_missing_code(aws):
    with respx.mock(assert_all_called=False) as mock:
        oauth = mock.post(OAUTH_URL)
        resp = call(api_event("POST", "/ring/token", json.dumps({"state": "x"}), JSON))
    assert resp["statusCode"] == 400
    assert not oauth.called


# Ring rejects the code
def test_ring_rejects_the_code(aws, caplog):
    caplog.set_level(logging.INFO)
    with respx.mock() as mock:
        mock.post(OAUTH_URL).respond(400, json={"error": "invalid_grant"})
        resp = call(api_event("POST", "/ring/token", json.dumps({"code": "abc123"}), JSON))
    assert resp["statusCode"] == 502
    assert TokenStore().load() is None
    logs = " ".join(r.getMessage() for r in caplog.records)
    assert "abc123" not in logs and "csecret" not in logs


def test_users_me_fails(aws):
    with respx.mock() as mock:
        mock.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_token.json"))
        mock.get(f"{API_BASE}/v1/users/me").respond(500)
        resp = call(api_event("POST", "/ring/token", json.dumps({"code": "abc123"}), JSON))
    assert resp["statusCode"] == 502
    assert TokenStore().load() is None


# Secrets never logged
def test_secrets_never_logged(aws, ring_ok, caplog):
    caplog.set_level(logging.DEBUG)
    call(api_event("POST", "/ring/token", json.dumps({"code": "abc123"}), JSON))
    logs = " ".join(r.getMessage() for r in caplog.records)
    for secret in ["abc123", "csecret", "at1", "rt1"]:
        assert secret not in logs
    assert "ava1.ring.account.A1" in logs
    assert "code" in logs  # field names are logged so the real request shape shows up


def test_unknown_route_is_404(aws):
    assert call(api_event("GET", "/nope"))["statusCode"] == 404
