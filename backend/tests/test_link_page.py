"""ring-account-link: link page, passcode, nonce and app integration."""

import json
from urllib.parse import urlencode

import pytest
import respx

from fridgesense.crypto import nonce_for
from fridgesense.handlers import http
from fridgesense.ring import API_BASE
from fridgesense.store import Tokens, TokenStore
from tests.conftest import APP_CONFIG, api_event, load_fixture

NOW = 1_771_131_000.0
NOW_MS = int(NOW * 1000)
ACCOUNT = "ava1.ring.account.A1"
KEY = APP_CONFIG["hmac_key"]
INTEGRATIONS = f"{API_BASE}/v1/accounts/me/app-integrations"
UNCLAIMED = Tokens(
    account_id=ACCOUNT,
    access_token="at1",
    refresh_token="rt1",
    expires_at=int(NOW) + 3600,
    link_status="unclaimed",
)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(http, "now", lambda: NOW)


@pytest.fixture
def unclaimed(aws):
    TokenStore().save(UNCLAIMED)


@pytest.fixture
def ring():
    with respx.mock(assert_all_called=False) as mock:
        mock.post(INTEGRATIONS).respond(201, json={"status": "awaiting"})
        mock.patch(INTEGRATIONS).respond(200, json=load_fixture("ring/app_integrations_patch.json"))
        mock.get(f"{API_BASE}/v1/devices").respond(200, json=load_fixture("ring/devices.json"))
        yield mock


def submit(passcode="open-sesame", time_ms=NOW_MS - 60_000, nonce=None, account=ACCOUNT):
    nonce = nonce if nonce is not None else nonce_for(KEY, str(time_ms), account)
    body = urlencode({"passcode": passcode, "time": str(time_ms), "nonce": nonce})
    event = api_event(
        "POST", "/ring/link", body, {"content-type": "application/x-www-form-urlencoded"}
    )
    return http.handler(event, None)


def ring_calls(mock):
    return [c for c in mock.calls if c.request.url.host == "api.amazonvision.com"]


# Ring opens the link page
def test_ring_opens_the_link_page(aws, ring):
    resp = http.handler(
        api_event("GET", "/ring/link", query={"nonce": "N1", "time": "1771130906289"}), None
    )
    assert resp["statusCode"] == 200
    assert resp["headers"]["content-type"].startswith("text/html")
    page = resp["body"]
    assert 'type="password"' in page and 'name="passcode"' in page
    assert 'name="nonce" value="N1"' in page
    assert 'name="time" value="1771130906289"' in page
    assert not ring.calls


def test_link_page_escapes_parameters(aws):
    resp = http.handler(
        api_event("GET", "/ring/link", query={"nonce": '"><script>', "time": "1"}), None
    )
    assert "<script>" not in resp["body"]


# Link page opened without Ring parameters
@pytest.mark.parametrize("query", [None, {"nonce": "N1"}, {"time": "1771130906289"}])
def test_link_page_without_ring_parameters(aws, query):
    resp = http.handler(api_event("GET", "/ring/link", query=query), None)
    assert resp["statusCode"] == 400
    assert "Ring app" in resp["body"]


# Wrong passcode
def test_wrong_passcode(unclaimed, ring):
    resp = submit(passcode="guess")
    assert resp["statusCode"] == 401
    assert 'name="passcode"' in resp["body"]
    assert "passcode" in resp["body"].lower() and "incorrect" in resp["body"].lower()
    assert not ring_calls(ring)
    assert TokenStore().load().link_status == "unclaimed"


def test_empty_configured_passcode_never_matches(unclaimed, ring):
    import boto3

    boto3.client("secretsmanager").put_secret_value(
        SecretId="fridgesense/ring-app", SecretString=json.dumps({**APP_CONFIG, "passcode": ""})
    )
    assert submit(passcode="")["statusCode"] == 401
    assert not ring_calls(ring)


# Stale link request
def test_stale_link_request(unclaimed, ring):
    resp = submit(time_ms=NOW_MS - 601_000)
    assert resp["statusCode"] == 400
    assert "expired" in resp["body"].lower()
    assert not ring_calls(ring)


# Time in the future
def test_time_in_the_future(unclaimed, ring):
    assert submit(time_ms=NOW_MS + 1000)["statusCode"] == 400
    assert not ring_calls(ring)


# Nonce does not match
def test_nonce_does_not_match(unclaimed, ring):
    resp = submit(nonce=nonce_for(KEY, str(NOW_MS - 60_000), "ava1.ring.account.OTHER"))
    assert resp["statusCode"] == 400
    assert not ring_calls(ring)
    assert TokenStore().load().link_status == "unclaimed"


# No unclaimed account
@pytest.mark.parametrize("status", [None, "linked", "needs_relink"])
def test_no_unclaimed_account(aws, ring, status):
    if status:
        TokenStore().save(UNCLAIMED.model_copy(update={"link_status": status}))
    assert submit()["statusCode"] == 400
    assert not ring_calls(ring)


# Successful link
def test_successful_link(unclaimed, ring):
    nonce = nonce_for(KEY, str(NOW_MS - 60_000), ACCOUNT)
    resp = submit(nonce=nonce)
    assert resp["statusCode"] == 200
    assert "linked" in resp["body"].lower()
    assert TokenStore().load().link_status == "linked"
    post = ring.routes[0].calls.last.request
    patch = ring.routes[1].calls.last.request
    assert post.headers["authorization"] == "Bearer at1"
    assert json.loads(post.content) == {
        "account_identifier": "o***r@fridgesense.app",
        "nonce": nonce,
    }
    assert json.loads(patch.content) == {"status": "completed"}
    assert patch.headers["authorization"] == "Bearer at1"


# App URL configured
def test_app_url_configured(unclaimed, ring, monkeypatch):
    monkeypatch.setenv("APP_URL", "https://d111.cloudfront.net")
    resp = submit()
    assert resp["statusCode"] == 200
    link = '<a class="button" href="https://d111.cloudfront.net">Open FridgeSense</a>'
    assert link in resp["body"]


# App URL not configured
def test_app_url_not_configured(unclaimed, ring, monkeypatch):
    monkeypatch.delenv("APP_URL", raising=False)
    resp = submit()
    assert resp["statusCode"] == 200
    assert "linked" in resp["body"].lower()
    assert "Open FridgeSense" not in resp["body"]


# Ring rejects the integration
@pytest.mark.parametrize("step,status", [("post", 400), ("post", 404), ("patch", 400)])
def test_ring_rejects_the_integration(unclaimed, step, status):
    with respx.mock(assert_all_called=False) as mock:
        mock.post(INTEGRATIONS).respond(status if step == "post" else 201, json={})
        mock.patch(INTEGRATIONS).respond(status if step == "patch" else 200, json={})
        resp = submit()
    assert resp["statusCode"] == 502
    assert "failed" in resp["body"].lower()
    assert TokenStore().load().link_status == "unclaimed"
