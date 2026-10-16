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

from fridgesense import (
    analysis,
    analysis_config,
    ask,
    assistant,
    camera,
    deps,
    door_calibration,
    fridge_area,
    inventory,
    session,
    traces,
    voice,
)
from fridgesense.devices import DeviceRepository
from fridgesense.door_events import DoorCheck, iso_utc
from fridgesense.faces import DEFAULT_PRICE, FaceBlurrer
from fridgesense.logs import log_event
from fridgesense.store import TokenStore, load_app_config
from fridgesense.table import FridgeTable, account_pk
from fridgesense.usage import Prices, UsageRecorder
from fridgesense.web import Request, json_response

now = time.time
sleep = time.sleep
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
    owner: bool = False  # owner only, even to read


ROUTES: list[Route] = []


def route(method: str, path: str, write: bool = False, owner: bool = False):
    pattern = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path) + "$")

    def register(fn):
        ROUTES.append(Route(method, pattern, fn, write, owner))
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
        if (r.write or r.owner) and role != "owner":
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


def _event_range(query: dict, prefix: str = "DOOR#") -> tuple[str, str] | str:
    """The sort key range to list, or the 400 error text."""
    if "from" not in query:
        raw = query.get("days", "7")
        if not raw.isdigit() or not 1 <= int(raw) <= 30:
            return "days must be 1 to 30"
        return f"{prefix}{iso_utc(int(now() * 1000) - int(raw) * DAY_MS)}", f"{prefix}~"
    start, end = _instant_ms(query["from"]), _instant_ms(query.get("to", ""))
    if start is None or end is None or not 0 < end - start <= MAX_RANGE_DAYS * DAY_MS:
        return f"from and to must be times, from before to, at most {MAX_RANGE_DAYS} days apart"
    return f"{prefix}{iso_utc(start)}", f"{prefix}{iso_utc(end)}"


def _page(ctx: Context, prefix: str) -> tuple[list[dict], bool] | dict:
    """Items in the query's range and page, newest first, and whether more remain; or a 400."""
    span = _event_range(ctx.req.query, prefix)
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
        cursor = decode_id(ctx.req.query["cursor"], prefix)
        if cursor is None:
            return json_response(400, {"error": "invalid cursor"})
        high = min(high, cursor)
    # One extra to know whether an older page exists, one more for the cursor item itself.
    found = ctx.table.query_range(
        ctx.account_id, low, high, newest_first=True, limit=limit and limit + 2
    )
    found = [e for e in found if e["sk"] != cursor]
    more = limit is not None and len(found) > limit
    if limit is not None:
        found = found[:limit]
    return found, more


@route("GET", "/api/events")
def get_events(ctx: Context) -> dict:
    page = _page(ctx, "DOOR#")
    if isinstance(page, dict):
        return page
    found, more = page
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


def _motion(item: dict) -> dict:
    """A traced motion as listed: what happened, and what its Nova calls cost and took."""
    calls = item.get("nova_calls", [])
    door_sk = item.get("door_sk")
    return {
        "id": encode_id(item["sk"]),
        "device_id": item.get("device_id"),
        "at": iso_utc(int(item["start_ms"])),
        "outcome": item.get("outcome"),
        "best": item.get("best"),
        "stills_downloaded": item.get("stills_downloaded", 0),
        "door_event_id": encode_id(door_sk) if door_sk else None,
        "nova": {
            "calls": len(calls),
            "input_tokens": sum(c.get("input_tokens", 0) for c in calls),
            "output_tokens": sum(c.get("output_tokens", 0) for c in calls),
            "usd": round(sum(c.get("usd", 0) for c in calls), 6),
            "latency_ms": sum(c["latency_ms"] for c in calls if c.get("latency_ms") is not None),
        },
    }


@route("GET", "/api/debug/motions", owner=True)
def get_motions(ctx: Context) -> dict:
    page = _page(ctx, "TRACE#")
    if isinstance(page, dict):
        return page
    found, more = page
    motions = [_motion(i) for i in found]
    return json_response(200, {"motions": motions, "next": motions[-1]["id"] if more else None})


@route("GET", "/api/debug/motions/{id}", owner=True)
def get_motion(ctx: Context) -> dict:
    sk = decode_id(ctx.params["id"], "TRACE#") or decode_id(ctx.params["id"], "DOOR#")
    if sk is None:
        return json_response(400, {"error": "invalid id"})
    sk = "TRACE#" + sk.split("#", 1)[1]  # a door event's trace shares its time and device
    item = ctx.table.get(account_pk(ctx.account_id), sk)
    if item is None:
        return json_response(404, {"error": "no trace"})
    s3, bucket = _s3(), os.environ.get("STILLS_BUCKET", "")
    found = traces.load(s3, bucket, ctx.account_id, item)
    if found is None:
        return json_response(404, {"error": "no trace"})
    door, calls = found

    def sign(key: str) -> str:
        return s3.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=STILL_LINK_TTL_S
        )

    motion = _motion(item)
    motion["nova_totals"] = motion.pop("nova")
    return json_response(
        200,
        {
            **motion,
            "door": traces.with_links(door, sign),
            "nova": [traces.with_links(c, sign) for c in calls],
        },
    )


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


def rekognition_client():
    return boto3.client(
        "rekognition",
        config=Config(retries={"max_attempts": 2}, connect_timeout=5, read_timeout=10),
    )


def _device_id(ctx: Context) -> str | None:
    """The account's first discovered camera (the setup UI handles one camera)."""
    devices = sorted(DeviceRepository().list(ctx.account_id), key=lambda d: d.device_id)
    return devices[0].device_id if devices else None


