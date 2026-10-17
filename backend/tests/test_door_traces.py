"""pipeline-debug-traces: door traces written by the fetch_stills task."""

import json
import logging

import boto3
import httpx
import pytest
import respx

from fridgesense.door_events import fetch_stills
from fridgesense.table import FridgeTable, account_pk
from fridgesense.traces import NullTraceWriter, TraceWriter, trace_thumbnail, writer_from_env
from tests import test_fetch_stills_task as fetch_tests
from tests.conftest import BUCKET, FakeBlurrer
from tests.test_fetch_stills_task import (
    ACCOUNT,
    CHECK,
    DOOR_SK,
    DOWNLOAD,
    OPEN,
    PREFIX,
    STATE,
    closed,
    door_events,
    ring_serves,
    stills_open_at,
)

ring_http = fetch_tests.ring_http  # the shared Ring client fixture
DEBUG = PREFIX + "debug/"
TRACE_SK = "TRACE#2026-08-14T13:53:16.000Z#ava1.ring.device.D1"


class BlurAll(FakeBlurrer):
    """Every still comes back changed, as if a face was blurred."""

    def __init__(self, drop=()):
        super().__init__(blurred=lambda data: b"blurred:" + data, drop=drop)


def run(ring_http, state=STATE, blurrer=None, writer=None, setup_for=None, s3=None, face_blur=True):
    ring, http = ring_http
    return fetch_stills(
        ring,
        http,
        boto3.client("s3"),
        FridgeTable(),
        BUCKET,
        CHECK,
        FakeBlurrer() if blurrer is None else blurrer,
        state,
        sleep=lambda s: None,
        setup_for=setup_for,
        writer=TraceWriter(s3 or boto3.client("s3"), FridgeTable(), BUCKET)
        if writer is None
        else writer,
        face_blur=face_blur,
    )


def s3_get(key: str) -> bytes:
    return boto3.client("s3").get_object(Bucket=BUCKET, Key=key)["Body"].read()


def keys(prefix: str = "") -> list[str]:
    listing = boto3.client("s3").list_objects_v2(Bucket=BUCKET, Prefix=prefix)
    return sorted(o["Key"] for o in listing.get("Contents", []))


def door_json() -> dict:
    return json.loads(s3_get(DEBUG + "door.json"))


def summary() -> dict | None:
    return FridgeTable().get(account_pk(ACCOUNT), TRACE_SK)


# Motion that is not the door
@respx.mock
def test_not_door_motion_traced(aws, ring_http):
    ring_serves([closed(30), closed(230)])
    out = run(ring_http)
    assert out["outcome"] == "not_door"
    assert door_events() == []
    assert keys(DEBUG) == sorted(
        [f"{DEBUG}raw-{n}.jpg" for n in range(1, 26)] + [DEBUG + "door.json"]
    )
    doc = door_json()
    assert doc["outcome"] == "not_door"
    assert doc["open_span"] == [] and doc["picked"] == [] and doc["stored_keys"] == []
    assert all(s["open"] is False for s in doc["stills"])
    assert summary()["outcome"] == "not_door"
    assert summary()["best"]["value"] == out["score"]


# Door opening (25 stills, stills 6-15 open)
@respx.mock
def test_door_opening_traced(aws, ring_http):
    ring_serves(stills_open_at(set(range(6, 16))))
    out = run(ring_http)
    doc = door_json()
    assert doc["outcome"] == "door_open"
    assert doc["door_sk"] == DOOR_SK
    [event] = door_events()
    assert doc["opened_at"] == event["opened_at"]
    assert doc["closed_at"] == event["closed_at"]
    assert doc["open_span"] == list(range(6, 17))
    assert doc["picked"] == [6, 9, 13, 16]
    assert doc["stored_keys"] == out["still_keys"] == event["still_keys"]
    # the trace shows the same verdicts the span came from
    assert [s["n"] for s in doc["stills"] if s["open"]] == list(range(6, 16))
    assert summary()["door_sk"] == DOOR_SK
    assert summary()["stills_downloaded"] == 25


def all_objects() -> list[bytes]:
    return [s3_get(k) for k in keys()]


# Raw stills are small blurred thumbnails
@respx.mock
def test_raw_stills_are_blurred_thumbnails(aws, ring_http):
    images = stills_open_at(set(range(6, 16)))
    ring_serves(images)
    out = run(ring_http, blurrer=BlurAll())
    assert [s3_get(f"{DEBUG}raw-{n}.jpg") for n in range(1, 26)] == [
        trace_thumbnail(i) for i in images
    ]
    assert not set(images) & set(all_objects())
    assert s3_get(out["still_keys"][0]) == b"blurred:" + images[5]


