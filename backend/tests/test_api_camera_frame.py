"""camera-snapshot: POST /api/camera/frame blurs a live frame from the app, stores nothing."""

import base64
import io

import boto3
import pytest
from botocore.stub import Stubber
from PIL import Image, ImageStat

from fridgesense.faces import enlarge_box
from fridgesense.handlers import api
from fridgesense.store import load_app_config
from tests.api_helpers import call, configure, link_account, sign_in
from tests.conftest import BUCKET, TABLE, checkerboard_jpeg, color_jpeg, load_fixture

NOW = 1792092010.0  # 2026-10-15T19:20:10Z
FRAME = "/api/camera/frame"


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def decoded(body: dict) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(body["image"])))


@pytest.fixture
def faces(aws, monkeypatch):
    client = boto3.client("rekognition", region_name="us-east-1")
    monkeypatch.setattr(api, "rekognition_client", lambda: client)
    with Stubber(client) as stub:
        yield stub


@pytest.fixture
def tokens(aws, faces, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    link_account()
    configure(demo_passcode="look-only")
    load_app_config(refresh=True)
    return {"owner": sign_in(), "viewer": sign_in("look-only")}


@pytest.fixture
def owner(tokens):
    return tokens["owner"]


# Frame blurred and returned
def test_frame_blurred_and_returned(owner, faces):
    faces.add_response("detect_faces", {"FaceDetails": []})
    items_before = boto3.client("dynamodb").scan(TableName=TABLE)["Count"]
    status, body = call("POST", FRAME, {"image": b64(color_jpeg(size=(1920, 1080)))}, owner)
    assert status == 200
    assert decoded(body).size == (960, 540)
    assert decoded(body).format == "JPEG"
    assert len(base64.b64decode(body["image"])) <= 300_000
    assert body["captured_at"] == "2026-10-15T19:20:10.000Z"
    assert boto3.client("s3").list_objects_v2(Bucket=BUCKET).get("KeyCount", 0) == 0
    assert boto3.client("dynamodb").scan(TableName=TABLE)["Count"] == items_before


# Face blurred in the frame
def test_face_blurred_in_the_frame(owner, faces):
    faces.add_response("detect_faces", load_fixture("rekognition/detect_faces_one.json"))
    frame = checkerboard_jpeg(size=(960, 540), square=16)
    status, body = call("POST", FRAME, {"image": b64(frame)}, owner)
    assert status == 200
    img = decoded(body).convert("L")
    x, y, w, h = enlarge_box((0.40, 0.20, 0.20, 0.30))
    W, H = img.size
    face = img.crop(
        (round(x * W) + 4, round(y * H) + 4, round((x + w) * W) - 4, round((y + h) * H) - 4)
    )
    assert ImageStat.Stat(face).stddev[0] < 10


# Small frame kept at its size
def test_small_frame_kept_at_its_size(owner, faces):
    faces.add_response("detect_faces", {"FaceDetails": []})
    status, body = call("POST", FRAME, {"image": b64(color_jpeg(size=(640, 360)))}, owner)
    assert status == 200
    assert decoded(body).size == (640, 360)


# Face detection unavailable
def test_face_detection_unavailable(owner, faces):
    faces.add_client_error("detect_faces", "InternalServerError")
    status, body = call("POST", FRAME, {"image": b64(color_jpeg(size=(960, 540)))}, owner)
    assert (status, body) == (502, {"error": "camera unavailable"})


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32)).save(buf, format="PNG")
    return buf.getvalue()


BAD_IMAGE = (400, {"error": "bad image"})


# Missing image
@pytest.mark.parametrize("body", [{}, {"image": None}, {"image": 5}, ["image"]])
def test_missing_image(owner, faces, body):
    assert call("POST", FRAME, body, owner) == BAD_IMAGE
    faces.assert_no_pending_responses()


def test_body_not_json(owner, faces):
    from tests.api_helpers import api_event

    headers = {"content-type": "application/json", "Authorization": f"Bearer {owner}"}
    resp = api.handler(api_event("POST", FRAME, "not json", headers, None), None)
    assert resp["statusCode"] == 400


# Not a JPEG
@pytest.mark.parametrize("image", [b64(png()), b64(b"hello"), "%%%not-base64%%%"])
def test_not_a_jpeg(owner, faces, image):
    assert call("POST", FRAME, {"image": image}, owner) == BAD_IMAGE


# Too large
def test_too_large(owner, faces):
    big = color_jpeg(size=(64, 64))
    big += b"\0" * (2_000_001 - len(big))
    assert call("POST", FRAME, {"image": b64(big)}, owner) == BAD_IMAGE


# Viewer refused
def test_viewer_refused(tokens, faces):
    image = b64(color_jpeg(size=(960, 540)))
    assert call("POST", FRAME, {"image": image}, tokens["viewer"]) == (
        403,
        {"error": "read-only"},
    )
    faces.assert_no_pending_responses()


# No token
def test_no_token(tokens):
    assert call("POST", FRAME, {"image": b64(color_jpeg())}) == (401, {"error": "sign in"})
