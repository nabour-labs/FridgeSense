"""Ring one-way account linking: token exchange and the link page."""

import hmac
import logging
from collections.abc import Callable

import httpx

from fridgesense import link_page
from fridgesense.crypto import is_fresh, nonce_for
from fridgesense.logs import log_event
from fridgesense.oauth import OAuthClient, OAuthRejected, OAuthUnavailable
from fridgesense.ring import API_BASE, TIMEOUT_S, RingAuthError, RingClient, TokenStoreLike
from fridgesense.store import AppConfig, Tokens
from fridgesense.web import Request, html_response, json_response


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
    # /ring/token has no auth: never let a new grant replace a different linked account.
    current = store.load()
    if (
        current is not None
        and current.link_status in ("linked", "needs_relink")
        and current.account_id != account_id
    ):
        log_event(
            "token_exchange_refused",
            logging.WARNING,
            account_id=current.account_id,
            new_account_id=account_id,
        )
        return json_response(409, {"error": "another account is linked"})
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


ACCOUNT_IDENTIFIER = "o***r@fridgesense.app"
INTEGRATIONS_PATH = "/v1/accounts/me/app-integrations"
OPEN_FROM_RING = "Open this page from the Ring app to link your camera."
TRY_AGAIN = "Start again from the Ring app."


class IntegrationFailed(Exception):
    pass


def link_form(req: Request) -> dict:
    nonce, time_ms = req.query.get("nonce"), req.query.get("time")
    if not nonce or not time_ms:
        return html_response(400, link_page.message("Can't link from here", OPEN_FROM_RING))
    return html_response(200, link_page.sign_in_form(nonce, time_ms))


def link_submit(
    req: Request,
    cfg: AppConfig,
    store: TokenStoreLike,
    ring: RingClient,
    now: float,
    after_link: Callable[[str], list[str] | None] = lambda account_id: None,
    app_url: str | None = None,
) -> dict:
    form = req.fields()
    nonce, time_ms = form.get("nonce", ""), form.get("time", "")
    passcode = form.get("passcode", "")
    if not cfg.passcode or not hmac.compare_digest(passcode.encode(), cfg.passcode.encode()):
        log_event("link_passcode_rejected", logging.WARNING)
        return html_response(
            401, link_page.sign_in_form(nonce, time_ms, "That passcode is incorrect.")
        )
    if not nonce or not time_ms:
        return html_response(400, link_page.message("Can't link from here", OPEN_FROM_RING))
    if not is_fresh(time_ms, now_ms=int(now * 1000)):
        log_event("link_rejected", logging.WARNING, reason="stale or future time")
        return html_response(400, link_page.message("This link has expired", TRY_AGAIN))
    tokens = store.load()
    if tokens is None or tokens.link_status != "unclaimed":
        log_event("link_rejected", logging.WARNING, reason="no unclaimed account")
        return html_response(400, link_page.message("Nothing to link", TRY_AGAIN))
    expected = nonce_for(cfg.hmac_key, time_ms, tokens.account_id)
    if not cfg.hmac_key or not hmac.compare_digest(nonce.encode(), expected.encode()):
        log_event("link_rejected", logging.WARNING, reason="nonce mismatch")
        return html_response(400, link_page.message("This link doesn't match", TRY_AGAIN))
    try:
        _complete_integration(ring, nonce)
    except IntegrationFailed as e:
        log_event("link_failed", logging.ERROR, account_id=tokens.account_id, error=str(e))
        return html_response(
            502, link_page.message("Linking failed", "Ring did not accept the link. " + TRY_AGAIN)
        )
    current = store.load() or tokens  # the Ring client may have refreshed the tokens
    store.save(current.model_copy(update={"link_status": "linked"}))
    log_event("link_ok", account_id=tokens.account_id)
    return html_response(200, link_page.linked(after_link(tokens.account_id), app_url))


def _complete_integration(ring: RingClient, nonce: str) -> None:
    steps = [
        ("POST", {"account_identifier": ACCOUNT_IDENTIFIER, "nonce": nonce}),
        ("PATCH", {"status": "completed"}),
    ]
    for method, body in steps:
        try:
            resp = ring.request(method, INTEGRATIONS_PATH, json=body)
        except (httpx.HTTPError, RingAuthError, OAuthRejected, OAuthUnavailable) as e:
            raise IntegrationFailed(f"{method}: {type(e).__name__}") from None
        if not resp.is_success:
            raise IntegrationFailed(f"{method}: HTTP {resp.status_code}")
