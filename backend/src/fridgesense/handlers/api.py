"""App API Lambda: sign-in plus inventory, door events and pending changes under /api."""

import base64
import json
import logging
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import unquote

import boto3
from botocore.config import Config

from fridgesense import inventory, session
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


@route("GET", "/api/pending")
def get_pending(ctx: Context) -> dict:
    pending = [
        {
            "id": encode_id(p["sk"]),
            "door_event_id": encode_id(p["door_sk"]) if p.get("door_sk") else None,
            "item": p.get("item"),
            "category": p.get("category", "other"),
            "direction": p.get("direction"),
            "quantity": p.get("quantity", 1),
            "confidence": p.get("confidence", 0),
            "opened_at": p["sk"].removeprefix("PENDING#").rsplit("#", 1)[0],
        }
        for p in ctx.table.query(ctx.account_id, "PENDING#")
    ]
    return json_response(200, {"pending": pending})


def _json_body(req: Request) -> dict | None:
    if not req.raw_body:
        return {}
    try:
        body = json.loads(req.raw_body)
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def _whole_number(value, minimum: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        return None
    return value


def _now_iso() -> str:
    return iso_utc(int(now() * 1000))


@route("POST", "/api/pending/{id}/confirm", write=True)
def confirm(ctx: Context) -> dict:
    sk = decode_id(ctx.params["id"], "PENDING#")
    body = _json_body(ctx.req)
    if sk is None:
        return json_response(404, {"error": "not found"})
    if body is None:
        return json_response(400, {"error": "invalid body"})
    quantity = None
    if "quantity" in body:
        quantity = _whole_number(body["quantity"], 1)
        if quantity is None:
            return json_response(400, {"error": "quantity must be a whole number of 1 or more"})
    item = body.get("item")
    if item is not None and (not isinstance(item, str) or not item.strip()):
        return json_response(400, {"error": "item must be a name"})
    try:
        inventory.confirm_pending(
            ctx.table, ctx.account_id, sk, item=item, quantity=quantity, now=_now_iso()
        )
    except inventory.PendingNotFound:
        return json_response(404, {"error": "not found"})
    return json_response(200, inventory_body(ctx.table, ctx.account_id))


@route("POST", "/api/pending/{id}/reject", write=True)
def reject(ctx: Context) -> dict:
    sk = decode_id(ctx.params["id"], "PENDING#")
    if sk is None:
        return json_response(404, {"error": "not found"})
    try:
        inventory.reject_pending(ctx.table, ctx.account_id, sk)
    except inventory.PendingNotFound:
        return json_response(404, {"error": "not found"})
    return json_response(200, inventory_body(ctx.table, ctx.account_id))


@route("PUT", "/api/items/{key}", write=True)
def put_item(ctx: Context) -> dict:
    body = _json_body(ctx.req)
    quantity = _whole_number((body or {}).get("quantity"), 0)
    if quantity is None:
        return json_response(400, {"error": "quantity must be a whole number of 0 or more"})
    inventory.set_quantity(
        ctx.table, ctx.account_id, unquote(ctx.params["key"]), quantity, now=_now_iso()
    )
    return json_response(200, inventory_body(ctx.table, ctx.account_id))
