"""Default wiring for Lambda handlers and the CLI."""

import httpx

from fridgesense.oauth import OAuthClient
from fridgesense.ring import RingClient
from fridgesense.store import AppConfig, TokenStore, load_app_config

_http: httpx.Client | None = None


def http_client() -> httpx.Client:
    global _http
    if _http is None:
        _http = httpx.Client()
    return _http


def oauth_client(cfg: AppConfig | None = None) -> OAuthClient:
    cfg = cfg or load_app_config()
    return OAuthClient(http_client(), cfg.client_id, cfg.client_secret)


def ring_client() -> RingClient:
    return RingClient(http_client(), TokenStore(), oauth_client())
