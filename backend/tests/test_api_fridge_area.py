"""fridge-area: reading and saving the fridge box on the app API."""

import base64

import pytest

from fridgesense.devices import Device, DeviceRepository
from fridgesense.handlers import api
from fridgesense.store import load_app_config
from tests.api_helpers import ACCOUNT, call, configure, link_account, sign_in
from tests.conftest import color_jpeg

DEVICE = "ava1.ring.device.D1"
SAVED_AT = 1792112400.0  # 2026-10-16T01:00:00Z
BOX = {"x": 0.2, "y": 0.05, "width": 0.5, "height": 0.9}
IMAGE = color_jpeg(size=(960, 540))
BOX_ERROR = (400, {"error": "box must be inside the image and at least 2% wide and tall"})
IMAGE_ERROR = (400, {"error": "image must be a JPEG of at most 300 KB"})


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


@pytest.fixture
def tokens(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: SAVED_AT)
    link_account()
    configure(demo_passcode="look-only")
    load_app_config(refresh=True)
    DeviceRepository().replace(ACCOUNT, [Device(DEVICE, "Fridge")])
    return {"owner": sign_in(), "viewer": sign_in("look-only")}


@pytest.fixture
def owner(tokens):
    return tokens["owner"]


def put(token, image=IMAGE, box=BOX):
    return call("PUT", "/api/fridge-area", {"image": b64(image), "box": box}, token)


def get(token):
    return call("GET", "/api/fridge-area", token=token)


# No fridge area yet
def test_no_fridge_area_yet(owner):
    assert get(owner) == (200, {"device_id": DEVICE, "area": None})


# Fridge area saved
def test_fridge_area_saved(owner):
    status, body = put(owner)
    assert status == 200
    assert body == {
        "device_id": DEVICE,
        "area": {"image": b64(IMAGE), "box": BOX, "updated_at": "2026-10-16T01:00:00.000Z"},
    }
    assert get(owner) == (200, body)


# Viewer reads the fridge area
def test_viewer_reads_the_fridge_area(tokens):
    put(tokens["owner"])
    status, body = get(tokens["viewer"])
    assert status == 200
    assert body["area"]["box"] == BOX
    assert body["area"]["image"] == b64(IMAGE)


# Saving again replaces the area
def test_saving_again_replaces_the_area(owner):
    put(owner)
    second = color_jpeg((200, 200, 200), size=(960, 540))
    wider = {"x": 0.1, "y": 0, "width": 0.6, "height": 1}
    put(owner, second, wider)
    _, body = get(owner)
    assert body["area"]["box"] == wider
    assert body["area"]["image"] == b64(second)


# Invalid fridge area rejected
@pytest.mark.parametrize(
    ("image", "box", "error"),
    [
        (b"\x89PNG\r\n\x1a\n" + b"0" * 100, BOX, IMAGE_ERROR),
        (b"\xff\xd8\xff" + b"0" * 300_000, BOX, IMAGE_ERROR),
        (IMAGE, {"x": 0.9, "y": 0, "width": 0.2, "height": 1}, BOX_ERROR),
        (IMAGE, {"x": 0, "y": 0, "width": 0.01, "height": 1}, BOX_ERROR),
        (IMAGE, {"x": 0, "y": 0, "width": 0.5}, BOX_ERROR),
    ],
    ids=["png", "too-big", "outside", "too-narrow", "no-height"],
)
def test_invalid_fridge_area_rejected(owner, image, box, error):
    put(owner)
    assert put(owner, image, box) == error
    assert get(owner)[1]["area"]["box"] == BOX


# Viewer cannot save the fridge area
def test_viewer_cannot_save_the_fridge_area(tokens):
    assert put(tokens["viewer"]) == (403, {"error": "read-only"})
    assert get(tokens["owner"])[1]["area"] is None


# Fridge area needs a camera
@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_fridge_area_needs_a_camera(owner, method):
    DeviceRepository().replace(ACCOUNT, [])
    body = {"image": b64(IMAGE), "box": BOX} if method == "PUT" else None
    assert call(method, "/api/fridge-area", body, owner) == (409, {"error": "no camera found"})


# Fridge area needs a token
def test_fridge_area_needs_a_token(tokens):
    assert call("GET", "/api/fridge-area") == (401, {"error": "sign in"})
