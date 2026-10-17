"""Ring webhook intake: verify, dedupe, acknowledge, dispatch.

Ring disables a webhook after 10+ failures in a row, so once the signature checks out
every call gets a 200, even ones we can't use.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import boto3
from botocore.exceptions import ClientError

from fridgesense.camera_info import StatusChange
from fridgesense.crypto import verify_signature
from fridgesense.logs import log_event
from fridgesense.store import AppConfig
from fridgesense.store import table_name as table_name_default
from fridgesense.table import account_pk
from fridgesense.web import Request, json_response

DEDUPE_TTL_S = 7 * 24 * 3600


@dataclass(frozen=True)
class MotionEvent:
    account_id: str
    device_id: str
    timestamp_ms: int
    sub_type: str
    request_id: str


class MotionHandler(Protocol):
    def handle(self, event: MotionEvent) -> None: ...


class StatusRecorder(Protocol):
    def record(self, account_id: str, device_id: str, change: StatusChange) -> None: ...


STATUS_EVENTS = {"device_online": True, "device_offline": False}


class LoggingMotionHandler:
    """Placeholder until door-event-pipeline starts the workflow."""

    def handle(self, event: MotionEvent) -> None:
        log_event("motion_received", **event.__dict__)


class WebhookLog:
    """Remembers accepted request IDs so repeated deliveries are handled once."""

    def __init__(self, table_name: str | None = None):
        self.table = boto3.resource("dynamodb").Table(table_name or table_name_default())

    def first_time(self, account_id: str, request_id: str, now: float) -> bool:
        try:
            self.table.put_item(
                Item={
                    "pk": account_pk(account_id),
                    "sk": f"WEBHOOK#{request_id}",
                    "ttl": int(now) + DEDUPE_TTL_S,
                },
                ConditionExpression="attribute_not_exists(sk)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        return True

    def forget(self, account_id: str, request_id: str) -> None:
        self.table.delete_item(Key={"pk": account_pk(account_id), "sk": f"WEBHOOK#{request_id}"})


def _is_paused(paused: Callable[[str, str], bool] | None, event: MotionEvent) -> bool:
    """A failed read counts as active: the stills step checks again before any download."""
    if paused is None:
        return False
    try:
        return paused(event.account_id, event.device_id)
    except Exception as e:
        log_event("monitoring_check_failed", logging.WARNING, error=type(e).__name__)
        return False


def handle_webhook(
    req: Request,
    cfg: AppConfig,
    log: WebhookLog,
    motion: MotionHandler,
    now: float,
    status: StatusRecorder | None = None,
    paused: Callable[[str, str], bool] | None = None,
) -> dict:
    if not cfg.hmac_key:
        log_event("webhook_not_configured", logging.ERROR)
        return json_response(503, {"error": "not configured"})
    if not verify_signature(req.raw_body, req.headers.get("x-signature"), cfg.hmac_key):
        log_event("webhook_bad_signature", logging.WARNING)
        return json_response(401, {"error": "bad signature"})

    try:
        payload = json.loads(req.raw_body)
        meta, data = payload["meta"], payload["data"]
        request_id, account_id = meta["request_id"], meta["account_id"]
        event_type = data["type"]
    except (ValueError, TypeError, KeyError) as e:
        log_event("webhook_malformed", logging.WARNING, error=type(e).__name__)
        return json_response(200, {"ok": True})

    if not log.first_time(account_id, request_id, now):
        log_event("webhook_duplicate", request_id=request_id, account_id=account_id)
        return json_response(200, {"ok": True, "duplicate": True})

    if event_type == "motion_detected":
        try:
            attrs = data["attributes"]
            event = MotionEvent(
                account_id=account_id,
                device_id=attrs["source"],
                timestamp_ms=int(attrs["timestamp"]),
                sub_type=str(attrs.get("sub_type", "motion")),
                request_id=request_id,
            )
        except (KeyError, TypeError, ValueError) as e:
            log_event("webhook_malformed", logging.WARNING, error=type(e).__name__)
            return json_response(200, {"ok": True})
        if _is_paused(paused, event):
            log_event("motion_paused", **event.__dict__)
            return json_response(200, {"ok": True, "paused": True})
        try:
            motion.handle(event)
        except Exception as e:
            # Forget the delivery so Ring's retry is handled as new; starting a run is idempotent.
            log.forget(account_id, request_id)
            log_event(
                "motion_handoff_failed", logging.ERROR, error=type(e).__name__, **event.__dict__
            )
            return json_response(500, {"error": "hand-over failed"})
    elif event_type in STATUS_EVENTS and status is not None:
        try:
            attrs = data["attributes"]
            device_id = str(attrs["source"])
            change = StatusChange(STATUS_EVENTS[event_type], int(attrs["timestamp"]), "webhook")
        except (KeyError, TypeError, ValueError) as e:
            log_event("webhook_malformed", logging.WARNING, error=type(e).__name__)
            return json_response(200, {"ok": True})
        try:
            status.record(account_id, device_id, change)
        except Exception as e:
            # Forget the delivery so Ring's retry is recorded; re-recording a change is harmless.
            log.forget(account_id, request_id)
            log_event("status_record_failed", logging.ERROR, error=type(e).__name__)
            return json_response(500, {"error": "record failed"})
        log_event(event_type, account_id=account_id, device_id=device_id, at_ms=change.at_ms)
    elif event_type == "app_integration_added":
        log_event("app_integration_added", account_id=account_id, request_id=request_id)
    else:
        log_event("webhook_ignored", type=event_type, account_id=account_id)
    return json_response(200, {"ok": True})
