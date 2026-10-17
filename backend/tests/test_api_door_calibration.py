"""door-calibration: the camera snapshot and door setup routes on the app API."""

import base64
import io
import json

import boto3
import pytest
import respx
from botocore.stub import Stubber
from PIL import Image

from fridgesense.devices import Device, DeviceRepository
from fridgesense.door_events import iso_utc
from fridgesense.handlers import api
from fridgesense.ring import API_BASE
from fridgesense.store import load_app_config
from tests.api_helpers import ACCOUNT, NOW, call, configure, link_account, sign_in
from tests.conftest import color_jpeg

DEVICE = "ava1.ring.device.D1"
DOWNLOAD = f"{API_BASE}/v1/devices/{DEVICE}/media/image/download"
LINK = "https://dl.example.com/snap"
GREY = (128, 128, 128)
LEFT = {"x": 0, "y": 0, "width": 0.5, "height": 1}
OPEN = color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), (40, 90, 200))], size=(200, 100))
CLOSED = color_jpeg(GREY, size=(200, 100))
NOT_FOUND_CAMERA = (409, {"error": "no camera found"})
READ_ONLY = (403, {"error": "read-only"})


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


@pytest.fixture
def faces(aws, monkeypatch):
    client = boto3.client("rekognition", region_name="us-east-1")
    monkeypatch.setattr(api, "rekognition_client", lambda: client)
    with Stubber(client) as stub:
        yield stub


