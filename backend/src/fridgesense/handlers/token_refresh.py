"""Scheduled Lambda: keep the Ring tokens fresh (runs every 3 hours)."""

import logging
import time
from collections.abc import Callable

from fridgesense import deps
from fridgesense.logs import log_event
from fridgesense.oauth import OAuthClient, OAuthRejected
from fridgesense.ring import TokenStoreLike, refreshed
from fridgesense.store import TokenStore


def run_refresh(
    store: TokenStoreLike, oauth: OAuthClient, now: Callable[[], float] = time.time
) -> str:
    tokens = store.load()
    if tokens is None:
        log_event("token_refresh_skipped", reason="no account linked")
        return "nothing_to_refresh"
    if tokens.link_status == "needs_relink":
        log_event("token_refresh_skipped", reason="needs relink", account_id=tokens.account_id)
        return "needs_relink"
    try:
        new = refreshed(tokens, oauth, now())
    except OAuthRejected as e:
        store.save(tokens.model_copy(update={"link_status": "needs_relink"}))
        log_event(
            "token_refresh_rejected",
            logging.ERROR,
            account_id=tokens.account_id,
            error=str(e),
            action="re-link the Ring account",
        )
        return "needs_relink"
    store.save(new)
    log_event("token_refresh_ok", account_id=tokens.account_id, expires_at=new.expires_at)
    return "refreshed"


def handler(event, context):
    logging.getLogger().setLevel(logging.INFO)
    return {"result": run_refresh(TokenStore(), deps.oauth_client())}