def with_device(fn: Callable[[Context, str], dict]) -> Callable[[Context], dict]:
    def handle(ctx: Context) -> dict:
        device_id = _device_id(ctx)
        if device_id is None:
            return json_response(409, {"error": "no camera found"})
        return fn(ctx, device_id)

    return handle


@route("POST", "/api/camera/snapshot", write=True)
@with_device
def post_snapshot(ctx: Context, device_id: str) -> dict:
    price = float(os.environ.get("FACE_DETECT_PRICE") or DEFAULT_PRICE)
    try:
        image, ts = camera.snapshot(
            deps.ring_client(now=now),
            deps.http_client(),
            FaceBlurrer(rekognition_client(), price),
            device_id,
            int(now() * 1000),
            sleep,
        )
    except camera.NoFootage:
        return json_response(409, {"error": "no recent footage"})
    except camera.SnapshotFailed:
        return json_response(502, {"error": "camera unavailable"})
    return json_response(
        200, {"image": base64.b64encode(image).decode(), "captured_at": iso_utc(ts)}
    )


def door_setup_body(
    table: FridgeTable, account_id: str, device_id: str, scores: dict | None = None
) -> dict:
    refs = door_calibration.list_references(table, account_id, device_id)
    setup = door_calibration.load_setup(table, account_id, device_id)
    if scores is None:
        scores = door_calibration.reference_scores(refs, setup)
    defaults = DoorCheck.from_config(os.environ.get("DOOR_ZONES"), os.environ.get("DOOR_THRESHOLD"))
    return {
        "device_id": device_id,
        "references": [
            {
                "id": encode_id(r.sk),
                "image": base64.b64encode(r.image).decode(),
                "box": door_calibration.box_json(r.box),
                "status": r.status,
                "score": None if scores.get(r.sk) is None else round(scores[r.sk], 3),
                "created_at": r.created_at,
            }
            for r in refs
        ],
        "setup": None
        if setup is None
        else {
            "zones": [
                {
                    **door_calibration.box_json(z.box),
                    "feature": z.feature,
                    "direction": z.direction,
                    "threshold": z.threshold,
                    "margin": z.margin,
                }
                for z in setup.zones
            ],
            "ran_at": setup.ran_at,
            "stale": setup.stale,
        },
        "defaults": {
            "zones": [door_calibration.box_json(z) for z in defaults.zones],
            "threshold": defaults.threshold,
        },
    }


@route("GET", "/api/door-calibration")
@with_device
def get_door_setup(ctx: Context, device_id: str) -> dict:
    return json_response(200, door_setup_body(ctx.table, ctx.account_id, device_id))


@route("POST", "/api/door-calibration/references", write=True)
@with_device
def post_door_reference(ctx: Context, device_id: str) -> dict:
    body = _json_body(ctx.req) or {}
    try:
        image = door_calibration.decode_image(body.get("image"))
        box = door_calibration.validate_box(body.get("box"))
        status = door_calibration.validate_status(body.get("status"))
    except analysis_config.Invalid as e:
        return json_response(400, {"error": e.message})
    try:
        door_calibration.add_reference(
            ctx.table, ctx.account_id, device_id, image, box, status, now_ms=int(now() * 1000)
        )
    except door_calibration.TooMany:
        limit = door_calibration.MAX_REFERENCES
        return json_response(409, {"error": f"at most {limit} door references"})
    return json_response(200, door_setup_body(ctx.table, ctx.account_id, device_id))


@route("DELETE", "/api/door-calibration/references/{id}", write=True)
@with_device
def delete_door_reference(ctx: Context, device_id: str) -> dict:
    sk = decode_id(ctx.params["id"], door_calibration.ref_prefix(device_id))
    if sk is None or not door_calibration.delete_reference(
        ctx.table, ctx.account_id, device_id, sk, now_ms=int(now() * 1000)
    ):
        return json_response(404, {"error": "not found"})
    return json_response(200, door_setup_body(ctx.table, ctx.account_id, device_id))


@route("POST", "/api/door-calibration/run", write=True)
@with_device
def post_door_setup_run(ctx: Context, device_id: str) -> dict:
    try:
        door_calibration.run(ctx.table, ctx.account_id, device_id, now_ms=int(now() * 1000))
    except door_calibration.SetupFailed as e:
        body = door_setup_body(ctx.table, ctx.account_id, device_id, scores=e.scores)
        return json_response(422, {"error": e.message, "references": body["references"]})
    log_event("door_setup_ran", account_id=ctx.account_id, device_id=device_id)
    return json_response(200, door_setup_body(ctx.table, ctx.account_id, device_id))


def fridge_area_body(table: FridgeTable, account_id: str, device_id: str) -> dict:
    area = fridge_area.load(table, account_id, device_id)
    return {
        "device_id": device_id,
        "area": None
        if area is None
        else {
            "image": base64.b64encode(area.image).decode(),
            "box": door_calibration.box_json(area.box),
            "updated_at": area.updated_at,
        },
    }


@route("GET", "/api/fridge-area")
@with_device
def get_fridge_area(ctx: Context, device_id: str) -> dict:
    return json_response(200, fridge_area_body(ctx.table, ctx.account_id, device_id))


@route("PUT", "/api/fridge-area", write=True)
@with_device
def put_fridge_area(ctx: Context, device_id: str) -> dict:
    body = _json_body(ctx.req) or {}
    try:
        image = door_calibration.decode_image(body.get("image"))
        fridge_area.save(
            ctx.table, ctx.account_id, device_id, image, body.get("box"), int(now() * 1000)
        )
    except analysis_config.Invalid as e:
        return json_response(400, {"error": e.message})
    return json_response(200, fridge_area_body(ctx.table, ctx.account_id, device_id))


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