@pytest.fixture
def tokens(aws, faces, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    monkeypatch.setattr(api, "sleep", lambda s: None)
    monkeypatch.delenv("DOOR_ZONES", raising=False)
    monkeypatch.delenv("DOOR_THRESHOLD", raising=False)
    link_account()
    configure(demo_passcode="look-only")
    load_app_config(refresh=True)
    DeviceRepository().replace(ACCOUNT, [Device(DEVICE, "Fridge")])
    return {"owner": sign_in(), "viewer": sign_in("look-only")}


@pytest.fixture
def owner(tokens):
    return tokens["owner"]


def add(token, image=OPEN, box=LEFT, status="open"):
    return call(
        "POST",
        "/api/door-calibration/references",
        {"image": b64(image), "box": box, "status": status},
        token,
    )


# Snapshot taken (through the API)
@respx.mock
def test_snapshot_taken(owner, faces):
    post = respx.post(DOWNLOAD).respond(303, headers={"Location": LINK})
    respx.get(LINK).respond(200, content=color_jpeg(size=(1920, 1080)))
    faces.add_response("detect_faces", {"FaceDetails": []})
    status, body = call("POST", "/api/camera/snapshot", token=owner)
    assert status == 200
    assert json.loads(post.calls.last.request.content)["timestamp"] == int(NOW * 1000) - 3000
    assert Image.open(io.BytesIO(base64.b64decode(body["image"]))).size == (960, 540)
    assert body["captured_at"] == iso_utc(int(NOW * 1000) - 3000)


# No recent footage
@respx.mock
def test_snapshot_no_recent_footage(owner):
    respx.post(DOWNLOAD).respond(416)
    respx.get(f"{API_BASE}/v1/history/devices/{DEVICE}/events").respond(200, json={"data": []})
    assert call("POST", "/api/camera/snapshot", token=owner) == (
        409,
        {"error": "no recent footage"},
    )


# Camera or face detection unavailable
@respx.mock
def test_snapshot_camera_unavailable(owner):
    respx.post(DOWNLOAD).respond(500)
    assert call("POST", "/api/camera/snapshot", token=owner) == (
        502,
        {"error": "camera unavailable"},
    )


@respx.mock
def test_snapshot_face_detection_unavailable(owner, faces):
    respx.post(DOWNLOAD).respond(303, headers={"Location": LINK})
    respx.get(LINK).respond(200, content=color_jpeg(size=(960, 540)))
    faces.add_client_error("detect_faces", "InternalServerError")
    assert call("POST", "/api/camera/snapshot", token=owner) == (
        502,
        {"error": "camera unavailable"},
    )


# No device discovered (every route)
@pytest.mark.parametrize(
    "method, path",
    [
        ("POST", "/api/camera/snapshot"),
        ("GET", "/api/door-calibration"),
        ("POST", "/api/door-calibration/references"),
        ("DELETE", "/api/door-calibration/references/abc"),
        ("POST", "/api/door-calibration/run"),
    ],
)
def test_no_device_discovered(owner, method, path):
    DeviceRepository().replace(ACCOUNT, [])
    assert call(method, path, {}, owner) == NOT_FOUND_CAMERA


# Nothing set up yet
def test_nothing_set_up_yet(tokens):
    status, body = call("GET", "/api/door-calibration", token=tokens["viewer"])
    assert status == 200
    assert body == {
        "device_id": DEVICE,
        "references": [],
        "setup": None,
        "defaults": {
            "zones": [
                {"x": 0.38, "y": 0.32, "width": 0.21, "height": 0.30},
                {"x": 0.455, "y": 0.60, "width": 0.12, "height": 0.18},
            ],
            "threshold": 0.01,
        },
    }


def test_defaults_from_config(tokens, monkeypatch):
    monkeypatch.setenv("DOOR_ZONES", "0,0,0.5,1")
    monkeypatch.setenv("DOOR_THRESHOLD", "0.05")
    _, body = call("GET", "/api/door-calibration", token=tokens["viewer"])
    assert body["defaults"] == {
        "zones": [{"x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0}],
        "threshold": 0.05,
    }


# No token
def test_no_token(aws):
    assert call("GET", "/api/door-calibration") == (401, {"error": "sign in"})


# Viewer cannot change the setup
@respx.mock
@pytest.mark.parametrize(
    "method, path",
    [
        ("POST", "/api/camera/snapshot"),
        ("POST", "/api/door-calibration/references"),
        ("DELETE", "/api/door-calibration/references/abc"),
        ("POST", "/api/door-calibration/run"),
    ],
)
def test_viewer_cannot_change_the_setup(tokens, method, path):
    ring = respx.post(DOWNLOAD).respond(303, headers={"Location": LINK})
    assert call(method, path, {}, tokens["viewer"]) == READ_ONLY
    assert not ring.called
    assert call("GET", "/api/door-calibration", token=tokens["owner"])[1]["references"] == []


# Reference added
def test_reference_added(owner):
    box = {"x": 0.38, "y": 0.32, "width": 0.21, "height": 0.30}
    status, body = add(owner, color_jpeg(size=(960, 540)), box)
    assert status == 200
    [ref] = body["references"]
    assert ref["id"]
    assert ref["box"] == box
    assert ref["status"] == "open"
    assert ref["score"] is None
    assert ref["image"] == b64(color_jpeg(size=(960, 540)))
    assert ref["created_at"].endswith("Z")


# Invalid reference rejected
@pytest.mark.parametrize(
    "body, error",
    [
        (
            {"image": b64(b"\x89PNG\r\n\x1a\n"), "box": LEFT, "status": "open"},
            "image must be a JPEG of at most 300 KB",
        ),
        (
            {
                "image": b64(OPEN),
                "box": {"x": 0.9, "y": 0, "width": 0.2, "height": 1},
                "status": "open",
            },
            "box must be inside the image and at least 2% wide and tall",
        ),
        ({"image": b64(OPEN), "box": LEFT, "status": "ajar"}, "status must be open or closed"),
    ],
)
def test_invalid_reference_rejected(owner, body, error):
    assert call("POST", "/api/door-calibration/references", body, owner) == (400, {"error": error})
    assert call("GET", "/api/door-calibration", token=owner)[1]["references"] == []


# Reference limit
def test_reference_limit(owner, monkeypatch):
    for n in range(12):
        monkeypatch.setattr(api, "now", lambda n=n: NOW + n)
        assert add(owner)[0] == 200
    assert add(owner) == (409, {"error": "at most 12 door references"})


# Reference deleted
def test_reference_deleted(owner):
    ref_id = add(owner)[1]["references"][0]["id"]
    status, body = call("DELETE", f"/api/door-calibration/references/{ref_id}", token=owner)
    assert status == 200 and body["references"] == []
    assert call("DELETE", f"/api/door-calibration/references/{ref_id}", token=owner) == (
        404,
        {"error": "not found"},
    )


# Setup from one open and one closed reference (through the API)
def test_run_setup(owner, monkeypatch):
    add(owner, OPEN, LEFT, "open")
    monkeypatch.setattr(api, "now", lambda: NOW + 1)
    add(owner, CLOSED, LEFT, "closed")
    monkeypatch.setattr(api, "now", lambda: NOW + 2)
    status, body = call("POST", "/api/door-calibration/run", token=owner)
    assert status == 200
    [zone] = body["setup"]["zones"]
    assert {k: zone[k] for k in ("x", "y", "width", "height", "feature", "direction")} == {
        "x": 0.0,
        "y": 0.0,
        "width": 0.5,
        "height": 1.0,
        "feature": "blue",
        "direction": "above",
    }
    assert zone["threshold"] == pytest.approx(0.05, abs=0.005)
    assert zone["margin"] == pytest.approx(0.1, abs=0.005)
    assert body["setup"]["stale"] is False
    assert body["setup"]["ran_at"].endswith("Z")
    assert [r["score"] for r in body["references"]] == [
        pytest.approx(0.1, abs=0.005),
        pytest.approx(0.0, abs=0.005),
    ]


# Setup marked stale (through the API)
def test_setup_marked_stale(owner, monkeypatch):
    add(owner, OPEN, LEFT, "open")
    add(owner, CLOSED, LEFT, "closed")
    call("POST", "/api/door-calibration/run", token=owner)
    monkeypatch.setattr(api, "now", lambda: NOW + 10)
    status, body = add(owner, CLOSED, LEFT, "closed")
    assert body["setup"]["stale"] is True
    assert body["references"][-1]["score"] == pytest.approx(0.0, abs=0.005)


# Missing a status / Open and closed overlap / Too many zones (422 with scores)
def test_setup_fails_with_scores(owner):
    add(owner, OPEN, LEFT, "open")
    status, body = call("POST", "/api/door-calibration/run", token=owner)
    assert status == 422
    assert body["error"] == "zone 1 needs an open and a closed reference"
    [ref] = body["references"]
    assert ref["score"] == pytest.approx(0.1, abs=0.005)
    assert call("GET", "/api/door-calibration", token=owner)[1]["setup"] is None
