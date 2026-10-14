"""HTTP API Lambda: Ring token exchange, account link page and webhook."""

import logging
import time

from fridgesense import deps, linking
from fridgesense.store import TokenStore, load_app_config
from fridgesense.web import Request, json_response

now = time.time


def handler(event, context):
    logging.getLogger().setLevel(logging.INFO)
    req = Request.from_event(event)
    route = (req.method, req.path)
    if route == ("POST", "/ring/token"):
        return linking.token_exchange(
            req, deps.oauth_client(), deps.http_client(), TokenStore(), now()
        )
    if route == ("GET", "/ring/link"):
        return linking.link_form(req)
    if route == ("POST", "/ring/link"):
        return linking.link_submit(
            req, load_app_config(), TokenStore(), deps.ring_client(now), now()
        )
    return json_response(404, {"error": "not found"})
