"""The pipeline Lambda driven in state-machine order, end to end (all external calls stubbed)."""

import io
import json
import logging
import time

import boto3
import httpx
import pytest
import respx
from botocore.exceptions import ClientError
from botocore.stub import Stubber
from PIL import Image

from fridgesense import face_blur
from fridgesense.door_events import crop_still
from fridgesense.faces import blur_regions
from fridgesense.handlers import pipeline
from fridgesense.ring import API_BASE
from fridgesense.store import Tokens, TokenStore
from fridgesense.table import FridgeTable, account_pk
from tests.conftest import BUCKET, checkerboard_jpeg, color_jpeg, load_fixture

ACCOUNT = "ava1.ring.account.A1"
DEVICE = "ava1.ring.device.D1"
HISTORY = f"{API_BASE}/v1/history/devices/{DEVICE}/events"
DOWNLOAD = f"{API_BASE}/v1/devices/{DEVICE}/media/image/download"
CLIP = f"{API_BASE}/v1/devices/{DEVICE}/media/video/download"
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
    monkeypatch.setenv("DOOR_ZONES", "0,0,1,1")
    monkeypatch.setenv("DOOR_THRESHOLD", "0.02")
    monkeypatch.delenv("STILL_CROP", raising=False)
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


OPEN = color_jpeg((128, 128, 128), [((0.2, 0.2, 0.4, 0.5), (40, 90, 200))])  # lit fridge
CLOSED = color_jpeg((128, 128, 128))  # grey steel doors


def no_clip():
    """Ring has no clip for the event: the door check falls back to sampled stills."""
    return respx.post(CLIP).respond(416, json={"code": "MEDIA_NOT_FOUND"})


def ring_serves(still: bytes):
    respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events.json"))
    no_clip()
    respx.post(DOWNLOAD).mock(
        side_effect=lambda r: httpx.Response(303, headers={"Location": "https://dl.example.com/x"})
    )
    respx.get("https://dl.example.com/x").respond(200, content=still)


def step(task: str, state: dict) -> dict:
    return pipeline.handler({**state, "task": task}, None)


@respx.mock
def test_door_opening_updates_inventory(env, faces):
    env.add_response("converse", load_fixture("nova/converse_tool_use.json"))
    no_faces(faces)
    ring_serves(OPEN)
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

    # pipeline-debug-traces: the run leaves its door trace and one Nova call trace
    debug = f"accounts/{ACCOUNT}/devices/{DEVICE}/events/{state['window']['start_ms']}/debug/"
    listing = boto3.client("s3").list_objects_v2(Bucket=BUCKET, Prefix=debug)
    names = {o["Key"].removeprefix(debug) for o in listing["Contents"]}
    assert "door.json" in names
    assert len([n for n in names if n.startswith("nova-") and n.endswith("-1.json")]) == 1
    [trace] = table.query(ACCOUNT, "TRACE#")
    assert trace["outcome"] == "door_open"
    [call] = trace["nova_calls"]
    assert (call["outcome"], call["input_tokens"], call["latency_ms"]) == ("ok", 1180, 2140)


@respx.mock
def test_tracing_off_leaves_no_debug_files(env, faces, monkeypatch):
    monkeypatch.setenv("DEBUG_TRACES", "false")
    env.add_response("converse", load_fixture("nova/converse_tool_use.json"))
    no_faces(faces)
    ring_serves(OPEN)
    state = step("analyze", step("fetch_stills", step("find_window", RUN_INPUT)))
    assert "analysis" in state
    listing = boto3.client("s3").list_objects_v2(Bucket=BUCKET)
    assert not any("/debug/" in o["Key"] for o in listing["Contents"])
    assert FridgeTable().query(ACCOUNT, "TRACE#") == []


@respx.mock
def test_closed_door_stops_before_nova(env, faces):
    ring_serves(CLOSED)  # no DetectFaces responses queued: a call would fail the stubber
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
    monkeypatch.setenv("DOOR_THRESHOLD", "0")  # the checkerboard has no colour; 0 lets it through
    downloaded = checkerboard_jpeg()
    respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events.json"))
    no_clip()
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


def capture_converse(env) -> list[dict]:
    sent: list[dict] = []
    pipeline.bedrock_client().meta.events.register(
        "provide-client-params.bedrock-runtime.Converse", lambda params, **kw: sent.append(params)
    )
    env.add_response("converse", load_fixture("nova/converse_tool_use.json"))
    return sent


