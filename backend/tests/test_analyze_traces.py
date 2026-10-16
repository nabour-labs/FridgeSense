"""pipeline-debug-traces: Nova call traces written by the analyze task."""

import copy
import json
from datetime import UTC, datetime

import boto3
import pytest

from fridgesense import analysis_config
from fridgesense.analysis import NovaAnalyzer
from fridgesense.inventory import analyze_task
from fridgesense.table import FridgeTable, account_pk
from fridgesense.traces import NullTraceWriter, TraceWriter
from tests.conftest import BUCKET, color_jpeg, load_fixture

ACCOUNT = "ava1.ring.account.A1"
DEVICE = "ava1.ring.device.D1"
DOOR_SK = f"DOOR#2026-08-14T13:53:16.000Z#{DEVICE}"
TRACE_SK = f"TRACE#2026-08-14T13:53:16.000Z#{DEVICE}"
PREFIX = f"accounts/{ACCOUNT}/devices/{DEVICE}/events/1786715596000/"
KEYS = [f"{PREFIX}still-{n}.jpg" for n in range(1, 5)]
STATE = {
    "account_id": ACCOUNT,
    "device_id": DEVICE,
    "timestamp_ms": 1786715596787,
    "window": {"status": "ready", "start_ms": 1786715596000, "end_ms": 1786715621000},
    "door_sk": DOOR_SK,
    "still_keys": KEYS,
    "outcome": "door_open",
}
BLURRED = [color_jpeg((n * 50, 60, 70)) for n in range(1, 5)]
RAW = [color_jpeg((n * 50, 200, 200)) for n in range(1, 5)]


class FakeBedrock:
    """Answers each converse call with the next response and keeps every request."""

    def __init__(self, *responses: dict):
        self.responses = list(responses)
        self.requests: list[dict] = []

    def converse(self, **request):
        self.requests.append(copy.deepcopy(request))
        return copy.deepcopy(self.responses.pop(0))


@pytest.fixture
def table(aws):
    s3 = boto3.client("s3")
    for key, still, raw in zip(KEYS, BLURRED, RAW, strict=True):
        s3.put_object(Bucket=BUCKET, Key=key, Body=still)
        s3.put_object(Bucket=BUCKET, Key=key.replace("still-", "debug/raw-"), Body=raw)
    t = FridgeTable()
    t.put({"pk": account_pk(ACCOUNT), "sk": DOOR_SK, "status": "analyzing"})
    t.put({"pk": account_pk(ACCOUNT), "sk": TRACE_SK, "outcome": "door_open", "nova_calls": []})
    return t


def at(ms: int):
    return lambda: datetime.fromtimestamp(ms / 1000, UTC)


def run(table, client, writer=None, clock_ms=1786715650000, state=STATE):
    return analyze_task(
        NovaAnalyzer(client),
        boto3.client("s3"),
        table,
        BUCKET,
        state,
        clock=at(clock_ms),
        writer=TraceWriter(boto3.client("s3"), table, BUCKET) if writer is None else writer,
    )


def debug_keys() -> list[str]:
    listing = boto3.client("s3").list_objects_v2(Bucket=BUCKET, Prefix=PREFIX + "debug/nova-")
    return sorted(o["Key"] for o in listing.get("Contents", []))


def s3_json(key: str) -> dict:
    return json.loads(boto3.client("s3").get_object(Bucket=BUCKET, Key=key)["Body"].read())


def test_analysis_traced(table):
    run(table, FakeBedrock(load_fixture("nova/converse_tool_use.json")))
    assert debug_keys() == [f"{PREFIX}debug/nova-1786715650000-1.json"]
    doc = s3_json(debug_keys()[0])
    assert doc["outcome"] == "ok"
    assert (doc["input_tokens"], doc["output_tokens"], doc["latency_ms"]) == (1180, 96, 2140)
    [entry] = table.get(account_pk(ACCOUNT), TRACE_SK)["nova_calls"]
    assert entry["key"] == debug_keys()[0]


def test_reference_images_traced(table):
    ref = color_jpeg((250, 250, 250))
    analysis_config.add_reference(table, ACCOUNT, "oat milk", ref, now_ms=1)
    run(table, FakeBedrock(load_fixture("nova/converse_tool_use.json")))
    doc = s3_json(f"{PREFIX}debug/nova-1786715650000-1.json")
    [ref_block] = [b for b in doc["request"]["content"] if b.get("role") == "reference"]
    stored = boto3.client("s3").get_object(Bucket=BUCKET, Key=ref_block["key"])["Body"].read()
    assert stored == ref


# Retried analyze step
def test_retried_analyze_step_keeps_both_runs(table):
    run(table, FakeBedrock(load_fixture("nova/converse_tool_use.json")), clock_ms=1786715650000)
    run(table, FakeBedrock(load_fixture("nova/converse_tool_use.json")), clock_ms=1786715660000)
    assert debug_keys() == [
        f"{PREFIX}debug/nova-1786715650000-1.json",
        f"{PREFIX}debug/nova-1786715660000-1.json",
    ]
    assert len(table.get(account_pk(ACCOUNT), TRACE_SK)["nova_calls"]) == 2


# Analysis receives blurred bytes
def test_analysis_receives_blurred_bytes(table):
    bedrock = FakeBedrock(load_fixture("nova/converse_tool_use.json"))
    run(table, bedrock)
    sent = [
        b["image"]["source"]["bytes"]
        for b in bedrock.requests[0]["messages"][0]["content"]
        if "image" in b
    ]
    assert sent == BLURRED
    assert not set(sent) & set(RAW)
    doc = s3_json(f"{PREFIX}debug/nova-1786715650000-1.json")
    assert [b["key"] for b in doc["request"]["content"] if b["type"] == "image"] == KEYS


# Summary write fails during analysis
def test_summary_failure_keeps_the_analysis(table):
    class FailingAppend(FridgeTable):
        def append(self, *args, **kwargs):
            raise RuntimeError("table down")

    writer = TraceWriter(boto3.client("s3"), FailingAppend(), BUCKET)
    out = run(table, FakeBedrock(load_fixture("nova/converse_tool_use.json")), writer=writer)
    assert out["analysis"]["added"][0]["item"] == "milk"
    assert table.get(account_pk(ACCOUNT), DOOR_SK)["nova_usd"] == 0.000653
    usage = table.get(account_pk(ACCOUNT), "USAGE#2026-08-14")
    assert (usage["calls"], usage["input_tokens"], usage["usd"]) == (1, 1180, 0.000653)


# Off
def test_tracing_off_writes_no_nova_traces(table):
    out = run(
        table, FakeBedrock(load_fixture("nova/converse_tool_use.json")), writer=NullTraceWriter()
    )
    assert "analysis" in out
    assert debug_keys() == []
    assert table.get(account_pk(ACCOUNT), TRACE_SK)["nova_calls"] == []


def test_without_a_writer_nothing_is_traced(table):
    out = analyze_task(
        NovaAnalyzer(FakeBedrock(load_fixture("nova/converse_tool_use.json"))),
        boto3.client("s3"),
        table,
        BUCKET,
        STATE,
    )
    assert "analysis" in out
    assert debug_keys() == []
