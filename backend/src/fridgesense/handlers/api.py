"""App API Lambda: sign-in plus inventory, door events and pending changes under /api."""

import base64
import json
import logging
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

import boto3
from botocore.config import Config

from fridgesense import session
from fridgesense.door_events import iso_utc
from fridgesense.logs import log_event
from fridgesense.store import TokenStore, load_app_config
from fridgesense.table import FridgeTable
from fridgesense.web import Request, json_response

now = time.time
DAY_MS = 24 * 3600 * 1000


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


def encode_id(sk: str) -> str:
    return base64.urlsafe_b64encode(sk.encode()).rstrip(b"=").decode()


def decode_id(value: str, prefix: str) -> str | None:
    try:
        sk = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    return sk if sk.startswith(prefix) else None


def inventory_body(table: FridgeTable, account_id: str) -> dict:
    items = [
        {
            "key": i["sk"].removeprefix("ITEM#"),
            "name": i.get("name", i["sk"].removeprefix("ITEM#")),
            "category": i.get("category", "other"),
            "quantity": i.get("quantity", 0),
            "last_changed_at": i.get("last_changed_at"),
        }
        for i in table.query(account_id, "ITEM#")
    ]
    items.sort(key=lambda i: (i["category"], i["name"].lower()))
    return {"items": items, "pending_count": len(table.query(account_id, "PENDING#"))}


@route("GET", "/api/inventory")
def get_inventory(ctx: Context) -> dict:
    return json_response(200, inventory_body(ctx.table, ctx.account_id))


STILLS_DAYS = 7
STILL_LINK_TTL_S = 900


def _s3():
    return boto3.client("s3", config=Config(signature_version="s3v4"))


@route("GET", "/api/events")
def get_events(ctx: Context) -> dict:
    raw = ctx.req.query.get("days", "7")
    if not raw.isdigit() or not 1 <= int(raw) <= 30:
        return json_response(400, {"error": "days must be 1 to 30"})
    now_ms = int(now() * 1000)
    since = iso_utc(now_ms - int(raw) * DAY_MS)
    stills_since = iso_utc(now_ms - STILLS_DAYS * DAY_MS)
    s3, bucket = _s3(), os.environ.get("STILLS_BUCKET", "")
    events = []
    for e in ctx.table.query_range(ctx.account_id, f"DOOR#{since}", "DOOR#~", newest_first=True):
        recent = e.get("opened_at", "") >= stills_since
        events.append(
            {
                "id": encode_id(e["sk"]),
                "opened_at": e.get("opened_at"),
                "closed_at": e.get("closed_at"),
                "duration_s": e.get("duration_s"),
                "status": e.get("status"),
                "changes": e.get("changes", []),
                "pending_count": e.get("pending_count", 0),
                "stills": [
                    s3.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": bucket, "Key": key},
                        ExpiresIn=STILL_LINK_TTL_S,
                    )
                    for key in (e.get("still_keys", []) if recent else [])
                ],
            }
        )
    return json_response(200, {"events": events})
