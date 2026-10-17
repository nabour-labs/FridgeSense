"""pipeline-debug-traces: the trace writer."""

import io
import json
import logging

import boto3
import pytest
from PIL import Image

from fridgesense.door_events import DoorCheck, Downloaded
from fridgesense.table import FridgeTable, account_pk
from fridgesense.traces import DoorTrace, NullTraceWriter, TraceWriter, trace_thumbnail
from tests.conftest import BUCKET, color_jpeg

HALVES = ((0.0, 0.0, 0.5, 1.0), (0.5, 0.0, 0.5, 1.0))
GREY = (128, 128, 128)
FRIDGE_BLUE = (40, 90, 200)
ACCOUNT = "ava1.ring.account.A1"
DEVICE = "ava1.ring.device.D1"
STATE = {
    "account_id": ACCOUNT,
    "device_id": DEVICE,
    "timestamp_ms": 1786715596787,
    "window": {
        "status": "ready",
        "start_ms": 1786715596000,
        "end_ms": 1786715621000,
        "ring_event_id": "evt_1786715596000",
    },
}
PREFIX = f"accounts/{ACCOUNT}/devices/{DEVICE}/events/1786715596000/debug/"
TRACE_SK = f"TRACE#2026-08-14T13:53:16.000Z#{DEVICE}"
CLOSED = color_jpeg(GREY, size=(200, 100))
OPEN = color_jpeg(GREY, [((0.6, 0.0, 0.2, 0.5), FRIDGE_BLUE)], size=(200, 100))


def s3_get(key: str) -> bytes:
    return boto3.client("s3").get_object(Bucket=BUCKET, Key=key)["Body"].read()


def s3_keys() -> list[str]:
    listing = boto3.client("s3").list_objects_v2(Bucket=BUCKET)
    return sorted(o["Key"] for o in listing.get("Contents", []))


def door_json() -> dict:
    return json.loads(s3_get(PREFIX + "door.json"))


def summary() -> dict | None:
    return FridgeTable().get(account_pk(ACCOUNT), TRACE_SK)


def writer() -> TraceWriter:
    return TraceWriter(boto3.client("s3"), FridgeTable(), BUCKET)


def trace_of(stills: list[Downloaded], check: DoorCheck | None = None, **fields) -> DoorTrace:
    check = check or DoorCheck(zones=HALVES, threshold=0.02)
    values = {s.n: check.zone_values(s.data) for s in stills if s.data is not None}
    return DoorTrace(stills=stills, values=values, check=check, **fields)


TIMES = [1786715601000, 1786715606000, 1786715611000, 1786715616000]


def four(*images: bytes | None) -> list[Downloaded]:
    return [
        Downloaded(n, ts, data, None if data is not None else 403)
        for n, (ts, data) in enumerate(zip(TIMES, images, strict=True), start=1)
    ]


# Door opening
def test_door_opening_trace(aws):
    stills = four(CLOSED, OPEN, OPEN, CLOSED)
    door_sk = f"DOOR#2026-08-14T13:53:16.000Z#{DEVICE}"
    trace = trace_of(
        stills,
        outcome="door_open",
        open_span=[2, 3, 4],
        picked=[2, 3, 4],
        stored_keys=["k/still-1.jpg", "k/still-2.jpg", "k/still-3.jpg"],
        door_sk=door_sk,
        opened_at="2026-08-14T13:53:26.000Z",
        closed_at="2026-08-14T13:53:36.000Z",
    )
    writer().door(STATE, trace)

    assert [s3_get(f"{PREFIX}raw-{n}.jpg") for n in range(1, 5)] == [
        trace_thumbnail(i) for i in (CLOSED, OPEN, OPEN, CLOSED)
    ]
    doc = door_json()
    assert doc["outcome"] == "door_open"
    assert doc["door_sk"] == door_sk
    assert doc["opened_at"] == "2026-08-14T13:53:26.000Z"
    assert doc["closed_at"] == "2026-08-14T13:53:36.000Z"
    assert doc["open_span"] == [2, 3, 4]
    assert doc["picked"] == [2, 3, 4]
    assert doc["stored_keys"] == ["k/still-1.jpg", "k/still-2.jpg", "k/still-3.jpg"]
    assert doc["window"] == {
        "start_ms": 1786715596000,
        "end_ms": 1786715621000,
        "ring_event_id": "evt_1786715596000",
    }
    still2 = doc["stills"][1]
    assert still2["n"] == 2
    assert still2["at_ms"] == 1786715606000
    assert still2["key"] == f"{PREFIX}raw-2.jpg"
    assert still2["missing_status"] is None
    assert [(z["zone"], z["value"], z["threshold"], z["open"]) for z in still2["zones"]] == [
        (1, 0.0, 0.02, False),
        (2, pytest.approx(0.2, abs=0.02), 0.02, True),
    ]
    assert still2["best_zone"] == 2
    assert still2["open"] is True
    assert doc["stills"][0]["open"] is False


