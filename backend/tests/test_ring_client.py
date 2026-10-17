"""ring-token-lifecycle: Valid token for every Ring API call."""

import threading

import httpx
import pytest
import respx

from fridgesense.oauth import OAUTH_URL, OAuthClient
from fridgesense.ring import API_BASE, RingAuthError, RingClient
from fridgesense.store import Tokens
from tests.conftest import MemoryTokenStore, load_fixture

NOW = 1_771_131_000


def tokens(expires_in: int = 3600, status: str = "linked") -> Tokens:
    return Tokens(
        account_id="ava1.ring.account.A1",
        access_token="at1",
        refresh_token="rt1",
        expires_at=NOW + expires_in,
        link_status=status,
    )


@pytest.fixture
def http():
    with httpx.Client() as c:
        yield c


def client(http, store) -> RingClient:
    return RingClient(http, store, OAuthClient(http, "cid", "csecret"), now=lambda: NOW)


# Bearer header
@respx.mock
def test_bearer_header_and_base_url(http):
    route = respx.get(f"{API_BASE}/v1/devices").respond(200, json=load_fixture("ring/devices.json"))
    resp = client(http, MemoryTokenStore(tokens())).get("/v1/devices")
    assert API_BASE == "https://api.amazonvision.com"
    assert resp.status_code == 200
    assert route.calls.last.request.headers["authorization"] == "Bearer at1"


def test_token_never_sent_to_another_host(http):
    with pytest.raises(ValueError):
        client(http, MemoryTokenStore(tokens())).get("https://evil.example.com/v1/devices")


# Token about to expire
@respx.mock
def test_token_about_to_expire_is_refreshed_first(http):
    respx.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_refresh.json"))
    route = respx.get(f"{API_BASE}/v1/devices").respond(200, json={"data": []})
    store = MemoryTokenStore(tokens(expires_in=240))
    client(http, store).get("/v1/devices")
    assert route.calls.last.request.headers["authorization"] == "Bearer at2"
    assert store.tokens.access_token == "at2"
    assert store.tokens.refresh_token == "rt2"
    assert store.tokens.expires_at == NOW + 14400
    assert store.tokens.link_status == "linked"


@respx.mock
def test_token_with_time_left_is_not_refreshed(http):
    oauth = respx.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_refresh.json"))
    respx.get(f"{API_BASE}/v1/devices").respond(200, json={"data": []})
    client(http, MemoryTokenStore(tokens(expires_in=301))).get("/v1/devices")
    assert not oauth.called


# Ring answers 401 once
@respx.mock
def test_401_once_refreshes_and_retries(http):
    respx.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_refresh.json"))
    route = respx.get(f"{API_BASE}/v1/devices").mock(
        side_effect=[httpx.Response(401), httpx.Response(200, json={"data": []})]
    )
    resp = client(http, MemoryTokenStore(tokens())).get("/v1/devices")
    assert resp.status_code == 200
    assert [c.request.headers["authorization"] for c in route.calls] == ["Bearer at1", "Bearer at2"]


# Ring answers 401 after refresh
@respx.mock
def test_401_after_refresh_fails(http):
    oauth = respx.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_refresh.json"))
    route = respx.get(f"{API_BASE}/v1/devices").respond(401)
    with pytest.raises(RingAuthError):
        client(http, MemoryTokenStore(tokens())).get("/v1/devices")
    assert route.call_count == 2
    assert oauth.call_count == 1


def test_no_tokens_raises_auth_error(http):
    with pytest.raises(RingAuthError):
        client(http, MemoryTokenStore(None)).get("/v1/devices")


@respx.mock
def test_post_sends_json(http):
    route = respx.post(f"{API_BASE}/v1/accounts/me/app-integrations").respond(201, json={})
    client(http, MemoryTokenStore(tokens())).post(
        "/v1/accounts/me/app-integrations", json={"nonce": "N1"}
    )
    req = route.calls.last.request
    assert req.headers["content-type"] == "application/json"
    assert req.content == b'{"nonce":"N1"}'


# Concurrent refresh
@respx.mock
def test_concurrent_refresh_calls_oauth_once(http):
    oauth = respx.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_refresh.json"))
    route = respx.get(f"{API_BASE}/v1/devices").respond(200, json={"data": []})
    both_loaded = threading.Barrier(2, timeout=5)

    class SlowStore(MemoryTokenStore):
        loads = 0

        def load(self):
            SlowStore.loads += 1
            current = super().load()
            if SlowStore.loads <= 2:  # both calls read the expiring tokens first
                both_loaded.wait()
            return current

    store = SlowStore(tokens(expires_in=240))
    ring = client(http, store)
    errors = []

    def call():
        try:
            ring.get("/v1/devices")
        except Exception as e:  # pragma: no cover - surfaced below
            errors.append(e)

    threads = [threading.Thread(target=call) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert oauth.call_count == 1
    assert [c.request.headers["authorization"] for c in route.calls] == ["Bearer at2"] * 2
    assert (store.tokens.access_token, store.tokens.refresh_token) == ("at2", "rt2")


# Another caller already refreshed
@respx.mock
def test_another_caller_already_refreshed(http):
    oauth = respx.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_refresh.json"))
    route = respx.get(f"{API_BASE}/v1/devices").respond(200, json={"data": []})
    newer = tokens(expires_in=14400).model_copy(
        update={"access_token": "at2", "refresh_token": "rt2"}
    )

    class RefreshedMeanwhile(MemoryTokenStore):
        def load(self):
            current = self.tokens
            self.tokens = newer  # another caller saves right after this read
            return current

    store = RefreshedMeanwhile(tokens(expires_in=240))
    client(http, store).get("/v1/devices")
    assert not oauth.called
    assert route.calls.last.request.headers["authorization"] == "Bearer at2"
    assert store.tokens == newer
    assert store.saves == 0
