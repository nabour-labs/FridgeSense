"""Contract tests for Ring's OAuth token endpoint."""

from urllib.parse import parse_qs

import httpx
import pytest
import respx

from fridgesense.oauth import OAUTH_URL, OAuthClient, OAuthRejected, OAuthUnavailable
from tests.conftest import load_fixture


@pytest.fixture
def oauth():
    with httpx.Client() as http:
        yield OAuthClient(http, client_id="cid", client_secret="csecret")


def form(request: httpx.Request) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}


@respx.mock
def test_exchange_code_posts_authorization_code_grant(oauth):
    route = respx.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_token.json"))
    tokens = oauth.exchange_code("abc123")
    req = route.calls.last.request
    assert OAUTH_URL == "https://oauth.ring.com/oauth/token"
    assert req.headers["content-type"] == "application/x-www-form-urlencoded"
    assert form(req) == {
        "grant_type": "authorization_code",
        "code": "abc123",
        "client_id": "cid",
        "client_secret": "csecret",
    }
    assert (tokens.access_token, tokens.refresh_token, tokens.expires_in) == ("at1", "rt1", 14400)


@respx.mock
def test_refresh_posts_refresh_token_grant(oauth):
    route = respx.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_refresh.json"))
    tokens = oauth.refresh("rt1")
    assert form(route.calls.last.request) == {
        "grant_type": "refresh_token",
        "refresh_token": "rt1",
        "client_id": "cid",
        "client_secret": "csecret",
    }
    assert (tokens.access_token, tokens.refresh_token) == ("at2", "rt2")


@respx.mock
def test_refresh_without_new_refresh_token(oauth):
    respx.post(OAUTH_URL).respond(200, json={"access_token": "at2", "expires_in": 14400})
    assert oauth.refresh("rt1").refresh_token is None


@respx.mock
@pytest.mark.parametrize("status", [400, 401])
def test_rejected_grant_raises_rejected(oauth, status):
    respx.post(OAUTH_URL).respond(status, json={"error": "invalid_grant"})
    with pytest.raises(OAuthRejected):
        oauth.refresh("rt1")


@respx.mock
def test_server_error_raises_unavailable(oauth):
    respx.post(OAUTH_URL).respond(503)
    with pytest.raises(OAuthUnavailable):
        oauth.refresh("rt1")


@respx.mock
def test_timeout_raises_unavailable(oauth):
    respx.post(OAUTH_URL).mock(side_effect=httpx.ConnectTimeout("slow"))
    with pytest.raises(OAuthUnavailable):
        oauth.exchange_code("abc123")