def test_zone_values_rounded_to_four_places(aws):
    writer().door(STATE, trace_of(four(OPEN, CLOSED, CLOSED, CLOSED), outcome="not_door"))
    value = door_json()["stills"][0]["zones"][1]["value"]
    assert value == round(value, 4)


# Raw stills are the downloaded bytes (blurring off)
def test_raw_stills_kept_as_downloaded_while_blurring_is_off(aws):
    writer().door(
        STATE, trace_of(four(CLOSED, OPEN, OPEN, CLOSED), outcome="not_door", face_blur=False)
    )
    assert [s3_get(f"{PREFIX}raw-{n}.jpg") for n in range(1, 5)] == [CLOSED, OPEN, OPEN, CLOSED]


# Still that cannot be decoded
def test_still_that_cannot_be_decoded(aws):
    stills = four(CLOSED, CLOSED, b"not an image", CLOSED)
    check = DoorCheck(zones=HALVES, threshold=0.02)
    values = {s.n: check.zone_values(s.data) for s in stills if s.n != 3}
    trace = DoorTrace(stills=stills, values=values, check=check, outcome="not_door")
    writer().door(STATE, trace)
    assert door_json()["stills"][2]["key"] is None
    assert s3_keys() == [PREFIX + n for n in ("door.json", "raw-1.jpg", "raw-2.jpg", "raw-4.jpg")]


# Too few stills
def test_missing_stills(aws):
    writer().door(STATE, trace_of(four(CLOSED, None, None, None), outcome="no_media"))
    doc = door_json()
    assert doc["outcome"] == "no_media"
    assert doc["stills"][0]["key"] == f"{PREFIX}raw-1.jpg"
    for still in doc["stills"][1:]:
        assert still["key"] is None
        assert still["missing_status"] == 403
        assert still["zones"] == []
        assert still["best_zone"] is None
        assert still["open"] is None
    assert s3_keys() == [PREFIX + "door.json", PREFIX + "raw-1.jpg"]


# Summary written
def test_summary_written(aws):
    writer().door(STATE, trace_of(four(CLOSED, OPEN, CLOSED, CLOSED), outcome="not_door"))
    item = summary()
    assert item["outcome"] == "not_door"
    assert item["door_sk"] is None
    assert item["nova_calls"] == []
    assert item["ttl"] == 1787320396
    assert item["device_id"] == DEVICE
    assert item["ring_event_id"] == "evt_1786715596000"
    assert (item["start_ms"], item["end_ms"]) == (1786715596000, 1786715621000)
    assert item["zones_source"] == "default"
    assert item["stills_requested"] == 4
    assert item["stills_downloaded"] == 4
    assert item["best"]["zone"] == 2
    assert item["best"]["feature"] == "blue"
    assert item["best"]["threshold"] == 0.02
    assert item["best"]["value"] == pytest.approx(0.2, abs=0.02)


