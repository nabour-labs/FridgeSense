"""clip-face-blur: publishing the blurred clip, failing closed, and logging what it cost."""

import json
import logging
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

from clipblur import handler
from clipblur.blur import BlurStats
from tests.clips import FakeDetector, make_clip

BUCKET = "stills"
TABLE = "fridge"
ACCOUNT = "ava1.ring.account.A1"
PK = f"ACCOUNT#{ACCOUNT}"
DOOR_SK = "DOOR#2026-10-18T10:08:00.000Z#ava1.ring.device.D1"
PREFIX = f"accounts/{ACCOUNT}/devices/D1/events/1792332480000/"
RAW_KEY = PREFIX + "clip-raw.mp4"
CLIP_KEY = PREFIX + "clip.mp4"


class Context:
    memory_limit_in_mb = "3008"  # a string in the real Lambda runtime


@pytest.fixture
def aws(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("STILLS_BUCKET", BUCKET)
    monkeypatch.setenv("TABLE_NAME", TABLE)
    monkeypatch.setattr(handler, "TMP_DIR", tmp_path)
    monkeypatch.setattr(
        handler,
        "make_detector",
        lambda w, h: FakeDetector([[10, 10, 50, 50, 0.9]], frames=range(3)),
    )
    with mock_aws():
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=BUCKET)
        s3.put_object(
            Bucket=BUCKET,
            Key=RAW_KEY,
            Body=make_clip(tmp_path / "src.mp4", 160, 90, 6).read_bytes(),
        )
        ddb = boto3.client("dynamodb")
        ddb.create_table(
            TableName=TABLE,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        ddb.put_item(
            TableName=TABLE, Item={"pk": {"S": PK}, "sk": {"S": DOOR_SK}, "status": {"S": "done"}}
        )
        yield s3, boto3.resource("dynamodb").Table(TABLE)


STATE = {
    "account_id": ACCOUNT,
    "device_id": "ava1.ring.device.D1",
    "door_sk": DOOR_SK,
    "clip": {"raw_key": RAW_KEY, "clip_span": [0.5, 8.5]},
}


def keys(s3) -> set[str]:
    return {o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])}


def door(table) -> dict | None:
    return table.get_item(Key={"pk": PK, "sk": DOOR_SK}).get("Item")


def logged(caplog, event) -> list[dict]:
    lines = [json.loads(r.getMessage()) for r in caplog.records if r.getMessage().startswith("{")]
    return [line for line in lines if line["event"] == event]


# Scenario: Clip published
def test_clip_published(aws, caplog):
    s3, table = aws
    caplog.set_level(logging.INFO)
    handler.handler(STATE, Context())
    assert keys(s3) == {CLIP_KEY}
    item = door(table)
    assert item["clip_key"] == CLIP_KEY
    assert item["clip_span"] == [Decimal("0.5"), Decimal("8.5")]
    assert item["clip_blurred"] is True
    [line] = logged(caplog, "clip_blurred")
    assert (line["device_id"], line["frames"], line["frames_with_faces"]) == (
        STATE["device_id"],
        6,
        3,
    )
    assert isinstance(line["duration_ms"], int)


# Scenario: Event deleted while blurring
def test_event_deleted_while_blurring(aws):
    s3, table = aws
    table.delete_item(Key={"pk": PK, "sk": DOOR_SK})
    handler.handler(STATE, Context())
    assert door(table) is None
    assert keys(s3) == set()


# Scenario: Detector fails / Decode error (the handler's part: clean up, log, re-raise)
def test_blur_failure_fails_closed(aws, caplog, monkeypatch):
    s3, table = aws
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(handler, "make_detector", lambda w, h: FakeDetector([], fail_on=2))
    with pytest.raises(RuntimeError):
        handler.handler(STATE, Context())
    assert keys(s3) == set()
    assert "clip_key" not in door(table)
    [line] = logged(caplog, "clip_not_stored")
    assert line["reason"] == "blur_failed" and line["device_id"] == STATE["device_id"]


def test_upload_failure_leaves_no_partial_clip(aws, monkeypatch):
    s3, table = aws

    def fail_update(*args, **kwargs):
        raise RuntimeError("dynamodb down")

    monkeypatch.setattr(handler, "publish", fail_update)
    with pytest.raises(RuntimeError):
        handler.handler(STATE, Context())
    assert keys(s3) == set()
    assert "clip_key" not in door(table)


# Scenario: Cost logged
def test_cost_logged(aws, caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    ticks = iter([1000.0, 1030.0])
    monkeypatch.setattr(handler, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(
        handler, "blur_clip", lambda src, dst, det: dst.write_bytes(b"mp4") and BlurStats(6, 0)
    )
    handler.handler(STATE, Context())
    [line] = logged(caplog, "clip_blur_cost")
    assert line == {
        "event": "clip_blur_cost",
        "device_id": STATE["device_id"],
        "billed_ms": 30000,
        "memory_mb": 3008,
        "usd": 0.001175,
    }
