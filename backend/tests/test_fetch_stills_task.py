"""door-event-detection: fetch_stills task (door check, door event record, duplicates)."""

import io
import json
import logging

import boto3
import httpx
import pytest
import respx
from PIL import Image

from fridgesense.door_events import DoorCheck, fetch_stills, iso_utc
from fridgesense.faces import blur_regions
from fridgesense.oauth import OAuthClient
from fridgesense.ring import API_BASE, RingClient
from fridgesense.store import Tokens
from fridgesense.table import FridgeTable
from tests.conftest import BUCKET, FakeBlurrer, MemoryTokenStore, color_jpeg, jpeg

NOW = 1_786_715_700.0
DOWNLOAD = f"{API_BASE}/v1/devices/ava1.ring.device.D1/media/image/download"
ACCOUNT = "ava1.ring.account.A1"
STATE = {
    "account_id": ACCOUNT,
    "device_id": "ava1.ring.device.D1",
    "timestamp_ms": 1786715596787,
    "request_id": "R1",
    "window": {
        "status": "ready",
        "start_ms": 1786715596000,
        "end_ms": 1786715621000,
        "ring_event_id": "evt_1786715596000",
    },
}
PREFIX = "accounts/ava1.ring.account.A1/devices/ava1.ring.device.D1/events/1786715596000/"
DOOR_SK = "DOOR#2026-08-14T13:53:16.000Z#ava1.ring.device.D1"
CHECK = DoorCheck(zones=((0.0, 0.0, 1.0, 1.0),), threshold=0.02)
GREY = (128, 128, 128)
OPEN = color_jpeg(GREY, [((0.2, 0.2, 0.4, 0.5), (40, 90, 200))])  # 20% lit fridge blue


def closed(level: int) -> bytes:
    """A grey still: steel doors at some ambient light level."""
    return color_jpeg((level, level, level))


@pytest.fixture
def ring_http():
    tokens = Tokens(
        account_id=ACCOUNT,
        access_token="at1",
        refresh_token="rt1",
        expires_at=int(NOW) + 3600,
        link_status="linked",
    )
    with httpx.Client() as http:
        ring = RingClient(http, MemoryTokenStore(tokens), OAuthClient(http, "c", "s"), lambda: NOW)
        yield ring, http


def ring_serves(images: list[bytes] | None, status: int = 200):
    """Mock Ring so the n-th still request returns images[n]; None means 403 for all."""
    if images is None:
        respx.post(DOWNLOAD).respond(403)
        return
    counter = iter(range(100))
    respx.post(DOWNLOAD).mock(
        side_effect=lambda request: httpx.Response(
            303, headers={"Location": f"https://dl.example.com/{next(counter)}"}
        )
    )
    respx.get(url__regex=r"https://dl\.example\.com/(\d+)").mock(
        side_effect=lambda request: httpx.Response(
            status, content=images[int(request.url.path.strip("/")) % len(images)]
        )
    )


def run(ring_http, state=STATE, blurrer=None, check=CHECK, crop=None):
    ring, http = ring_http
    return fetch_stills(
        ring,
        http,
        boto3.client("s3"),
        FridgeTable(),
        BUCKET,
        check,
        FakeBlurrer() if blurrer is None else blurrer,
        state,
        sleep=lambda s: None,
        crop=crop,
    )


def stored_keys() -> list[str]:
    listing = boto3.client("s3").list_objects_v2(Bucket=BUCKET)
    return sorted(o["Key"] for o in listing.get("Contents", []))


def door_events():
    return [i for i in FridgeTable().query(ACCOUNT, "DOOR#")]


def test_iso_utc():
    assert iso_utc(1786715596000) == "2026-08-14T13:53:16.000Z"
    assert iso_utc(1786715596787) == "2026-08-14T13:53:16.787Z"


