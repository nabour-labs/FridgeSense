"""Ring API client with automatic token refresh."""

import time
from collections.abc import Callable
from typing import Any, Protocol

import httpx

from fridgesense.oauth import OAuthClient
from fridgesense.store import Tokens

API_BASE = "https://api.amazonvision.com"
TIMEOUT_S = 5.0
REFRESH_MARGIN_S = 300


class RingAuthError(Exception):
    """No usable Ring token: nothing linked, or Ring still answers 401 after a refresh."""


class TokenStoreLike(Protocol):
    def load(self) -> Tokens | None: ...
    def save(self, tokens: Tokens) -> None: ...


def refreshed(tokens: Tokens, oauth: OAuthClient, now: float) -> Tokens:
    """New tokens from a refresh grant; keeps the old refresh token if Ring sends none."""
    resp = oauth.refresh(tokens.refresh_token)
    return tokens.model_copy(
        update={
            "access_token": resp.access_token,
            "refresh_token": resp.refresh_token or tokens.refresh_token,
            "expires_at": int(now) + resp.expires_in,
        }
    )


class RingClient:
    def __init__(
        self,
        http: httpx.Client,
        store: TokenStoreLike,
        oauth: OAuthClient,
        now: Callable[[], float] = time.time,
    ):
        self.http = http
        self.store = store
        self.oauth = oauth
        self.now = now

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", path, **kwargs)

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if not path.startswith("/"):
            raise ValueError("Ring API paths must be relative to the API base URL")
        tokens = self.store.load()
        if tokens is None:
            raise RingAuthError("no Ring account linked")
        if tokens.expires_at - self.now() < REFRESH_MARGIN_S:
            tokens = self._refresh(tokens)
        resp = self._send(method, path, tokens, **kwargs)
        if resp.status_code == 401:
            tokens = self._refresh(tokens)
            resp = self._send(method, path, tokens, **kwargs)
            if resp.status_code == 401:
                raise RingAuthError("Ring answered 401 after a token refresh")
        return resp

    def _refresh(self, tokens: Tokens) -> Tokens:
        new = refreshed(tokens, self.oauth, self.now())
        self.store.save(new)
        return new

    def _send(self, method: str, path: str, tokens: Tokens, **kwargs: Any) -> httpx.Response:
        extra = {k: v for k, v in kwargs.pop("headers", {}).items() if k.lower() != "authorization"}
        headers = {**extra, "Authorization": f"Bearer {tokens.access_token}"}
        return self.http.request(
            method, API_BASE + path, headers=headers, timeout=TIMEOUT_S, **kwargs
        )
