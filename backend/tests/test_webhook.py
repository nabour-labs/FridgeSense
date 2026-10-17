"""ring-webhook-intake: signature, dedupe, safe acknowledgement, motion hand-over."""

import hashlib
import hmac
import json
import logging

import boto3
import pytest

from fridgesense.handlers import http
from fridgesense.webhook import MotionEvent
from tests.conftest import APP_CONFIG, APP_SECRET, TABLE, api_event, fixture_bytes

NOW = 1_771_131_000.0
KEY = APP_CONFIG["hmac_key"]
MOTION = fixture_bytes("ring/webhook_motion_detected.json")
ACCOUNT = "ava1.ring.account.XXXYYY"
MOTION_REQUEST_ID = "2ad45ade-1818-4154-813b-afdd8bcd8085"


class RecordingMotionHandler:
    def __init__(self):
        self.events: list[MotionEvent] = []

    def handle(self, event: MotionEvent) -> None:
        self.events.append(event)


@pytest.fixture
def motion(monkeypatch):
    recorder = RecordingMotionHandler()
    monkeypatch.setattr(http, "motion_handler", recorder)
    monkeypatch.setattr(http, "now", lambda: NOW)
    return recorder


def sign(body: bytes, key: str = KEY) -> str:
    return "sha256=" + hmac.new(key.encode(), body, hashlib.sha256).hexdigest()


def post(body: bytes, signature: str | None = "auto", base64: bool = False):
    headers = {"content-type": "application/json"}
    if signature == "auto":
        signature = sign(body)
    if signature is not None:
        headers["X-Signature"] = signature
    return http.handler(api_event("POST", "/ring/webhook", body, headers, base64=base64), None)


def stored_items():
    return boto3.resource("dynamodb").Table(TABLE).scan()["Items"]


# Valid signature
def test_valid_signature(aws, motion):
    resp = post(MOTION)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"ok": True}


# Invalid signature
def test_invalid_signature(aws, motion):
    resp = post(MOTION, "sha256=" + "0" * 64)
    assert resp["statusCode"] == 401
    assert stored_items() == []
    assert motion.events == []


def test_signature_over_different_bytes_is_rejected(aws, motion):
    reformatted = json.dumps(json.loads(MOTION)).encode()
    assert post(reformatted, sign(MOTION))["statusCode"] == 401


def test_invalid_signature_body_is_not_parsed(aws, motion):
    assert post(b"not json at all", "sha256=" + "0" * 64)["statusCode"] == 401


# Missing signature header
def test_missing_signature_header(aws, motion):
    assert post(MOTION, None)["statusCode"] == 401
    assert stored_items() == []


# Base64-encoded body from the gateway
def test_base64_encoded_body(aws, motion):
    resp = post(MOTION, sign(MOTION), base64=True)
    assert resp["statusCode"] == 200
    assert len(motion.events) == 1


# Signing key not configured
def test_signing_key_not_configured(aws, motion):
    boto3.client("secretsmanager").put_secret_value(
        SecretId=APP_SECRET, SecretString=json.dumps({**APP_CONFIG, "hmac_key": ""})
    )
    assert post(MOTION, sign(MOTION, ""))["statusCode"] == 503
    assert stored_items() == []
    assert motion.events == []


# First delivery
def test_first_delivery(aws, motion):
    post(MOTION)
    [item] = stored_items()
    assert item["pk"] == f"ACCOUNT#{ACCOUNT}"
    assert item["sk"] == f"WEBHOOK#{MOTION_REQUEST_ID}"
    assert int(item["ttl"]) == int(NOW) + 7 * 24 * 3600
    assert len(motion.events) == 1


# Repeated delivery
def test_repeated_delivery(aws, motion):
    post(MOTION)
    resp = post(MOTION)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"ok": True, "duplicate": True}
    assert len(motion.events) == 1
    assert len(stored_items()) == 1


# Unknown event type
def test_unknown_event_type(aws, motion, caplog):
    caplog.set_level(logging.INFO)
    resp = post(fixture_bytes("ring/webhook_button_press.json"))
    assert resp["statusCode"] == 200
    assert motion.events == []
    messages = [r.getMessage() for r in caplog.records]
    assert any("button_press" in m and "ignored" in m for m in messages)


# Malformed JSON with a valid signature
@pytest.mark.parametrize(
    "body",
    [b"{not json", b"[]", json.dumps({"data": {"type": "motion_detected"}}).encode()],
    ids=["not-json", "not-object", "no-request-id"],
)
def test_malformed_body_with_valid_signature(aws, motion, caplog, body):
    caplog.set_level(logging.INFO)
    resp = post(body)
    assert resp["statusCode"] == 200
    assert motion.events == []
    assert any("webhook_malformed" in r.getMessage() for r in caplog.records)