# Raw stills are the downloaded bytes (blurring off)
@respx.mock
def test_raw_stills_are_the_downloaded_bytes(aws, ring_http):
    images = stills_open_at(set(range(6, 16)))
    ring_serves(images)
    out = run(ring_http, blurrer=BlurAll(), face_blur=False)
    assert [s3_get(f"{DEBUG}raw-{n}.jpg") for n in range(1, 26)] == images
    assert s3_get(out["still_keys"][0]) == b"blurred:" + images[5]


# Too few stills
@respx.mock
def test_too_few_stills_traced(aws, ring_http):
    answers = iter([httpx.Response(303, headers={"Location": "https://dl.example.com/0"})])
    respx.post(DOWNLOAD).mock(side_effect=lambda request: next(answers, httpx.Response(403)))
    respx.get("https://dl.example.com/0").respond(200, content=OPEN)
    assert run(ring_http)["outcome"] == "no_media"
    doc = door_json()
    assert doc["outcome"] == "no_media"
    assert doc["stills"][0]["key"] == DEBUG + "raw-1.jpg"
    assert all(s["key"] is None and s["missing_status"] == 403 for s in doc["stills"][1:])
    assert summary()["stills_downloaded"] == 1


# Duplicate run
@respx.mock
def test_duplicate_run_traced(aws, ring_http):
    ring_serves([OPEN])
    run(ring_http)
    second = run(ring_http, {**STATE, "timestamp_ms": 1786715597500, "request_id": "R2"})
    assert second["outcome"] == "duplicate"
    assert door_json()["outcome"] == "duplicate"
    assert summary()["outcome"] == "duplicate"


# Setup lookup failed
@respx.mock
def test_setup_lookup_failed_traces_default_rule(aws, ring_http):
    def broken(account_id, device_id):
        raise RuntimeError("table down")

    ring_serves([closed(128)])
    run(ring_http, setup_for=broken)
    assert door_json()["rule"]["source"] == "default"


# Debug copy is not an event still
@respx.mock
def test_debug_copy_is_not_an_event_still(aws, ring_http):
    images = stills_open_at(set(range(6, 16)))
    ring_serves(images)
    out = run(ring_http, blurrer=BlurAll(drop={2}))
    # picked still 9 failed detection: only its thumbnail is kept
    assert s3_get(DEBUG + "raw-9.jpg") == trace_thumbnail(images[8])
    assert images[8] not in all_objects()
    assert len(out["still_keys"]) == 3
    assert f"{PREFIX}still-2.jpg" not in out["still_keys"]
    assert all(s3_get(k).startswith(b"blurred:") for k in out["still_keys"])
    assert keys(PREFIX + "still-") == sorted(out["still_keys"])


class FailingRawPuts:
    def __init__(self):
        self.real = boto3.client("s3")

    def put_object(self, **kwargs):
        from botocore.exceptions import ClientError

        if "raw-2.jpg" in kwargs["Key"]:
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "PutObject")
        return self.real.put_object(**kwargs)


# S3 put fails during door trace
@respx.mock
def test_trace_failure_keeps_the_door_event(aws, ring_http, caplog):
    caplog.set_level(logging.INFO)
    ring_serves(stills_open_at(set(range(6, 16))))
    out = run(ring_http, s3=FailingRawPuts())
    assert out["outcome"] == "door_open"
    [event] = door_events()
    assert event["status"] == "analyzing"
    failed = [r.getMessage() for r in caplog.records if "debug_trace_failed" in r.getMessage()]
    assert len(failed) == 1 and '"part": "door"' in failed[0]


# Off
@respx.mock
def test_tracing_off_writes_nothing(aws, ring_http):
    ring_serves(stills_open_at(set(range(6, 16))))
    out = run(ring_http, blurrer=BlurAll(), writer=NullTraceWriter())
    assert out["outcome"] == "door_open"
    assert keys(DEBUG) == []
    # No debug stills when tracing is off: only the blurred event stills are stored
    assert all(b.startswith(b"blurred:") for b in all_objects())
    assert FridgeTable().query(ACCOUNT, "TRACE#") == []


@pytest.mark.parametrize(
    ("setting", "kind"),
    [(None, TraceWriter), ("", TraceWriter), ("true", TraceWriter), ("false", NullTraceWriter)],
)
def test_writer_from_env(aws, monkeypatch, setting, kind):
    if setting is None:
        monkeypatch.delenv("DEBUG_TRACES", raising=False)
    else:
        monkeypatch.setenv("DEBUG_TRACES", setting)
    assert type(writer_from_env(boto3.client("s3"), FridgeTable(), BUCKET)) is kind
