"""Ring one-way account linking: token exchange and the link page."""

import logging

import httpx

from fridgesense.logs import log_event
from fridgesense.oauth import OAuthClient, OAuthRejected, OAuthUnavailable
from fridgesense.ring import API_BASE, TIMEOUT_S, TokenStoreLike
from fridgesense.store import Tokens
from fridgesense.web import Request, json_response


class RingLookupFailed(Exception):
    pass


def users_me(http: httpx.Client, access_token: str) -> str:
    """The Ring account ID for a freshly issued access token."""
    try:
        resp = http.get(
            f"{API_BASE}/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=TIMEOUT_S,
        )
    except httpx.HTTPError as e:
        raise RingLookupFailed(type(e).__name__) from None
    if resp.status_code != 200:
        raise RingLookupFailed(f"HTTP {resp.status_code}")
    return resp.json()["data"]["id"]


def token_exchange(
    req: Request, oauth: OAuthClient, http: httpx.Client, store: TokenStoreLike, now: float
) -> dict:
    fields = req.fields()
    code = fields.get("code") or req.query.get("code")
    # Ring's request format isn't documented: log its shape (names only) to learn it.
    shape = {
        "content_type": req.content_type,
        "body_fields": sorted(fields),
        "query_fields": sorted(req.query),
    }
    if not code:
        log_event("token_exchange_missing_code", logging.WARNING, **shape)
        return json_response(400, {"error": "missing code"})
    try:
        grant = oauth.exchange_code(code)
        account_id = users_me(http, grant.access_token)
    except (OAuthRejected, OAuthUnavailable, RingLookupFailed) as e:
        log_event("token_exchange_failed", logging.ERROR, error=str(e), **shape)
        return json_response(502, {"error": "token exchange failed"})
    store.save(
        Tokens(
            account_id=account_id,
            access_token=grant.access_token,
            refresh_token=grant.refresh_token or "",
            expires_at=int(now) + grant.expires_in,
            link_status="unclaimed",
        )
    )
    log_event("token_exchange_ok", account_id=account_id, **shape)
    return json_response(200, {"ok": True})
