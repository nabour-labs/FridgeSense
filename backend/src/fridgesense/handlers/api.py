"""App API Lambda: sign-in plus inventory, door events and pending changes under /api."""

import asyncio
import base64
import json
import logging
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import boto3
from botocore.config import Config

from fridgesense import analysis, analysis_config, ask, assistant, inventory, session, voice
from fridgesense.door_events import iso_utc
from fridgesense.logs import log_event
from fridgesense.store import TokenStore, load_app_config
from fridgesense.table import FridgeTable
from fridgesense.usage import Prices, UsageRecorder
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


MAX_RANGE_DAYS = 31
MAX_PAGE = 50


def _instant_ms(value: str) -> int | None:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return int(dt.timestamp() * 1000) if dt.tzinfo else None


def _event_range(query: dict) -> tuple[str, str] | str:
    """The DOOR# sort key range to list, or the 400 error text."""
    if "from" not in query:
        raw = query.get("days", "7")
        if not raw.isdigit() or not 1 <= int(raw) <= 30:
            return "days must be 1 to 30"
        return f"DOOR#{iso_utc(int(now() * 1000) - int(raw) * DAY_MS)}", "DOOR#~"
    start, end = _instant_ms(query["from"]), _instant_ms(query.get("to", ""))
    if start is None or end is None or not 0 < end - start <= MAX_RANGE_DAYS * DAY_MS:
        return f"from and to must be times, from before to, at most {MAX_RANGE_DAYS} days apart"
    return f"DOOR#{iso_utc(start)}", f"DOOR#{iso_utc(end)}"


@route("GET", "/api/events")
def get_events(ctx: Context) -> dict:
    span = _event_range(ctx.req.query)
    if isinstance(span, str):
        return json_response(400, {"error": span})
    low, high = span
    limit = None
    if "limit" in ctx.req.query:
        raw = ctx.req.query["limit"]
        if not raw.isdigit() or not 1 <= int(raw) <= MAX_PAGE:
            return json_response(400, {"error": f"limit must be 1 to {MAX_PAGE}"})
        limit = int(raw)
    cursor = None
    if "cursor" in ctx.req.query:
        cursor = decode_id(ctx.req.query["cursor"], "DOOR#")
        if cursor is None:
            return json_response(400, {"error": "invalid cursor"})
        high = min(high, cursor)
    # One extra to know whether an older page exists, one more for the cursor event itself.
    found = ctx.table.query_range(
        ctx.account_id, low, high, newest_first=True, limit=limit and limit + 2
    )
    found = [e for e in found if e["sk"] != cursor]
    more = limit is not None and len(found) > limit
    if limit is not None:
        found = found[:limit]
    now_ms = int(now() * 1000)
    stills_since = iso_utc(now_ms - STILLS_DAYS * DAY_MS)
    s3, bucket = _s3(), os.environ.get("STILLS_BUCKET", "")
    events = []
    for e in found:
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
    return json_response(200, {"events": events, "next": events[-1]["id"] if more else None})


@route("DELETE", "/api/events/{id}", write=True)
def delete_event(ctx: Context) -> dict:
    sk = decode_id(ctx.params["id"], "DOOR#")
    try:
        if sk is None:
            raise inventory.DoorEventNotFound(ctx.params["id"])
        inventory.delete_door_event(ctx.table, ctx.account_id, sk)
    except inventory.DoorEventNotFound:
        return json_response(404, {"error": "not found"})
    return json_response(200, {"id": ctx.params["id"]})


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


@route("POST", "/api/items", write=True)
def post_item(ctx: Context) -> dict:
    body = _json_body(ctx.req)
    if body is None:
        return json_response(400, {"error": "invalid body"})
    try:
        inventory.add_item(
            ctx.table,
            ctx.account_id,
            body.get("name"),
            body.get("category"),
            body.get("quantity"),
            now=_now_iso(),
        )
    except inventory.InvalidItem as e:
        return json_response(400, {"error": str(e)})
    return json_response(200, inventory_body(ctx.table, ctx.account_id))


@route("PUT", "/api/items/{key}", write=True)
def put_item(ctx: Context) -> dict:
    body = _json_body(ctx.req) or {}
    quantity = _whole_number(body.get("quantity"), 0)
    if quantity is None:
        return json_response(400, {"error": "quantity must be a whole number of 0 or more"})
    key, name, category = unquote(ctx.params["key"]), body.get("name"), body.get("category")
    try:
        if name is None:
            inventory.set_quantity(
                ctx.table, ctx.account_id, key, quantity, category=category, now=_now_iso()
            )
        else:
            inventory.edit_item(
                ctx.table, ctx.account_id, key, quantity, name, category, now=_now_iso()
            )
    except inventory.InvalidItem as e:
        return json_response(400, {"error": str(e)})
    except inventory.ItemExists:
        return json_response(409, {"error": "item exists"})
    except inventory.ItemNotFound:
        return json_response(404, {"error": "not found"})
    return json_response(200, inventory_body(ctx.table, ctx.account_id))


