"""HTTP API Lambda: Ring token exchange, account link page and webhook."""

import logging
import os
import time

from fridgesense import deps, devices, linking, monitoring, webhook, workflow
from fridgesense.camera_info import StatusHistory
from fridgesense.store import TokenStore, load_app_config
from fridgesense.table import FridgeTable
from fridgesense.web import Request, json_response

now = time.time
motion_handler: webhook.MotionHandler = workflow.default_motion_handler()


def status_recorder() -> webhook.StatusRecorder:
    return StatusHistory(FridgeTable())


def is_paused(account_id: str, device_id: str) -> bool:
    return monitoring.load(FridgeTable(), account_id, device_id).paused


def handler(event, context):
    logging.getLogger().setLevel(logging.INFO)
    req = Request.from_event(event)
    route = (req.method, req.path)
    if route == ("POST", "/ring/token"):
        return linking.token_exchange(
            req, deps.oauth_client(), deps.http_client(), TokenStore(), now()
        )
    if route == ("POST", "/ring/webhook"):
        return webhook.handle_webhook(
            req,
            load_app_config(),
            webhook.WebhookLog(),
            motion_handler,
            now(),
            status=status_recorder(),
            paused=lambda account_id, device_id: is_paused(account_id, device_id),
        )
    if route == ("GET", "/ring/link"):
        return linking.link_form(req)
    if route == ("POST", "/ring/link"):
        ring = deps.ring_client(now)

        def after_link(account_id: str) -> list[str] | None:
            found = devices.discover(ring, devices.DeviceRepository(), account_id)
            return None if found is None else [d.name for d in found]

        return linking.link_submit(
            req,
            load_app_config(),
            TokenStore(),
            ring,
            now(),
            after_link,
            app_url=os.environ.get("APP_URL"),
        )
    return json_response(404, {"error": "not found"})