# Motion event handed over
def test_motion_event_handed_over(aws, motion):
    post(MOTION)
    assert motion.events == [
        MotionEvent(
            account_id=ACCOUNT,
            device_id="ava1.ring.device.XXXYYY",
            timestamp_ms=1786715596787,
            sub_type="motion",
            request_id=MOTION_REQUEST_ID,
        )
    ]


def test_default_motion_handler_logs(aws, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(http, "now", lambda: NOW)
    assert post(MOTION)["statusCode"] == 200
    assert any(
        "motion_received" in r.getMessage() and "ava1.ring.device.XXXYYY" in r.getMessage()
        for r in caplog.records
    )


# App integration added
def test_app_integration_added(aws, motion, caplog):
    caplog.set_level(logging.INFO)
    resp = post(fixture_bytes("ring/webhook_app_integration_added.json"))
    assert resp["statusCode"] == 200
    assert any(
        "app_integration_added" in r.getMessage() and ACCOUNT in r.getMessage()
        for r in caplog.records
    )


class FlakyMotionHandler:
    """Fails the first `failures` calls, then records events."""

    def __init__(self, failures: int):
        self.failures = failures
        self.events: list[MotionEvent] = []

    def handle(self, event: MotionEvent) -> None:
        if self.failures:
            self.failures -= 1
            raise RuntimeError("StartExecution failed")
        self.events.append(event)


# Motion handler fails
def test_motion_handler_fails(aws, monkeypatch):
    monkeypatch.setattr(http, "now", lambda: NOW)
    monkeypatch.setattr(http, "motion_handler", FlakyMotionHandler(failures=1))
    resp = post(MOTION)
    assert resp["statusCode"] == 500
    assert stored_items() == []


# Ring retries after a failed hand-over
def test_ring_retries_after_failed_hand_over(aws, monkeypatch):
    flaky = FlakyMotionHandler(failures=1)
    monkeypatch.setattr(http, "now", lambda: NOW)
    monkeypatch.setattr(http, "motion_handler", flaky)
    assert post(MOTION)["statusCode"] == 500
    resp = post(MOTION)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"ok": True}
    assert len(flaky.events) == 1


# --- device_online / device_offline ---

OFFLINE = fixture_bytes("ring/webhook_device_offline.json")
ONLINE = fixture_bytes("ring/webhook_device_online.json")
STATUS_DEVICE = "ava1.ring.device.XXXYYY"


def recorded_changes():
    from fridgesense.camera_info import StatusHistory
    from fridgesense.table import FridgeTable

    return StatusHistory(FridgeTable()).since(ACCOUNT, STATUS_DEVICE, 0)


# Scenario: Device goes offline
def test_device_goes_offline(aws, motion):
    from fridgesense.camera_info import StatusChange

    resp = post(OFFLINE)
    assert (resp["statusCode"], json.loads(resp["body"])) == (200, {"ok": True})
    assert recorded_changes() == [StatusChange(False, 1771025206000, "webhook")]
    assert motion.events == []


# Scenario: Device comes online
def test_device_comes_online(aws, motion):
    from fridgesense.camera_info import StatusChange

    assert post(ONLINE)["statusCode"] == 200
    assert recorded_changes() == [StatusChange(True, 1771025206000, "webhook")]


# Scenario: Repeated status delivery
def test_repeated_status_delivery(aws, motion):
    post(OFFLINE)
    resp = post(OFFLINE)
    assert (resp["statusCode"], json.loads(resp["body"])) == (200, {"ok": True, "duplicate": True})
    assert len(recorded_changes()) == 1


# Scenario: Status event without a timestamp
def test_status_event_without_a_timestamp(aws, motion, caplog):
    payload = json.loads(ONLINE)
    del payload["data"]["attributes"]["timestamp"]
    body = json.dumps(payload).encode()
    with caplog.at_level(logging.INFO):
        resp = post(body)
    assert (resp["statusCode"], json.loads(resp["body"])) == (200, {"ok": True})
    assert recorded_changes() == []
    assert any("webhook_malformed" in r.getMessage() for r in caplog.records)


# Scenario: Bad signature on a status event
def test_bad_signature_on_a_status_event(aws, motion):
    assert post(OFFLINE, "sha256=" + "0" * 64)["statusCode"] == 401
    assert recorded_changes() == []


def test_status_recorder_fails(aws, motion, monkeypatch):
    class Broken:
        def record(self, *args):
            raise RuntimeError("table down")

    working = http.status_recorder
    monkeypatch.setattr(http, "status_recorder", lambda: Broken())
    assert post(OFFLINE)["statusCode"] == 500
    # Restore only the recorder: monkeypatch.undo() would also drop the aws fixture's region.
    monkeypatch.setattr(http, "status_recorder", working)
    monkeypatch.setattr(http, "now", lambda: NOW)
    # The request id was forgotten, so Ring's retry is recorded.
    assert post(OFFLINE)["statusCode"] == 200
    assert len(recorded_changes()) == 1