@route("DELETE", "/api/items/{key}", write=True)
def delete_item(ctx: Context) -> dict:
    try:
        inventory.delete_item(ctx.table, ctx.account_id, unquote(ctx.params["key"]))
    except inventory.ItemNotFound:
        return json_response(404, {"error": "not found"})
    return json_response(200, inventory_body(ctx.table, ctx.account_id))


def config_body(table: FridgeTable, account_id: str) -> dict:
    loaded = analysis_config.load(table, account_id)
    return {
        "instructions": loaded.instructions,
        "references": [
            {
                "id": encode_id(r.sk),
                "annotation": r.annotation,
                "image": base64.b64encode(r.image).decode(),
                "created_at": r.created_at,
            }
            for r in loaded.references
        ],
    }


@route("GET", "/api/config")
def get_config(ctx: Context) -> dict:
    return json_response(200, config_body(ctx.table, ctx.account_id))


@route("PUT", "/api/config/instructions", write=True)
def put_instructions(ctx: Context) -> dict:
    try:
        body = _json_body(ctx.req) or {}
        text = analysis_config.validate_instructions(body.get("instructions"))
    except analysis_config.Invalid as e:
        return json_response(400, {"error": e.message})
    analysis_config.save_instructions(ctx.table, ctx.account_id, text, now_ms=int(now() * 1000))
    return json_response(200, config_body(ctx.table, ctx.account_id))


@route("POST", "/api/config/references", write=True)
def post_reference(ctx: Context) -> dict:
    body = _json_body(ctx.req) or {}
    try:
        annotation = analysis_config.validate_annotation(body.get("annotation"))
        image = analysis_config.decode_image(body.get("image"))
    except analysis_config.Invalid as e:
        return json_response(400, {"error": e.message})
    try:
        analysis_config.add_reference(
            ctx.table, ctx.account_id, annotation, image, now_ms=int(now() * 1000)
        )
    except analysis_config.TooMany:
        limit = analysis_config.MAX_REFERENCES
        return json_response(409, {"error": f"at most {limit} reference images"})
    return json_response(200, config_body(ctx.table, ctx.account_id))


@route("DELETE", "/api/config/references/{id}", write=True)
def delete_reference(ctx: Context) -> dict:
    sk = decode_id(ctx.params["id"], analysis_config.REF_PREFIX)
    if sk is None or not analysis_config.delete_reference(ctx.table, ctx.account_id, sk):
        return json_response(404, {"error": "not found"})
    return json_response(200, config_body(ctx.table, ctx.account_id))


MAX_QUESTION = 200


@route("POST", "/api/ask")
def post_ask(ctx: Context) -> dict:
    question = (_json_body(ctx.req) or {}).get("question")
    if not isinstance(question, str) or not question.strip() or len(question) > MAX_QUESTION:
        return json_response(400, {"error": "question required"})
    tz = ZoneInfo(os.environ.get("TIME_ZONE") or "America/Toronto")
    when = datetime.fromtimestamp(now(), UTC)
    agent = _ask_assistant(ctx, question, when, tz)
    if agent is not None:
        body = {
            "intent": "agent",
            "answer": agent.answer,
            "data": {"tools": agent.tools},
            "source": "agent",
        }
    else:
        result = ask.ask(ctx.table, ctx.account_id, question, now=when, tz=tz)
        body = {**result.model_dump(), "source": "keywords"}
    voice_id = os.environ.get("ASK_VOICE") or voice.DEFAULT_VOICE
    body["audio"] = voice.speak(body["answer"], polly_client(), voice=voice_id)
    return json_response(200, body)


def bedrock_client():
    # One HTTP attempt: the assistant's 12 s deadline is the retry budget, and a failure
    # falls back to the keyword answer.
    return boto3.client(
        "bedrock-runtime",
        config=Config(
            retries={"total_max_attempts": 1, "mode": "standard"},
            connect_timeout=3,
            read_timeout=10,
        ),
    )


def polly_client():
    return boto3.client("polly")


def _ask_assistant(
    ctx: Context, question: str, when: datetime, tz: ZoneInfo
) -> assistant.AssistantResult | None:
    """The assistant's answer over MCP, or None to fall back to the keyword rules."""
    key = load_app_config().mcp_key
    if os.environ.get("ASK_AGENT") != "on" or not key or not ctx.req.host:
        return None
    limit = int(os.environ.get("ASK_AGENT_DAILY_LIMIT") or assistant.DAILY_LIMIT)
    model_id = os.environ.get("NOVA_MODEL_ID") or analysis.DEFAULT_MODEL_ID
    try:
        result = asyncio.run(
            assistant.run(
                question,
                server=assistant.mcp_url(ctx.req.host, key),
                bedrock=bedrock_client(),
                model_id=model_id,
                prices=Prices.from_env(),
                on_usage=UsageRecorder(
                    ctx.table,
                    tz,
                    source="assistant",
                    account_id=ctx.account_id,
                    model_id=model_id,
                    clock=lambda: when,
                ),
                budget=lambda: assistant.take_budget(ctx.table, ctx.account_id, when, tz, limit),
            )
        )
    except Exception as e:
        log_event("ask_agent", logging.ERROR, outcome="internal_error", error=type(e).__name__)
        return None
    return result if isinstance(result, assistant.AssistantResult) else None
