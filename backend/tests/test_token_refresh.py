"""ring-token-lifecycle: Scheduled token refresh."""

import json
import logging
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from fridgesense.handlers import token_refresh
from fridgesense.oauth import OAUTH_URL, OAuthClient, OAuthUnavailable
from fridgesense.store import Tokens, TokenStore
from tests.conftest import MemoryTokenStore, load_fixture

NOW = 1_771_131_000
OLD = Tokens(
    account_id="ava1.ring.account.A1",
    access_token="at1",
    refresh_token="rt1",
    expires_at=NOW + 3600,
    link_status="linked",
)


@pytest.fixture
def oauth():
    with httpx.Client() as http:
        yield OAuthClient(http, "cid", "csecret")


def run(store, oauth):
    return token_refresh.run_refresh(store, oauth, now=lambda: NOW)


# Refresh succeeds and rotates the refresh token
@respx.mock
def test_refresh_rotates_tokens(oauth):
    route = respx.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_refresh.json"))
    store = MemoryTokenStore(OLD)
    assert run(store, oauth) == "refreshed"
    assert store.tokens == OLD.model_copy(
        update={"access_token": "at2", "refresh_token": "rt2", "expires_at": NOW + 14400}
    )
    body = parse_qs(route.calls.last.request.content.decode())
    assert body["grant_type"] == ["refresh_token"]
    assert body["refresh_token"] == ["rt1"]
    assert body["client_id"] == ["cid"]
    assert body["client_secret"] == ["csecret"]


@respx.mock
def test_unclaimed_account_is_refreshed_too(oauth):
    respx.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_refresh.json"))
    store = MemoryTokenStore(OLD.model_copy(update={"link_status": "unclaimed"}))
    assert run(store, oauth) == "refreshed"
    assert store.tokens.link_status == "unclaimed"


# Refresh response without a new refresh token
@respx.mock
def test_refresh_without_new_refresh_token_keeps_old_one(oauth):
    respx.post(OAUTH_URL).respond(200, json={"access_token": "at2", "expires_in": 14400})
    store = MemoryTokenStore(OLD)
    run(store, oauth)
    assert store.tokens.refresh_token == "rt1"
    assert store.tokens.access_token == "at2"
    assert store.tokens.expires_at == NOW + 14400


# Nothing to refresh
@respx.mock
def test_nothing_to_refresh(oauth):
    route = respx.post(OAUTH_URL)
    assert run(MemoryTokenStore(None), oauth) == "nothing_to_refresh"
    assert not route.called


@respx.mock
def test_account_needing_relink_is_skipped(oauth):
    route = respx.post(OAUTH_URL)
    store = MemoryTokenStore(OLD.model_copy(update={"link_status": "needs_relink"}))
    assert run(store, oauth) == "needs_relink"
    assert not route.called


# Refresh token rejected
@respx.mock
@pytest.mark.parametrize("status", [400, 401])
def test_refresh_token_rejected(oauth, caplog, status):
    caplog.set_level(logging.INFO)
    respx.post(OAUTH_URL).respond(status, json={"error": "invalid_grant"})
    store = MemoryTokenStore(OLD)
    assert run(store, oauth) == "needs_relink"
    assert store.tokens == OLD.model_copy(update={"link_status": "needs_relink"})
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors and "ava1.ring.account.A1" in errors[-1].getMessage()
    assert all("rt1" not in r.getMessage() and "at1" not in r.getMessage() for r in caplog.records)


# Refresh rejected after another caller already refreshed
@respx.mock
def test_refresh_rejected_after_another_caller_refreshed(oauth, caplog):
    caplog.set_level(logging.INFO)
    newer = OLD.model_copy(
        update={"access_token": "at2", "refresh_token": "rt2", "expires_at": NOW + 14400}
    )
    store = MemoryTokenStore(OLD)

    def rotated_elsewhere(request):
        store.tokens = newer  # another caller used rt1 first and stored its result
        return httpx.Response(400, json={"error": "invalid_grant"})

    respx.post(OAUTH_URL).mock(side_effect=rotated_elsewhere)
    assert run(store, oauth) == "already_refreshed"
    assert store.tokens == newer
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert all("rt1" not in r.getMessage() and "rt2" not in r.getMessage() for r in caplog.records)


# Refresh rejected and nobody else refreshed
@respx.mock
def test_refresh_rejected_and_nobody_else_refreshed(oauth):
    respx.post(OAUTH_URL).respond(400, json={"error": "invalid_grant"})
    store = MemoryTokenStore(OLD)
    assert run(store, oauth) == "needs_relink"
    assert store.tokens == OLD.model_copy(update={"link_status": "needs_relink"})


# OAuth endpoint unavailable
@respx.mock
@pytest.mark.parametrize(
    "mock", [{"return_value": httpx.Response(503)}, {"side_effect": httpx.ReadTimeout("slow")}]
)
def test_oauth_unavailable(oauth, mock):
    respx.post(OAUTH_URL).mock(**mock)
    store = MemoryTokenStore(OLD)
    with pytest.raises(OAuthUnavailable):
        run(store, oauth)
    assert store.tokens == OLD
    assert store.saves == 0


@respx.mock
def test_lambda_handler_uses_secrets_manager(aws):
    respx.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_refresh.json"))
    TokenStore().save(OLD)
    assert token_refresh.handler({}, None) == {"result": "refreshed"}
    assert json.loads(TokenStore().load().model_dump_json())["access_token"] == "at2"
