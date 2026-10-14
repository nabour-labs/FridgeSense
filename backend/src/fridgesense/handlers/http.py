"""HTTP API Lambda: Ring token exchange, account link page and webhook."""

import logging
import time

from fridgesense import deps, devices, linking
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
        ring = deps.ring_client(now)

        def after_link(account_id: str) -> list[str] | None:
            found = devices.discover(ring, devices.DeviceRepository(), account_id)
            return None if found is None else [d.name for d in found]

        return linking.link_submit(req, load_app_config(), TokenStore(), ring, now(), after_link)
    return json_response(404, {"error": "not found"})
