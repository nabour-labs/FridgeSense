"""The pipeline Lambda driven in state-machine order, end to end (all external calls stubbed)."""

import time

import boto3
import httpx
import pytest
import respx
from botocore.stub import Stubber

from fridgesense.faces import blur_regions
from fridgesense.handlers import pipeline
from fridgesense.ring import API_BASE
from fridgesense.store import Tokens, TokenStore
from fridgesense.table import FridgeTable, account_pk
from tests.conftest import BUCKET, checkerboard_jpeg, jpeg, load_fixture

ACCOUNT = "ava1.ring.account.A1"
DEVICE = "ava1.ring.device.D1"
HISTORY = f"{API_BASE}/v1/history/devices/{DEVICE}/events"
DOWNLOAD = f"{API_BASE}/v1/devices/{DEVICE}/media/image/download"
RUN_INPUT = {
    "account_id": ACCOUNT,
    "device_id": DEVICE,
    "timestamp_ms": 1786715596787,
    "request_id": "R1",
}


@pytest.fixture
def faces(aws, monkeypatch):
    """Stubbed Rekognition behind the pipeline handler."""
    client = boto3.client("rekognition", region_name="us-east-1")
    monkeypatch.setattr(pipeline, "rekognition_client", lambda: client)
    with Stubber(client) as stub:
        yield stub
        stub.assert_no_pending_responses()


def no_faces(faces, count: int = 4) -> None:
    for _ in range(count):
        faces.add_response("detect_faces", {"FaceDetails": []})


@pytest.fixture
def env(aws, monkeypatch, faces):
    monkeypatch.setenv("DOOR_BOX", "0,0,1,1")
    monkeypatch.setenv("DOOR_THRESHOLD", "0.5")
    monkeypatch.setattr(pipeline, "sleep", lambda s: None)
    TokenStore().save(
        Tokens(
            account_id=ACCOUNT,
            access_token="at1",
            refresh_token="rt1",
            expires_at=int(time.time()) + 3600,
            link_status="linked",
        )
    )
    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
    monkeypatch.setattr(pipeline, "bedrock_client", lambda: bedrock)
    with Stubber(bedrock) as stub:
        yield stub


def ring_serves(brightness: float):
    respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events.json"))
    respx.post(DOWNLOAD).mock(
        side_effect=lambda r: httpx.Response(303, headers={"Location": "https://dl.example.com/x"})
    )
    respx.get("https://dl.example.com/x").respond(200, content=jpeg(brightness))


def step(task: str, state: dict) -> dict:
    return pipeline.handler({**state, "task": task}, None)


@respx.mock
def test_door_opening_updates_inventory(env, faces):
    env.add_response("converse", load_fixture("nova/converse_tool_use.json"))
    no_faces(faces)
    ring_serves(0.8)
    state = step("find_window", RUN_INPUT)
    assert state["window"]["status"] == "ready"
    state = step("fetch_stills", state)
    assert state["outcome"] == "door_open"
    state = step("analyze", state)
    state = step("save", state)
    assert state["outcome"] == "saved"
    assert "task" not in state

    table = FridgeTable()
    milk = table.get(account_pk(ACCOUNT), "ITEM#milk")
    assert milk["quantity"] == 1
    event = table.get(account_pk(ACCOUNT), state["door_sk"])
    assert event["status"] == "done"
    assert event["nova_usd"] == 0.000653
    assert event["closed_at"] == "2026-08-14T13:53:41.000Z"
    env.assert_no_pending_responses()


@respx.mock
def test_closed_door_stops_before_nova(env, faces):
    no_faces(faces)
    ring_serves(0.1)
    state = step("fetch_stills", step("find_window", RUN_INPUT))
    assert state["outcome"] == "not_door"
    assert FridgeTable().query(ACCOUNT, "DOOR#") == []
    assert FridgeTable().query(ACCOUNT, "ITEM#") == []


def test_unknown_task_is_an_error(env):
    with pytest.raises(ValueError):
        step("dance", RUN_INPUT)


@respx.mock
def test_state_machine_payload_shape(env):
    """The state machine sends {"task": ..., "input": <run state>}."""
    respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events.json"))
    out = pipeline.handler({"task": "find_window", "input": RUN_INPUT}, None)
    assert out["window"]["status"] == "ready"
    assert out["account_id"] == ACCOUNT and "input" not in out


# Analysis receives blurred bytes
@respx.mock
def test_analysis_receives_blurred_bytes(env, faces, monkeypatch):
    monkeypatch.setenv("DOOR_THRESHOLD", "0.3")  # the checkerboard's mean brightness is ~0.5
    downloaded = checkerboard_jpeg()
    respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events.json"))
    respx.post(DOWNLOAD).mock(
        side_effect=lambda r: httpx.Response(303, headers={"Location": "https://dl.example.com/x"})
    )
    respx.get("https://dl.example.com/x").respond(200, content=downloaded)
    one_face = load_fixture("rekognition/detect_faces_one.json")
    faces.add_response(
        "detect_faces", one_face, {"Image": {"Bytes": downloaded}, "Attributes": ["DEFAULT"]}
    )
    no_faces(faces, 3)
    sent = []
    bedrock = pipeline.bedrock_client()
    bedrock.meta.events.register(
        "provide-client-params.bedrock-runtime.Converse", lambda params, **kw: sent.append(params)
    )
    env.add_response("converse", load_fixture("nova/converse_tool_use.json"))

    state = step("fetch_stills", step("find_window", RUN_INPUT))
    assert state["outcome"] == "door_open"
    step("analyze", state)

    [request] = sent
    content = request["messages"][0]["content"]
    images = [c["image"]["source"]["bytes"] for c in content if "image" in c]
    s3 = boto3.client("s3")
    still_1 = s3.get_object(Bucket=BUCKET, Key=state["still_keys"][0])["Body"].read()
    face = one_face["FaceDetails"][0]["BoundingBox"]
    assert still_1 == blur_regions(
        downloaded, [(face["Left"], face["Top"], face["Width"], face["Height"])]
    )
    assert images[0] == still_1
    assert images[0] != downloaded
