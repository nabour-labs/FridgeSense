"""door-calibration: the camera snapshot and door setup routes on the app API."""

import base64
import io
import json

import boto3
import pytest
import respx
from botocore.exceptions import ClientError
from botocore.stub import Stubber
from PIL import Image

from fridgesense import alignment, face_blur
from fridgesense.devices import Device, DeviceRepository
from fridgesense.door_events import iso_utc
from fridgesense.handlers import api
from fridgesense.ring import API_BASE
from fridgesense.store import load_app_config
from fridgesense.table import FridgeTable
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


def add_zone(token, name="Doors", box=LEFT):
    body = {"name": name, "box": box, "source": "clip"}
    return call("POST", "/api/door-calibration/zones", body, token)


def zone_id(token, name="Doors", box=LEFT):
    status, body = add_zone(token, name, box)
    assert status == 200
    return body["zones"][-1]["id"]


def add(token, zone, image=OPEN, status="open"):
    return call(
        "POST",
        "/api/door-calibration/references",
        {"image": b64(image), "zone_id": zone, "status": status, "source": "clip"},
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


# Snapshot while blurring is off
@respx.mock
def test_snapshot_while_blurring_is_off(owner, faces):
    call("PUT", "/api/settings/face-blur", {"enabled": False}, owner)
    respx.post(DOWNLOAD).respond(303, headers={"Location": LINK})
    respx.get(LINK).respond(200, content=color_jpeg(size=(1920, 1080)))
    status, body = call("POST", "/api/camera/snapshot", token=owner)  # no detect_faces stubbed
    assert status == 200
    assert Image.open(io.BytesIO(base64.b64decode(body["image"]))).size == (960, 540)
    faces.assert_no_pending_responses()


# Read fails for a snapshot
@respx.mock
def test_snapshot_setting_read_fails(owner, faces, monkeypatch):
    call("PUT", "/api/settings/face-blur", {"enabled": False}, owner)
    get = FridgeTable.get

    def failing_get(self, pk, sk):
        if sk == face_blur.SETTING_SK:
            raise ClientError({"Error": {"Code": "InternalServerError"}}, "GetItem")
        return get(self, pk, sk)

    monkeypatch.setattr(FridgeTable, "get", failing_get)
    respx.post(DOWNLOAD).respond(303, headers={"Location": LINK})
    respx.get(LINK).respond(200, content=color_jpeg(size=(960, 540)))
    faces.add_response("detect_faces", {"FaceDetails": []})
    assert call("POST", "/api/camera/snapshot", token=owner)[0] == 200
    faces.assert_no_pending_responses()  # detection ran although the saved setting is off


# No device discovered (every route)
@pytest.mark.parametrize(
    "method, path",
    [
        ("POST", "/api/camera/snapshot"),
        ("GET", "/api/door-calibration"),
        ("POST", "/api/door-calibration/zones"),
        ("PATCH", "/api/door-calibration/zones/abc"),
        ("DELETE", "/api/door-calibration/zones/abc"),
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
        "zones": [],
        "references": [],
        "setup": None,
        "alignment": None,
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
        ("POST", "/api/door-calibration/zones"),
        ("PATCH", "/api/door-calibration/zones/{zone}"),
        ("DELETE", "/api/door-calibration/zones/{zone}"),
        ("POST", "/api/door-calibration/references"),
        ("DELETE", "/api/door-calibration/references/abc"),
        ("POST", "/api/door-calibration/run"),
    ],
)
def test_viewer_cannot_change_the_setup(tokens, method, path):
    zone = zone_id(tokens["owner"])
    before = call("GET", "/api/door-calibration", token=tokens["owner"])[1]
    ring = respx.post(DOWNLOAD).respond(303, headers={"Location": LINK})
    body = {"name": "Other", "box": LEFT, "zone_id": zone, "image": b64(OPEN), "status": "open"}
    assert call(method, path.format(zone=zone), body, tokens["viewer"]) == READ_ONLY
    assert not ring.called
    assert call("GET", "/api/door-calibration", token=tokens["owner"])[1] == before


# Zone added
def test_zone_added(owner, monkeypatch):
    add_zone(owner, "Doors")
    monkeypatch.setattr(api, "now", lambda: NOW + 1)  # zones list oldest first
    box = {"x": 0.38, "y": 0.65, "width": 0.2, "height": 0.25}
    status, body = add_zone(owner, "Freezer drawer", box)
    assert status == 200
    last = body["zones"][-1]
    assert last["id"]
    assert {k: last[k] for k in ("name", "box", "open", "closed")} == {
        "name": "Freezer drawer",
        "box": box,
        "open": 0,
        "closed": 0,
    }
    assert [z["name"] for z in body["zones"]] == ["Doors", "Freezer drawer"]


# Invalid zone rejected
@pytest.mark.parametrize(
    "body, error",
    [
        ({"name": "", "box": LEFT}, "name must be 1 to 30 characters"),
        ({"name": "   ", "box": LEFT}, "name must be 1 to 30 characters"),
        ({"name": "x" * 31, "box": LEFT}, "name must be 1 to 30 characters"),
        ({"box": LEFT}, "name must be 1 to 30 characters"),
        (
            {"name": "Doors", "box": {"x": 0.9, "y": 0, "width": 0.2, "height": 1}},
            "box must be inside the image and at least 2% wide and tall",
        ),
    ],
)
def test_invalid_zone_rejected(owner, body, error):
    assert call("POST", "/api/door-calibration/zones", body, owner) == (400, {"error": error})
    assert call("GET", "/api/door-calibration", token=owner)[1]["zones"] == []


# Zone limit
def test_zone_limit(owner, monkeypatch):
    for n in range(6):
        monkeypatch.setattr(api, "now", lambda n=n: NOW + n)
        assert add_zone(owner, f"Z{n}")[0] == 200
    assert add_zone(owner, "Z6") == (409, {"error": "at most 6 door zones"})


# Zone redrawn
def test_zone_redrawn(owner, monkeypatch):
    zone = zone_id(owner)
    add(owner, zone, OPEN, "open")
    add(owner, zone, CLOSED, "closed")
    call("POST", "/api/door-calibration/run", token=owner)
    monkeypatch.setattr(api, "now", lambda: NOW + 10)
    box = {"x": 0.36, "y": 0.3, "width": 0.25, "height": 0.4}
    status, body = call("PATCH", f"/api/door-calibration/zones/{zone}", {"box": box}, owner)
    assert status == 200
    assert [(z["name"], z["box"]) for z in body["zones"]] == [("Doors", box)]
    assert [r["box"] for r in body["references"]] == [box, box]
    assert body["setup"]["stale"] is True


def test_zone_renamed(owner):
    zone = zone_id(owner)
    path = f"/api/door-calibration/zones/{zone}"
    status, body = call("PATCH", path, {"name": "Fridge doors"}, owner)
    assert status == 200
    assert [(z["name"], z["box"]) for z in body["zones"]] == [("Fridge doors", LEFT)]
    assert call("PATCH", path, {"name": ""}, owner) == (
        400,
        {"error": "name must be 1 to 30 characters"},
    )


# Zone deleted with its references
def test_zone_deleted_with_its_references(owner):
    zone = zone_id(owner)
    add(owner, zone, OPEN, "open")
    add(owner, zone, CLOSED, "closed")
    status, body = call("DELETE", f"/api/door-calibration/zones/{zone}", token=owner)
    assert status == 200
    assert body["zones"] == [] and body["references"] == []
    for method in ("PATCH", "DELETE"):
        assert call(method, f"/api/door-calibration/zones/{zone}", {"name": "x"}, owner) == (
            404,
            {"error": "not found"},
        )


# Reference added
def test_reference_added(owner):
    box = {"x": 0.38, "y": 0.32, "width": 0.21, "height": 0.30}
    zone = zone_id(owner, "Doors", box)
    status, body = add(owner, zone, color_jpeg(size=(960, 540)))
    assert status == 200
    [ref] = body["references"]
    assert ref["id"]
    assert ref["zone_id"] == zone
    assert ref["box"] == box
    assert (body["zones"][0]["open"], body["zones"][0]["closed"]) == (1, 0)
    assert ref["status"] == "open"
    assert ref["score"] is None
    assert ref["image"] == b64(color_jpeg(size=(960, 540)))
    assert ref["created_at"].endswith("Z")


# Invalid reference rejected
@pytest.mark.parametrize(
    "body, error",
    [
        (
            {"image": b64(b"\x89PNG\r\n\x1a\n"), "zone_id": "{zone}", "status": "open"},
            "image must be a JPEG of at most 300 KB",
        ),
        (
            {"image": b64(OPEN), "zone_id": "{zone}", "status": "ajar"},
            "status must be open or closed",
        ),
        ({"image": b64(OPEN), "status": "open"}, "pick a door zone"),
        ({"image": b64(OPEN), "zone_id": "bm9wZQ", "status": "open"}, "pick a door zone"),
        ({"image": b64(OPEN), "zone_id": 5, "status": "open"}, "pick a door zone"),
    ],
)
def test_invalid_reference_rejected(owner, body, error):
    zone = zone_id(owner)
    body = {
        k: v.format(zone=zone) if k == "zone_id" and isinstance(v, str) else v
        for k, v in body.items()
    }
    assert call("POST", "/api/door-calibration/references", body, owner) == (400, {"error": error})
    assert call("GET", "/api/door-calibration", token=owner)[1]["references"] == []


# Zones kept per device
def test_zones_kept_per_device(owner):
    zone = zone_id(owner)
    DeviceRepository().replace(ACCOUNT, [Device("ava1.ring.device.D2", "Other")])
    assert add(owner, zone) == (400, {"error": "pick a door zone"})


# Reference limit
def test_reference_limit(owner, monkeypatch):
    zone = zone_id(owner)
    for n in range(24):
        monkeypatch.setattr(api, "now", lambda n=n: NOW + n)
        assert add(owner, zone)[0] == 200
    assert add(owner, zone) == (409, {"error": "at most 24 door references"})


# Reference deleted
def test_reference_deleted(owner):
    ref_id = add(owner, zone_id(owner))[1]["references"][0]["id"]
    status, body = call("DELETE", f"/api/door-calibration/references/{ref_id}", token=owner)
    assert status == 200 and body["references"] == []
    assert call("DELETE", f"/api/door-calibration/references/{ref_id}", token=owner) == (
        404,
        {"error": "not found"},
    )


# Setup from one open and one closed reference (through the API)
def test_run_setup(owner, monkeypatch):
    doors = zone_id(owner, "Doors")
    add(owner, doors, OPEN, "open")
    monkeypatch.setattr(api, "now", lambda: NOW + 1)
    add(owner, doors, CLOSED, "closed")
    monkeypatch.setattr(api, "now", lambda: NOW + 2)
    status, body = call("POST", "/api/door-calibration/run", token=owner)
    assert status == 200
    [zone] = body["setup"]["zones"]
    assert (zone["id"], zone["name"]) == (doors, "Doors")
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
    zone = zone_id(owner)
    add(owner, zone, OPEN, "open")
    add(owner, zone, CLOSED, "closed")
    call("POST", "/api/door-calibration/run", token=owner)
    monkeypatch.setattr(api, "now", lambda: NOW + 10)
    status, body = add(owner, zone, CLOSED, "closed")
    assert body["setup"]["stale"] is True
    assert body["references"][-1]["score"] == pytest.approx(0.0, abs=0.005)


# Reference of a zone added after setup
def test_reference_of_a_zone_added_after_setup(owner, monkeypatch):
    set_up_door(owner)
    monkeypatch.setattr(api, "now", lambda: NOW + 10)
    drawer = zone_id(owner, "Drawer", {"x": 0.5, "y": 0, "width": 0.5, "height": 1})
    _, body = add(owner, drawer, CLOSED, "closed")
    assert body["references"][-1]["score"] is None


# No zones
def test_no_zones(owner):
    assert call("POST", "/api/door-calibration/run", token=owner) == (
        422,
        {"error": "add a door zone first", "references": []},
    )


# Missing a status / Open and closed overlap (422 with scores)
def test_setup_fails_with_scores(owner):
    add(owner, zone_id(owner, "Freezer drawer"), OPEN, "open")
    status, body = call("POST", "/api/door-calibration/run", token=owner)
    assert status == 422
    assert body["error"] == "Freezer drawer needs an open and a closed reference"
    [ref] = body["references"]
    assert ref["score"] == pytest.approx(0.1, abs=0.005)
    assert call("GET", "/api/door-calibration", token=owner)[1]["setup"] is None


# --- door-self-calibration: alignment and tuning in the body ---


def set_up_door(owner):
    zone = zone_id(owner)
    add(owner, zone, OPEN, "open")
    add(owner, zone, CLOSED, "closed")
    call("POST", "/api/door-calibration/run", token=owner)


# Before any event
def test_alignment_before_any_event(owner):
    set_up_door(owner)
    _, body = call("GET", "/api/door-calibration", token=owner)
    assert body["alignment"] == {
        "dx": 0,
        "dy": 0,
        "error": None,
        "failures": 0,
        "moved": False,
        "moved_at": None,
        "last_moved_at": None,
        "checked_at": None,
    }
    assert body["setup"]["tuned_at"] is None
    assert body["setup"]["tuned_from"] is None


# Reported after an aligned event
def test_reported_after_an_aligned_event(owner, tokens):
    set_up_door(owner)
    at = int(NOW * 1000) + 5000
    result = alignment.Alignment(True, 0.0156, 0.0, 0.0312, "first")
    alignment.record(FridgeTable(), ACCOUNT, DEVICE, result, at)
    _, body = call("GET", "/api/door-calibration", token=tokens["viewer"])
    assert body["alignment"] == {
        "dx": 0.016,
        "dy": 0,
        "error": 0.031,
        "failures": 0,
        "moved": False,
        "moved_at": None,
        "last_moved_at": None,
        "checked_at": iso_utc(at),
    }
    assert body["setup"]["tuned_at"] is None


def test_moved_times_reported(owner):
    set_up_door(owner)
    at = int(NOW * 1000) + 9000
    moved = alignment.Alignment(True, 0.05, 0, 0.01, "last")
    alignment.record(FridgeTable(), ACCOUNT, DEVICE, moved, at)
    _, body = call("GET", "/api/door-calibration", token=owner)
    assert body["alignment"]["moved"] is True
    assert body["alignment"]["moved_at"] == iso_utc(at)
    assert body["alignment"]["last_moved_at"] == iso_utc(at)


# --- Door zones and references record their picture's source ---


def body_of(owner) -> dict:
    return call("GET", "/api/door-calibration", token=owner)[1]


# Reference from a clip
def test_reference_from_a_clip(owner):
    zone = zone_id(owner)
    payload = {"image": b64(CLOSED), "zone_id": zone, "status": "closed", "source": "clip"}
    status, body = call("POST", "/api/door-calibration/references", payload, owner)
    assert status == 200
    assert body["references"][-1]["source"] == "clip"


# Source left out
def test_source_left_out(owner):
    call("POST", "/api/door-calibration/zones", {"name": "Doors", "box": LEFT}, owner)
    [zone] = body_of(owner)["zones"]
    assert zone["source"] == "live"
    ref = {"image": b64(CLOSED), "zone_id": zone["id"], "status": "closed"}
    call("POST", "/api/door-calibration/references", ref, owner)
    assert body_of(owner)["references"][0]["source"] == "live"


# Unknown source
@pytest.mark.parametrize("source", ["upload", 3])
def test_unknown_source(owner, source):
    error = (400, {"error": "source must be clip or live"})
    zone_body = {"name": "Doors", "box": LEFT, "source": source}
    assert call("POST", "/api/door-calibration/zones", zone_body, owner) == error
    zone = zone_id(owner)
    ref = {"image": b64(CLOSED), "zone_id": zone, "status": "closed", "source": source}
    assert call("POST", "/api/door-calibration/references", ref, owner) == error
    patch = {"box": LEFT, "source": source}
    assert call("PATCH", f"/api/door-calibration/zones/{zone}", patch, owner) == error
    body = body_of(owner)
    assert len(body["zones"]) == 1
    assert body["references"] == []


# Stored before this change
def test_stored_before_this_change(owner):
    zone = zone_id(owner)
    add(owner, zone, CLOSED, "closed")
    table = FridgeTable()
    for item in table.query(ACCOUNT, "DOORZONE#") + table.query(ACCOUNT, "DOORREF#"):
        item.pop("source", None)
        table.put(item)
    body = body_of(owner)
    assert body["zones"][0]["source"] == "live"
    assert body["references"][0]["source"] == "live"


# Rename keeps the source
def test_rename_keeps_the_source(owner):
    call(
        "POST",
        "/api/door-calibration/zones",
        {"name": "Doors", "box": LEFT, "source": "clip"},
        owner,
    )
    zone = body_of(owner)["zones"][0]["id"]
    call("PATCH", f"/api/door-calibration/zones/{zone}", {"name": "Fridge doors"}, owner)
    assert body_of(owner)["zones"][0]["source"] == "clip"


# Redraw on a live picture
def test_redraw_on_a_live_picture(owner):
    call(
        "POST",
        "/api/door-calibration/zones",
        {"name": "Doors", "box": LEFT, "source": "clip"},
        owner,
    )
    zone = body_of(owner)["zones"][0]["id"]
    right = {"x": 0.5, "y": 0, "width": 0.5, "height": 1}
    call("PATCH", f"/api/door-calibration/zones/{zone}", {"box": right}, owner)
    assert body_of(owner)["zones"][0]["source"] == "live"
    call("PATCH", f"/api/door-calibration/zones/{zone}", {"box": LEFT, "source": "clip"}, owner)
    assert body_of(owner)["zones"][0]["source"] == "clip"


# --- Setup needs zones and references from clips ---


def clip_zone(owner, name="Doors", box=LEFT, source="clip") -> str:
    call("POST", "/api/door-calibration/zones", {"name": name, "box": box, "source": source}, owner)
    return body_of(owner)["zones"][-1]["id"]


def clip_ref(owner, zone, image, status, source="clip"):
    payload = {"image": b64(image), "zone_id": zone, "status": status, "source": source}
    return call("POST", "/api/door-calibration/references", payload, owner)


# Live reference refused
def test_live_reference_refused(owner, monkeypatch):
    zone = clip_zone(owner)
    clip_ref(owner, zone, OPEN, "open")
    monkeypatch.setattr(api, "now", lambda: NOW + 1)  # listed second
    clip_ref(owner, zone, CLOSED, "closed", source="live")
    status, body = call("POST", "/api/door-calibration/run", token=owner)
    assert status == 422
    assert body["error"] == (
        "reference 2 is not from a recorded clip. Replace it with a frame from a recent clip."
    )
    assert len(body["references"]) == 2
    assert body_of(owner)["setup"] is None


# Live zone refused
def test_live_zone_refused(owner):
    zone = clip_zone(owner, source="live")
    clip_ref(owner, zone, OPEN, "open", source="live")
    clip_ref(owner, zone, CLOSED, "closed")
    status, body = call("POST", "/api/door-calibration/run", token=owner)
    assert status == 422
    assert body["error"] == (
        "zone Doors was drawn on a live picture. Redraw it on a frame from a recent clip."
    )


# Everything from clips
def test_everything_from_clips(owner):
    zone = clip_zone(owner)
    clip_ref(owner, zone, OPEN, "open")
    clip_ref(owner, zone, CLOSED, "closed")
    status, body = call("POST", "/api/door-calibration/run", token=owner)
    assert status == 200
    assert body["setup"]["zones"][0]["feature"] == "blue"