# Door event saved
@respx.mock
def test_door_event_saved(aws, ring_http):
    ring_serves([closed(30), OPEN, OPEN, closed(60)])
    out = run(ring_http)
    assert out["outcome"] == "door_open"
    assert out["door_sk"] == DOOR_SK
    assert len(out["still_keys"]) == 4
    [event] = door_events()
    assert event["sk"] == DOOR_SK
    assert event["device_id"] == "ava1.ring.device.D1"
    assert event["ring_event_id"] == "evt_1786715596000"
    assert event["opened_at"] == "2026-08-14T13:53:16.000Z"
    assert event["closed_at"] == "2026-08-14T13:53:41.000Z"
    assert event["duration_s"] == 25
    assert event["status"] == "analyzing"
    assert event["still_keys"] == out["still_keys"]


# Same Ring event in two runs
@respx.mock
def test_same_ring_event_in_two_runs(aws, ring_http):
    ring_serves([OPEN])
    assert run(ring_http)["outcome"] == "door_open"
    second = run(ring_http, {**STATE, "timestamp_ms": 1786715597500, "request_id": "R2"})
    assert second["outcome"] == "duplicate"
    assert len(door_events()) == 1


# Door stayed closed
@respx.mock
def test_door_stayed_closed(aws, ring_http, caplog):
    caplog.set_level(logging.INFO)
    # 1% colourful pixels: below the 0.02 threshold
    speck = color_jpeg(GREY, [((0.0, 0.0, 0.1, 0.1), (40, 90, 200))])
    ring_serves([closed(30), closed(230), speck])
    blurrer = FakeBlurrer()
    out = run(ring_http, blurrer=blurrer)
    assert out["outcome"] == "not_door"
    assert out["score"] == pytest.approx(0.01, abs=0.002)
    assert "brightest" not in out
    assert door_events() == []
    assert blurrer.contexts == []
    assert stored_keys() == []
    [line] = [r.getMessage() for r in caplog.records if "motion_not_door" in r.getMessage()]
    logged = json.loads(line[line.index("{") :])
    assert logged["score"] == pytest.approx(0.01, abs=0.002)
    assert logged["zone"] == 1
    assert logged["threshold"] == 0.02
    assert "brightest" not in logged


# Too few stills
@respx.mock
def test_too_few_stills_records_no_media(aws, ring_http):
    ring_serves(None)
    blurrer = FakeBlurrer()
    out = run(ring_http, blurrer=blurrer)
    assert out["outcome"] == "no_media"
    assert blurrer.contexts == []
    assert stored_keys() == []
    [event] = door_events()
    assert event["status"] == "no_media"
    assert event["still_keys"] == []


@respx.mock
def test_fallback_window_claims_by_timestamp(aws, ring_http):
    ring_serves([OPEN])
    state = {**STATE, "window": {**STATE["window"], "ring_event_id": None}}
    assert run(ring_http, state)["outcome"] == "door_open"
    assert run(ring_http, state)["outcome"] == "duplicate"


@respx.mock
def test_one_still_is_too_few(aws, ring_http):
    answers = iter([httpx.Response(303, headers={"Location": "https://dl.example.com/0"})])
    respx.post(DOWNLOAD).mock(side_effect=lambda request: next(answers, httpx.Response(403)))
    respx.get("https://dl.example.com/0").respond(200, content=OPEN)
    blurrer = FakeBlurrer()
    out = run(ring_http, blurrer=blurrer)
    assert out["outcome"] == "no_media"
    assert blurrer.contexts == []
    assert stored_keys() == []
    [event] = door_events()
    assert event["status"] == "no_media"
    assert event["still_keys"] == []


# Detection fails for one still
@respx.mock
def test_detection_fails_for_one_still(aws, ring_http):
    ring_serves([OPEN])
    out = run(ring_http, blurrer=FakeBlurrer(drop={2}))
    expected = [f"{PREFIX}still-{n}.jpg" for n in (1, 3, 4)]
    assert stored_keys() == expected
    assert out["outcome"] == "door_open"
    [event] = door_events()
    assert event["still_keys"] == expected


# Detection fails for every still / Too few stills (blur failures count)
@respx.mock
def test_detection_fails_for_every_still(aws, ring_http):
    ring_serves([OPEN])
    out = run(ring_http, blurrer=FakeBlurrer(drop={1, 2, 3, 4}))
    assert stored_keys() == []
    assert out["outcome"] == "no_media"
    [event] = door_events()
    assert event["status"] == "no_media"
    assert event["still_keys"] == []