# Analysis sees the cropped still
@respx.mock
def test_analysis_sees_the_cropped_still(env, faces, monkeypatch):
    monkeypatch.setenv("STILL_CROP", "0.25,0.0,0.5,1.0")
    ring_serves(OPEN)  # 320x180
    cropped = crop_still(OPEN, (0.25, 0.0, 0.5, 1.0))
    for _ in range(4):  # detection gets the crop, not the download
        faces.add_response(
            "detect_faces",
            {"FaceDetails": []},
            {"Image": {"Bytes": cropped}, "Attributes": ["DEFAULT"]},
        )
    sent = capture_converse(env)

    state = step("fetch_stills", step("find_window", RUN_INPUT))
    assert state["outcome"] == "door_open"
    step("analyze", state)

    [request] = sent
    images = [
        c["image"]["source"]["bytes"] for c in request["messages"][0]["content"] if "image" in c
    ]
    s3 = boto3.client("s3")
    stored = [s3.get_object(Bucket=BUCKET, Key=k)["Body"].read() for k in state["still_keys"]]
    assert images == stored
    assert all(Image.open(io.BytesIO(i)).size == (160, 180) for i in images)


# Fridge area wins over STILL_CROP (the pipeline loads the device's fridge area)
@respx.mock
def test_pipeline_crops_to_the_fridge_area(env, faces, monkeypatch):
    from fridgesense import fridge_area

    monkeypatch.setenv("STILL_CROP", "0.25,0.0,0.5,1.0")
    area = {"x": 0.25, "y": 0.2, "width": 0.5, "height": 0.6}
    fridge_area.save(FridgeTable(), ACCOUNT, DEVICE, b"\xff\xd8\xff", area, 1786715600000)
    ring_serves(OPEN)  # 320x180
    box = fridge_area.analysis_box((0.25, 0.2, 0.5, 0.6), None)
    cropped = crop_still(OPEN, box)
    for _ in range(4):
        faces.add_response(
            "detect_faces",
            {"FaceDetails": []},
            {"Image": {"Bytes": cropped}, "Attributes": ["DEFAULT"]},
        )
    state = step("fetch_stills", step("find_window", RUN_INPUT))
    assert state["outcome"] == "door_open"
    body = boto3.client("s3").get_object(Bucket=BUCKET, Key=state["still_keys"][0])["Body"].read()
    assert Image.open(io.BytesIO(body)).size == (192, 118)


def blurring_off() -> None:
    face_blur.save(FridgeTable(), ACCOUNT, False, now_ms=1786715500000)


def no_cost_lines(caplog) -> bool:
    return not any('"face_detect_cost"' in r.getMessage() for r in caplog.records)


# Blurring off, no crop box (and Analysis while blurring is off)
@respx.mock
def test_blurring_off_no_crop_box(env, faces, caplog):
    caplog.set_level(logging.INFO)
    blurring_off()
    ring_serves(OPEN)  # no DetectFaces responses queued: a call would fail the stubber
    sent = capture_converse(env)

    state = step("fetch_stills", step("find_window", RUN_INPUT))
    assert state["outcome"] == "door_open"
    step("analyze", state)

    s3 = boto3.client("s3")
    stored = [s3.get_object(Bucket=BUCKET, Key=k)["Body"].read() for k in state["still_keys"]]
    assert len(stored) == 4 and all(b == OPEN for b in stored)
    [request] = sent
    images = [
        c["image"]["source"]["bytes"] for c in request["messages"][0]["content"] if "image" in c
    ]
    assert images == stored
    assert no_cost_lines(caplog)