def test_summary_with_no_stills_has_no_best(aws):
    writer().door(STATE, trace_of(four(None, None, None, None), outcome="no_media"))
    item = summary()
    assert item["best"] is None
    assert item["stills_downloaded"] == 0


# Duplicate run
def test_duplicate_replaces_summary(aws):
    w = writer()
    w.door(STATE, trace_of(four(CLOSED, OPEN, OPEN, CLOSED), outcome="door_open", door_sk="D"))
    w.door(STATE, trace_of(four(CLOSED, OPEN, OPEN, CLOSED), outcome="duplicate"))
    assert summary()["outcome"] == "duplicate"
    assert door_json()["outcome"] == "duplicate"


def test_null_writer_writes_nothing(aws):
    NullTraceWriter().door(STATE, trace_of(four(CLOSED, OPEN, OPEN, CLOSED), outcome="not_door"))
    assert s3_keys() == []
    assert FridgeTable().query(ACCOUNT, "TRACE#") == []


def png_size(data: bytes) -> tuple[int, int]:
    img = Image.open(io.BytesIO(data))
    assert img.format == "PNG"
    return img.size


# Setup rule
def test_setup_rule(aws):
    from fridgesense import door_calibration as dc

    left = {"x": 0, "y": 0, "width": 0.5, "height": 1}
    open_ref = color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), FRIDGE_BLUE)], size=(200, 100))
    closed_ref = color_jpeg(GREY, size=(200, 100))
    t0 = 1792092000000
    table = FridgeTable()
    z = dc.add_zone(table, ACCOUNT, DEVICE, "Doors", left, now_ms=t0).sk
    r1 = dc.add_reference(table, ACCOUNT, DEVICE, open_ref, z, "open", now_ms=t0)
    r2 = dc.add_reference(table, ACCOUNT, DEVICE, closed_ref, z, "closed", now_ms=t0 + 1)
    dc.run(table, ACCOUNT, DEVICE, now_ms=t0 + 60_000)
    check = dc.setup_check(table, ACCOUNT, DEVICE)

    writer().door(STATE, trace_of(four(CLOSED, OPEN, CLOSED, CLOSED), check, outcome="not_door"))

    rule = door_json()["rule"]
    assert rule["source"] == "setup"
    assert rule["ran_at"] == "2026-10-15T19:21:00.000Z"
    [zone] = rule["zones"]
    assert zone["box"] == {"x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0}
    assert (zone["feature"], zone["direction"]) == ("blue", "above")
    assert zone["threshold"] == pytest.approx(0.05, abs=0.005)
    assert zone["margin"] == pytest.approx(0.1, abs=0.005)
    assert zone["baseline_key"] == PREFIX + "baseline-1.png"
    assert png_size(s3_get(zone["baseline_key"])) == (256, 256)
    refs = rule["references"]
    assert [(r["status"], r["box"]) for r in refs] == [
        ("open", {"x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0}),
        ("closed", {"x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0}),
    ]
    for ref, original in zip(refs, (r1, r2), strict=True):
        assert ref["id"] == original.sk.removeprefix(dc.ref_prefix(DEVICE))
        assert ref["key"] == f"{PREFIX}door-ref-{ref['id']}.jpg"
        assert ref["created_at"] == original.created_at
        assert s3_get(ref["key"]) == original.image


def test_baseline_png_shows_the_baseline(aws):
    from fridgesense.door_events import ZoneRule, baseline_of

    whole = (0.0, 0.0, 1.0, 1.0)
    baseline = baseline_of([color_jpeg((10, 200, 30))], whole)
    rule = ZoneRule(whole, "change", "above", 0.1, baseline, margin=0.05)
    check = DoorCheck(rules=(rule,), source="setup", ran_at="2026-10-15T19:21:00.000Z")
    writer().door(STATE, trace_of(four(CLOSED, CLOSED, CLOSED, CLOSED), check, outcome="not_door"))
    img = Image.open(io.BytesIO(s3_get(PREFIX + "baseline-1.png"))).convert("RGB")
    r, g, b = img.getpixel((128, 128))
    assert abs(r - 10) <= 3 and abs(g - 200) <= 3 and abs(b - 30) <= 3


# Default rule
def test_default_rule(aws):
    check = DoorCheck.from_config("0.6,0.0,0.4,1.0", "0.03")
    writer().door(STATE, trace_of(four(CLOSED, OPEN, CLOSED, CLOSED), check, outcome="not_door"))
    rule = door_json()["rule"]
    assert rule == {
        "source": "default",
        "ran_at": None,
        "zones": [
            {
                "zone": 1,
                "box": {"x": 0.6, "y": 0.0, "width": 0.4, "height": 1.0},
                "feature": "blue",
                "direction": "above",
                "threshold": 0.03,
                "margin": None,
                "baseline_key": None,
            }
        ],
        "references": [],
    }
    assert not any("baseline" in k or "door-ref" in k for k in s3_keys())


class FailingS3:
    """An S3 client whose puts fail with AccessDenied (after optionally letting some through)."""

    def __init__(self, fail_keys: str = ""):
        self.real = boto3.client("s3")
        self.fail_keys = fail_keys

    def put_object(self, **kwargs):
        from botocore.exceptions import ClientError

        if self.fail_keys in kwargs["Key"]:
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "PutObject")
        return self.real.put_object(**kwargs)


class FailingTable(FridgeTable):
    def put(self, item):
        raise RuntimeError("table down")


def trace_failures(caplog) -> list[dict]:
    return [
        json.loads(r.getMessage()) for r in caplog.records if "debug_trace_failed" in r.getMessage()
    ]


# S3 put fails during door trace
def test_door_files_failure_is_logged_not_raised(aws, caplog):
    caplog.set_level(logging.INFO)
    w = TraceWriter(FailingS3("raw-2.jpg"), FridgeTable(), BUCKET)
    w.door(STATE, trace_of(four(CLOSED, OPEN, OPEN, CLOSED), outcome="door_open"))
    [line] = trace_failures(caplog)
    assert line["part"] == "door"
    assert line["error"] == "ClientError"
    assert (line["account_id"], line["device_id"]) == (ACCOUNT, DEVICE)
    assert summary()["outcome"] == "door_open"  # the summary is still written


def test_summary_failure_is_logged_not_raised(aws, caplog):
    caplog.set_level(logging.INFO)
    w = TraceWriter(boto3.client("s3"), FailingTable(), BUCKET)
    w.door(STATE, trace_of(four(CLOSED, OPEN, OPEN, CLOSED), outcome="door_open"))
    [line] = trace_failures(caplog)
    assert line["part"] == "summary"
    assert line["error"] == "RuntimeError"
    assert door_json()["outcome"] == "door_open"


# --- Nova call traces ---
from fridgesense.analysis import CallRecord, build_request  # noqa: E402
from fridgesense.usage import Tokens  # noqa: E402

RUN_MS = 1786715650000
STILL_KEYS = [
    f"accounts/{ACCOUNT}/devices/{DEVICE}/events/1786715596000/still-{n}.jpg" for n in (1, 2, 3, 4)
]
REF_MILK, REF_EGGS = color_jpeg((250, 250, 250)), color_jpeg((240, 220, 180))
REFERENCES = [("oat milk", REF_MILK), ("eggs", REF_EGGS)]
STILLS = [color_jpeg((n * 40, n * 40, n * 40)) for n in range(1, 5)]
TOOL_RESPONSE = {
    "output": {
        "message": {
            "role": "assistant",
            "content": [
                {
                    "toolUse": {
                        "toolUseId": "t1",
                        "name": "record_fridge_changes",
                        "input": {
                            "added": [
                                {
                                    "item": "milk",
                                    "category": "dairy",
                                    "quantity": 1,
                                    "confidence": 0.9,
                                }
                            ],
                            "removed": [],
                        },
                    }
                }
            ],
        }
    },
    "stopReason": "tool_use",
    "usage": {"inputTokens": 1180, "outputTokens": 96, "cacheReadInputTokens": 2000},
    "metrics": {"latencyMs": 2140},
}


def call(attempt=1, outcome="ok", instructions="", cache=False, **fields) -> CallRecord:
    request = build_request(
        "us.amazon.nova-2-lite-v1:0", STILLS, ["milk"], REFERENCES, instructions, cache=cache
    )
    defaults = {
        "response": TOOL_RESPONSE,
        "tokens": Tokens(input=1180, output=96, cache_read=2000),
        "usd": 0.000818,
        "latency_ms": 2140,
        "wall_ms": 2310,
    }
    return CallRecord(attempt=attempt, request=request, outcome=outcome, **{**defaults, **fields})


def nova(record: CallRecord, w: TraceWriter | None = None, run_ms: int = RUN_MS) -> None:
    (w or writer()).nova(STATE, run_ms, record, REFERENCES, STILL_KEYS)


def nova_json(attempt=1, run_ms=RUN_MS) -> dict:
    return json.loads(s3_get(f"{PREFIX}nova-{run_ms}-{attempt}.json"))


# Request with references
def test_nova_request_in_order(aws):
    nova(call(cache=True))
    content = nova_json()["request"]["content"]
    shapes = [
        (b["type"], b.get("role"), b.get("n")) if b["type"] == "image" else (b["type"],)
        for b in content
    ]
    assert shapes == [
        ("text",),
        ("text",),
        ("image", "reference", 1),
        ("text",),
        ("image", "reference", 2),
        ("cache_point",),
        ("text",),
        ("image", "still", 1),
        ("text",),
        ("image", "still", 2),
        ("text",),
        ("image", "still", 3),
        ("text",),
        ("image", "still", 4),
        ("cache_point",),
        ("text",),
    ]
    texts = [b["text"] for b in content if b["type"] == "text"]
    assert texts[1] == "Reference 1: oat milk"
    assert texts[2] == "Reference 2: eggs"
    assert texts[3] == "Image 1 of 4"
    assert "Current inventory: [milk]" in texts[-1]


# Image keys are retrievable
def test_nova_image_keys(aws):
    nova(call())
    images = [b for b in nova_json()["request"]["content"] if b["type"] == "image"]
    assert [b["key"] for b in images if b["role"] == "still"] == STILL_KEYS
    ref_keys = [b["key"] for b in images if b["role"] == "reference"]
    assert ref_keys == [f"{PREFIX}nova-{RUN_MS}-ref-{n}.jpg" for n in (1, 2)]
    assert [s3_get(k) for k in ref_keys] == [REF_MILK, REF_EGGS]


def test_nova_references_written_once_per_run(aws):
    puts = []
    w = writer()
    real_put = w._put
    w._put = lambda key, body, ct: puts.append(key) or real_put(key, body, ct)
    nova(call(attempt=1, outcome="invalid"), w)
    nova(call(attempt=2), w)
    assert sum("-ref-" in k for k in puts) == 2


# Owner's instructions shown
def test_nova_owner_instructions(aws):
    nova(call(instructions="Ignore condiments"))
    last = nova_json()["request"]["content"][-1]
    assert "Owner's instructions: Ignore condiments" in last["text"]


# Response kept
def test_nova_response_kept(aws):
    nova(call(response={**TOOL_RESPONSE, "ResponseMetadata": {"RequestId": "r"}}))
    doc = nova_json()
    assert doc["response"]["stopReason"] == "tool_use"
    tool = doc["response"]["output"]["message"]["content"][0]["toolUse"]
    assert tool["input"]["added"][0]["item"] == "milk"
    assert "ResponseMetadata" not in doc["response"]
    assert doc["request"]["inferenceConfig"] == {"maxTokens": 1024, "temperature": 0}
    assert doc["request"]["toolConfig"]["toolChoice"] == {"tool": {"name": "record_fridge_changes"}}
    assert doc["model_id"] == "us.amazon.nova-2-lite-v1:0"
    assert (doc["attempt"], doc["run_ms"], doc["outcome"]) == (1, RUN_MS, "ok")
    assert (doc["input_tokens"], doc["output_tokens"]) == (1180, 96)
    assert (doc["cache_read_tokens"], doc["cache_write_tokens"]) == (2000, 0)
    assert (doc["usd"], doc["latency_ms"], doc["wall_ms"]) == (0.000818, 2140, 2310)
    assert doc["error_code"] is None


def test_nova_error_call(aws):
    nova(
        call(
            outcome="error",
            response=None,
            tokens=Tokens(),
            usd=0.0,
            latency_ms=None,
            wall_ms=120,
            error_code="ThrottlingException",
        )
    )
    doc = nova_json()
    assert doc["response"] is None
    assert (doc["outcome"], doc["error_code"], doc["wall_ms"]) == (
        "error",
        "ThrottlingException",
        120,
    )
    assert (doc["input_tokens"], doc["usd"], doc["latency_ms"]) == (0, 0.0, None)


# Nova calls added later
def test_nova_calls_added_to_summary(aws):
    writer().door(
        STATE, trace_of(four(CLOSED, OPEN, OPEN, CLOSED), outcome="door_open", door_sk="D")
    )
    before = summary()
    nova(call())
    after = summary()
    [entry] = after["nova_calls"]
    assert entry == {
        "attempt": 1,
        "run_ms": RUN_MS,
        "outcome": "ok",
        "input_tokens": 1180,
        "output_tokens": 96,
        "cache_read_tokens": 2000,
        "cache_write_tokens": 0,
        "usd": 0.000818,
        "latency_ms": 2140,
        "wall_ms": 2310,
        "error_code": None,
        "key": f"{PREFIX}nova-{RUN_MS}-1.json",
    }
    assert {k: v for k, v in after.items() if k != "nova_calls"} == {
        k: v for k, v in before.items() if k != "nova_calls"
    }


def test_two_nova_calls_append(aws):
    writer().door(
        STATE, trace_of(four(CLOSED, OPEN, OPEN, CLOSED), outcome="door_open", door_sk="D")
    )
    nova(call(attempt=1, outcome="invalid"))
    nova(call(attempt=2))
    assert [c["outcome"] for c in summary()["nova_calls"]] == ["invalid", "ok"]


# Summary write fails during analysis
def test_nova_summary_failure_is_logged_not_raised(aws, caplog):
    class FailingUpdates(FridgeTable):
        def append(self, *args, **kwargs):
            raise RuntimeError("table down")

    caplog.set_level(logging.INFO)
    nova(call(), TraceWriter(boto3.client("s3"), FailingUpdates(), BUCKET))
    [line] = trace_failures(caplog)
    assert line["part"] == "summary"
    assert nova_json()["outcome"] == "ok"


def test_nova_file_failure_is_logged_not_raised(aws, caplog):
    caplog.set_level(logging.INFO)
    nova(call(), TraceWriter(FailingS3("nova-"), FridgeTable(), BUCKET))
    [line] = trace_failures(caplog)
    assert line["part"] == "nova"


def test_null_writer_nova_writes_nothing(aws):
    NullTraceWriter().nova(STATE, RUN_MS, call(), REFERENCES, STILL_KEYS)
    assert s3_keys() == []


def test_nova_without_window_is_logged_not_raised(aws, caplog):
    caplog.set_level(logging.INFO)
    state = {"account_id": ACCOUNT, "door_sk": "DOOR#x"}
    writer().nova(state, RUN_MS, call(), REFERENCES, STILL_KEYS)
    assert [line["part"] for line in trace_failures(caplog)] == ["nova"]
