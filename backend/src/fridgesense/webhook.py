"""Ring webhook intake: verify, dedupe, acknowledge, dispatch.

Ring disables a webhook after 10+ failures in a row, so once the signature checks out
every call gets a 200, even ones we can't use.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Protocol

import boto3
from botocore.exceptions import ClientError

from fridgesense.crypto import verify_signature
from fridgesense.devices import account_pk
from fridgesense.logs import log_event
from fridgesense.store import AppConfig
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


class LoggingMotionHandler:
    """Placeholder until door-event-pipeline starts the workflow."""

    def handle(self, event: MotionEvent) -> None:
        log_event("motion_received", **event.__dict__)


class WebhookLog:
    """Remembers accepted request IDs so repeated deliveries are handled once."""

    def __init__(self, table_name: str | None = None):
        self.table = boto3.resource("dynamodb").Table(table_name or os.environ["TABLE_NAME"])

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


def handle_webhook(
    req: Request, cfg: AppConfig, log: WebhookLog, motion: MotionHandler, now: float
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
        motion.handle(event)
    elif event_type == "app_integration_added":
        log_event("app_integration_added", account_id=account_id, request_id=request_id)
    else:
        log_event("webhook_ignored", type=event_type, account_id=account_id)
    return json_response(200, {"ok": True})