# Blurring off, with a crop box
@respx.mock
def test_blurring_off_with_a_crop_box(env, faces, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("STILL_CROP", "0.25,0.0,0.5,1.0")
    blurring_off()
    ring_serves(OPEN)
    state = step("fetch_stills", step("find_window", RUN_INPUT))
    assert state["outcome"] == "door_open"
    s3 = boto3.client("s3")
    stored = [s3.get_object(Bucket=BUCKET, Key=k)["Body"].read() for k in state["still_keys"]]
    assert stored == [crop_still(OPEN, (0.25, 0.0, 0.5, 1.0))] * 4
    assert no_cost_lines(caplog)


# Read fails in the pipeline
@respx.mock
def test_setting_read_fails_in_the_pipeline(env, faces, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    blurring_off()
    get = FridgeTable.get

    def failing_get(self, pk, sk):
        if sk == face_blur.SETTING_SK:
            raise ClientError(
                {"Error": {"Code": "ProvisionedThroughputExceededException"}}, "GetItem"
            )
        return get(self, pk, sk)

    monkeypatch.setattr(FridgeTable, "get", failing_get)
    no_faces(faces)  # detection runs on every still, as when the setting is on
    ring_serves(OPEN)
    state = step("fetch_stills", step("find_window", RUN_INPUT))
    assert state["outcome"] == "door_open"
    assert any('"face_blur_setting_failed"' in r.getMessage() for r in caplog.records)


# Invalid crop config
@respx.mock
def test_invalid_crop_config_fails_before_ring(env, monkeypatch):
    monkeypatch.setenv("STILL_CROP", "0.8,0,0.5,1")
    download = respx.post(DOWNLOAD).respond(303, headers={"Location": "https://dl.example.com/x"})
    state = {
        **RUN_INPUT,
        "window": {"status": "ready", "start_ms": 1, "end_ms": 2, "ring_event_id": None},
    }
    with pytest.raises(ValueError, match="STILL_CROP"):
        step("fetch_stills", state)
    assert not download.called


# Invalid zone config
@respx.mock
def test_invalid_zone_config_fails_before_ring(env, monkeypatch):
    monkeypatch.setenv("DOOR_ZONES", "0,0,1")
    download = respx.post(DOWNLOAD).respond(303, headers={"Location": "https://dl.example.com/x"})
    state = {
        **RUN_INPUT,
        "window": {"status": "ready", "start_ms": 1, "end_ms": 2, "ring_event_id": None},
    }
    with pytest.raises(ValueError, match="DOOR_ZONES"):
        step("fetch_stills", state)
    assert not download.called


# Invalid interval config
@respx.mock
@pytest.mark.parametrize("value", ["0", "-500", "fast"])
def test_invalid_interval_config_fails_before_ring(env, monkeypatch, value):
    monkeypatch.setenv("STILL_INTERVAL_MS", value)
    download = respx.post(DOWNLOAD).respond(303, headers={"Location": "https://dl.example.com/x"})
    state = {
        **RUN_INPUT,
        "window": {"status": "ready", "start_ms": 1, "end_ms": 2, "ring_event_id": None},
    }
    with pytest.raises(ValueError, match="STILL_INTERVAL_MS"):
        step("fetch_stills", state)
    assert not download.called


# Door check on the event clip, through the handler (frames every 500 ms by default)
@respx.mock
def test_door_opening_from_the_clip(env, faces, tmp_path, monkeypatch):
    from tests.clip_video import door_clip

    monkeypatch.delenv("DOOR_FRAME_INTERVAL_MS", raising=False)
    env.add_response("converse", load_fixture("nova/converse_tool_use.json"))
    no_faces(faces)
    respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events.json"))
    clip = door_clip(tmp_path / "c.mp4", [(4000, 12_500)], duration_ms=25_000).read_bytes()
    respx.post(CLIP).respond(303, headers={"Location": "https://clip.example.com/c.mp4"})
    respx.get("https://clip.example.com/c.mp4").respond(200, content=clip)
    stills = respx.post(DOWNLOAD).mock(
        side_effect=lambda r: httpx.Response(303, headers={"Location": "https://dl.example.com/x"})
    )
    respx.get("https://dl.example.com/x").respond(200, content=OPEN)
    state = step("fetch_stills", step("find_window", RUN_INPUT))
    assert state["outcome"] == "door_open"
    assert stills.call_count == 0  # the picked clip frames are the stills
    event = FridgeTable().get(account_pk(ACCOUNT), state["door_sk"])
    assert event["opened_at"] == "2026-08-14T13:53:20.000Z"
    assert event["closed_at"] == "2026-08-14T13:53:28.500Z"
    # the door trace keeps every checked frame
    debug = f"accounts/{ACCOUNT}/devices/{DEVICE}/events/{state['window']['start_ms']}/debug/"
    listing = boto3.client("s3").list_objects_v2(Bucket=BUCKET, Prefix=debug)
    raws = [
        o["Key"] for o in listing["Contents"] if o["Key"].removeprefix(debug).startswith("raw-")
    ]
    assert len(raws) == 50


# Invalid frame interval
@respx.mock
@pytest.mark.parametrize("value", ["0", "-5", "abc"])
def test_invalid_frame_interval_fails_before_ring(env, monkeypatch, value):
    monkeypatch.setenv("DOOR_FRAME_INTERVAL_MS", value)
    clip = respx.post(CLIP).respond(403)
    download = respx.post(DOWNLOAD).respond(303, headers={"Location": "https://dl.example.com/x"})
    state = {
        **RUN_INPUT,
        "window": {"status": "ready", "start_ms": 1, "end_ms": 2, "ring_event_id": None},
    }
    with pytest.raises(ValueError, match="DOOR_FRAME_INTERVAL_MS"):
        step("fetch_stills", state)
    assert not clip.called and not download.called


def run_setup_for(device: str) -> None:
    """Setup on `device` whose single zone is the right 40%: colourful there means open."""
    from fridgesense import door_calibration

    right = {"x": 0.6, "y": 0.0, "width": 0.4, "height": 1.0}
    lit = color_jpeg((128, 128, 128), [((0.6, 0.0, 0.4, 1.0), (40, 90, 200))])
    z = door_calibration.add_zone(
        FridgeTable(), ACCOUNT, device, "Doors", right, 1, source="clip"
    ).sk
    door_calibration.add_reference(FridgeTable(), ACCOUNT, device, lit, z, "open", 1, source="clip")
    door_calibration.add_reference(
        FridgeTable(), ACCOUNT, device, CLOSED, z, "closed", 2, source="clip"
    )
    door_calibration.run(FridgeTable(), ACCOUNT, device, now_ms=3)


# Setup result used for the device (through the pipeline handler and the table)
@respx.mock
def test_pipeline_uses_the_devices_setup(env, faces, monkeypatch):
    monkeypatch.setenv("DOOR_ZONES", "0,0,0.4,1")  # would miss the right-hand light
    run_setup_for(DEVICE)
    no_faces(faces)
    ring_serves(color_jpeg((128, 128, 128), [((0.6, 0.0, 0.4, 1.0), (40, 90, 200))]))
    state = step("fetch_stills", step("find_window", RUN_INPUT))
    assert state["outcome"] == "door_open"


# Setup kept per device
@respx.mock
def test_setup_kept_per_device(env, faces, monkeypatch):
    monkeypatch.setenv("DOOR_ZONES", "0,0,0.4,1")
    run_setup_for("ava1.ring.device.D2")
    ring_serves(color_jpeg((128, 128, 128), [((0.6, 0.0, 0.4, 1.0), (40, 90, 200))]))
    state = step("fetch_stills", step("find_window", RUN_INPUT))
    assert state["outcome"] == "not_door"  # D1 has no setup: DOOR_ZONES misses the light


# fridge-monitoring: a run for a paused camera stops before any Ring media download
@respx.mock
def test_paused_camera_stops_before_ring_media(env, faces):
    from fridgesense import monitoring

    ring_serves(OPEN)  # no DetectFaces or Converse responses queued: a call would fail
    state = step("find_window", RUN_INPUT)
    monitoring.set_paused(FridgeTable(), ACCOUNT, DEVICE, True, 1786715600000)
    state = step("fetch_stills", state)
    assert state["outcome"] == "paused"
    assert not respx.routes[2].called  # image download
    assert FridgeTable().query(ACCOUNT, "DOOR#") == []


# door-event-detection: Analysis video never shown (clip path, face blurring on, tracing on)
@respx.mock
def test_analysis_video_never_shown(env, faces, monkeypatch, tmp_path):
    from fridgesense.handlers import api
    from fridgesense.store import load_app_config
    from tests.api_helpers import call, configure, sign_in
    from tests.clip_video import door_clip

    respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events.json"))
    clip = door_clip(tmp_path / "served.mp4", [(4000, 12_500)], duration_ms=25_000).read_bytes()
    respx.post(CLIP).respond(303, headers={"Location": "https://clip.example.com/c.mp4"})
    respx.get("https://clip.example.com/c.mp4").respond(200, content=clip)
    no_faces(faces)
    env.add_response("converse", load_fixture("nova/converse_tool_use.json"))

    state = step("fetch_stills", step("find_window", RUN_INPUT))
    assert state["outcome"] == "door_open"
    assert state["analysis_video"]["key"].endswith("/analysis.mp4")
    state = step("save", step("analyze", state))

    s3 = boto3.client("s3")
    prefix = state["analysis_video"]["key"].rsplit("/", 1)[0] + "/"
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)["Contents"]]
    assert not any(k.endswith("analysis.mp4") for k in keys)  # deleted after the analysis
    event = FridgeTable().get(account_pk(ACCOUNT), state["door_sk"])
    assert "analysis.mp4" not in json.dumps(event, default=str)

    monkeypatch.setattr(api, "now", lambda: 1786715700.0)
    configure()
    load_app_config(refresh=True)
    owner = sign_in()
    status, events = call("GET", "/api/events", token=owner)
    assert status == 200 and events["events"]
    assert "analysis.mp4" not in json.dumps(events)
    status, trace = call("GET", f"/api/debug/motions/{events['events'][0]['id']}", token=owner)
    assert status == 200
    assert "analysis.mp4" not in json.dumps(trace)
    videos = [b for n in trace["nova"] for b in n["request"]["content"] if b["type"] == "video"]
    assert videos and all("url" not in v and "key" not in v for v in videos)
