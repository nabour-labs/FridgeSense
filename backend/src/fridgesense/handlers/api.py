"""App API Lambda: sign-in plus inventory, door events and pending changes under /api."""

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from fridgesense import session
from fridgesense.door_events import iso_utc
from fridgesense.logs import log_event
from fridgesense.store import TokenStore, load_app_config
from fridgesense.table import FridgeTable
from fridgesense.web import Request, json_response

now = time.time


@dataclass
class Context:
    req: Request
    account_id: str
    role: str
    params: dict[str, str]
    table: FridgeTable


@dataclass(frozen=True)
class Route:
    method: str
    pattern: re.Pattern
    handle: Callable[[Context], dict]
    write: bool = False


ROUTES: list[Route] = []


def route(method: str, path: str, write: bool = False):
    pattern = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path) + "$")

    def register(fn):
        ROUTES.append(Route(method, pattern, fn, write))
        return fn

    return register


def handler(event, context):
    logging.getLogger().setLevel(logging.INFO)
    req = Request.from_event(event)
    if (req.method, req.path) == ("POST", "/api/session"):
        return _sign_in(req)

    cfg = load_app_config()
    header = req.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
    role = session.verify(cfg, token, now=int(now())) if token else None
    if role is None:
        return json_response(401, {"error": "sign in"})

    for r in ROUTES:
        match = r.pattern.match(req.path)
        if r.method != req.method or not match:
            continue
        if r.write and role != "owner":
            return json_response(403, {"error": "read-only"})
        tokens = TokenStore().load()
        if tokens is None:
            return json_response(409, {"error": "no camera linked"})
        ctx = Context(req, tokens.account_id, role, match.groupdict(), FridgeTable())
        return r.handle(ctx)
    return json_response(404, {"error": "not found"})


def _sign_in(req: Request) -> dict:
    try:
        body = json.loads(req.raw_body or b"{}")
        passcode = body.get("passcode", "") if isinstance(body, dict) else ""
    except ValueError:
        passcode = ""
    result = session.sign_in(load_app_config(), str(passcode), now=int(now()))
    if result is None:
        log_event("sign_in_rejected", logging.WARNING)
        return json_response(401, {"error": "wrong passcode"})
    token, exp, role = result
    log_event("sign_in", role=role)
    return json_response(200, {"token": token, "expires_at": iso_utc(exp * 1000), "role": role})


@route("GET", "/api/inventory")
def get_inventory(ctx: Context) -> dict:
    return json_response(200, {"items": [], "pending_count": 0})
