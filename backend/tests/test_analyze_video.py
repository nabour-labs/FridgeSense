"""fridge-change-analysis: the analysis video in the analyze task, and proof from its moments."""

import copy
import json
import logging

import boto3
import pytest
from botocore.exceptions import ClientError

from fridgesense.analysis import BedrockRetryable, NovaAnalyzer
from fridgesense.inventory import analyze_task
from fridgesense.table import FridgeTable, account_pk
from tests.conftest import BUCKET, jpeg, load_fixture

ACCOUNT = "ava1.ring.account.A1"
DOOR_SK = "DOOR#2026-08-14T13:53:16.000Z#ava1.ring.device.D1"
PREFIX = f"accounts/{ACCOUNT}/devices/D1/events/1/"
KEYS = [f"{PREFIX}still-{n}.jpg" for n in range(1, 5)]
VIDEO_KEY = f"{PREFIX}analysis.mp4"
VIDEO = b"\x00\x00\x00\x18ftypmp42 pretend video"
T = 1786715600000
STATE = {
    "account_id": ACCOUNT,
    "door_sk": DOOR_SK,
    "still_keys": KEYS,
    "still_ms": [T, T + 3000, T + 6000, T + 9500],
    "analysis_video": {"key": VIDEO_KEY, "start_ms": T, "frame_ms": 500, "frames": 20},
    "outcome": "door_open",
}


class FakeBedrock:
    """Answers each converse call with the next queued response (or raises it)."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[dict] = []

    def converse(self, **request):
        self.requests.append(request)
        answer = self.responses.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "Converse")


def with_moments(*moments_per_item):
    resp = copy.deepcopy(load_fixture("nova/converse_tool_use.json"))
    items = resp["output"]["message"]["content"][0]["toolUse"]["input"]["items"]
    for it, moments in zip(items, moments_per_item, strict=True):
        it["moments"] = moments
    return resp


@pytest.fixture
def table(aws):
    s3 = boto3.client("s3")
    for k in KEYS:
        s3.put_object(Bucket=BUCKET, Key=k, Body=jpeg(0.8))
    s3.put_object(Bucket=BUCKET, Key=VIDEO_KEY, Body=VIDEO, Tagging="transient=true")
    t = FridgeTable()
    t.put({"pk": account_pk(ACCOUNT), "sk": DOOR_SK, "status": "analyzing"})
    return t


def run(table, client, state=STATE):
    return analyze_task(NovaAnalyzer(client), boto3.client("s3"), table, BUCKET, state)


def video_exists() -> bool:
    listing = boto3.client("s3").list_objects_v2(Bucket=BUCKET, Prefix=VIDEO_KEY)
    return listing.get("KeyCount", 0) > 0


def media(request: dict) -> tuple[list[bytes], list[bytes]]:
    content = request["messages"][0]["content"]
    videos = [c["video"]["source"]["bytes"] for c in content if "video" in c]
    images = [c["image"]["source"]["bytes"] for c in content if "image" in c]
    return videos, images


def test_video_sent_instead_of_stills(table):
    client = FakeBedrock(load_fixture("nova/converse_tool_use.json"))
    run(table, client)
    videos, images = media(client.requests[0])
    assert videos == [VIDEO]
    assert images == []


# Video object missing
def test_video_object_missing(table, caplog):
    boto3.client("s3").delete_object(Bucket=BUCKET, Key=VIDEO_KEY)
    caplog.set_level(logging.INFO)
    client = FakeBedrock(load_fixture("nova/converse_tool_use.json"))
    out = run(table, client)
    videos, images = media(client.requests[0])
    assert videos == [] and len(images) == 4
    assert out["analysis"]["added"][0]["item"] == "milk"
    assert any('"analysis_video_missing"' in r.getMessage() for r in caplog.records)


# Analysis video deleted after analysis
@pytest.mark.parametrize(
    "responses",
    [
        [load_fixture("nova/converse_tool_use.json")],
        [load_fixture("nova/converse_end_turn.json")] * 2,
        [error("ValidationException")],
    ],
    ids=["valid", "invalid-twice", "rejected"],
)
def test_analysis_video_deleted_after_analysis(table, responses):
    run(table, FakeBedrock(*responses))
    assert not video_exists()


# Analysis video deleted when the step is retried
def test_video_kept_for_a_retried_step(table):
    with pytest.raises(BedrockRetryable):
        run(table, FakeBedrock(error("ThrottlingException")))
    assert video_exists()
    run(table, FakeBedrock(load_fixture("nova/converse_tool_use.json")))
    assert not video_exists()


def test_stills_path_without_a_video(table):
    state = {k: v for k, v in STATE.items() if k != "analysis_video"}
    client = FakeBedrock(load_fixture("nova/converse_tool_use.json"))
    run(table, client, state)
    videos, images = media(client.requests[0])
    assert videos == [] and len(images) == 4
    assert video_exists()  # not this run's video: left to the lifecycle rule


# Proof mapped from video seconds
def test_proof_mapped_from_video_seconds(table):
    client = FakeBedrock(with_moments([7, 12], [19.5]))
    out = run(table, client)
    assert out["analysis"]["added"][0]["images"] == [2, 3]  # T+3500 -> still 2, T+6000 -> 3
    assert out["analysis"]["removed"][0]["images"] == [4]  # T+9750 -> still 4


# Video moments past the end
def test_video_moments_past_the_end(table):
    client = FakeBedrock(with_moments([-1, 25, "3"], [20]))
    out = run(table, client)
    assert out["analysis"]["added"][0]["images"] == []
    assert out["analysis"]["removed"][0]["images"] == []
    assert len(client.requests) == 1


def test_video_cost_logged(table, caplog):
    caplog.set_level(logging.INFO)
    run(table, FakeBedrock(load_fixture("nova/converse_tool_use.json")))
    [line] = [json.loads(r.getMessage()) for r in caplog.records if "nova_cost" in r.getMessage()]
    assert line["door_sk"] == DOOR_SK