# Too few stills survive face detection
@respx.mock
def test_too_few_stills_after_blur_failures(aws, ring_http):
    ring_serves([OPEN])
    out = run(ring_http, blurrer=FakeBlurrer(drop={1, 2, 3}))
    assert out["outcome"] == "no_media"
    [event] = door_events()
    assert event["status"] == "no_media"
    assert event["still_keys"] == [f"{PREFIX}still-4.jpg"]
    assert stored_keys() == [f"{PREFIX}still-4.jpg"]


# Fridge light visible
@respx.mock
def test_fridge_light_visible(aws, ring_http):
    ring_serves([closed(30), OPEN])
    blurrer = FakeBlurrer()
    out = run(ring_http, blurrer=blurrer)
    assert out["outcome"] == "door_open"
    assert len(blurrer.contexts) == 4
    assert len(stored_keys()) == 4


# Closed door costs no face detection
@respx.mock
def test_closed_door_costs_no_face_detection(aws, ring_http):
    ring_serves([closed(30), closed(60), closed(230), closed(30)])
    blurrer = FakeBlurrer()
    out = run(ring_http, blurrer=blurrer)
    assert out["outcome"] == "not_door"
    assert blurrer.contexts == []
    assert stored_keys() == []


# Door check runs on downloaded stills
@respx.mock
def test_door_check_runs_on_downloaded_stills(aws, ring_http):
    ring_serves([OPEN])
    face = (0.40, 0.20, 0.20, 0.30)  # inside the door box (whole image)
    out = run(ring_http, blurrer=FakeBlurrer(blurred=lambda data: blur_regions(data, [face])))
    assert out["outcome"] == "door_open"
    body = boto3.client("s3").get_object(Bucket=BUCKET, Key=out["still_keys"][0])["Body"].read()
    assert body == blur_regions(OPEN, [face])


@respx.mock
def test_door_check_uses_the_download_not_the_blurred_bytes(aws, ring_http):
    ring_serves([OPEN])
    out = run(ring_http, blurrer=FakeBlurrer(blurred=lambda data: jpeg(0.1)))
    assert out["outcome"] == "door_open"
    body = boto3.client("s3").get_object(Bucket=BUCKET, Key=out["still_keys"][0])["Body"].read()
    assert body == jpeg(0.1)  # only the blurred result is stored


def size(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


# Door check ignores the crop
@respx.mock
def test_door_check_ignores_the_crop(aws, ring_http):
    right_only = color_jpeg(GREY, [((0.6, 0.0, 0.4, 1.0), (40, 90, 200))])
    ring_serves([right_only])
    check = DoorCheck(zones=((0.6, 0.0, 0.4, 1.0),), threshold=0.02)
    out = run(ring_http, check=check, crop=(0.0, 0.0, 0.5, 1.0))
    assert out["outcome"] == "door_open"


# Detection sees the downloaded bytes, S3 sees only the result (with a crop box)
@respx.mock
def test_detection_and_storage_get_the_cropped_still(aws, ring_http):
    ring_serves([OPEN])  # 320x180
    seen = []
    blurrer = FakeBlurrer(blurred=lambda data: seen.append(data) or data)
    out = run(ring_http, blurrer=blurrer, crop=(0.25, 0.0, 0.5, 1.0))
    assert out["outcome"] == "door_open"
    assert len(seen) == 4
    assert all(size(data) == (160, 180) for data in seen)
    body = boto3.client("s3").get_object(Bucket=BUCKET, Key=out["still_keys"][0])["Body"].read()
    assert body == seen[0]
    assert body != OPEN


# Stills of a closed fridge are never cropped or stored
@respx.mock
def test_closed_fridge_is_not_cropped(aws, ring_http):
    ring_serves([closed(30), closed(60)])
    blurrer = FakeBlurrer()
    assert run(ring_http, blurrer=blurrer, crop=(0.25, 0.0, 0.5, 1.0))["outcome"] == "not_door"
    assert blurrer.contexts == []
    assert stored_keys() == []
