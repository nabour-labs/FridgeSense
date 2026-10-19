"""door-event-detection: fetch_stills task (door check, door event record, duplicates)."""

import io
import json
import logging

import boto3
import httpx
import pytest
import respx
from PIL import Image

from fridgesense.door_events import (
    DoorCheck,
    ZoneRule,
    baseline_of,
    fetch_stills,
    iso_utc,
    still_count,
    still_times,
)
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


def window_times(state=STATE) -> list[int]:
    w = state["window"]
    return still_times(w["start_ms"], w["end_ms"], still_count(w["end_ms"] - w["start_ms"]))


def ring_serves(images: list[bytes] | None, status: int = 200, state=STATE):
    """Mock Ring so still n (by its timestamp) gets images[(n - 1) % len]; None: 403 for all."""
    if images is None:
        respx.post(DOWNLOAD).respond(403)
        return
    times = window_times(state)
    respx.post(DOWNLOAD).mock(
        side_effect=lambda request: httpx.Response(
            303,
            headers={
                "Location": f"https://dl.example.com/{json.loads(request.content)['timestamp']}"
            },
        )
    )
    respx.get(url__regex=r"https://dl\.example\.com/(\d+)").mock(
        side_effect=lambda request: httpx.Response(
            status,
            content=images[times.index(int(request.url.path.strip("/"))) % len(images)],
        )
    )


def stills_open_at(numbers: set[int], count: int = 25) -> list[bytes]:
    """`count` distinguishable stills (fill level n); the given numbers show the lit fridge."""
    return [
        color_jpeg((100 + n, 100 + n, 100 + n), [((0.2, 0.2, 0.4, 0.5), (40, 90, 200))])
        if n in numbers
        else color_jpeg((100 + n, 100 + n, 100 + n))
        for n in range(1, count + 1)
    ]


def run(
    ring_http,
    state=STATE,
    blurrer=None,
    check=CHECK,
    crop=None,
    setup_for=None,
    paused_for=None,
    area_for=None,
):
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
        setup_for=setup_for,
        paused_for=paused_for,
        area_for=area_for,
    )


def stored_keys() -> list[str]:
    listing = boto3.client("s3").list_objects_v2(Bucket=BUCKET)
    return sorted(o["Key"] for o in listing.get("Contents", []))


def door_events():
    return [i for i in FridgeTable().query(ACCOUNT, "DOOR#")]


def test_iso_utc():
    assert iso_utc(1786715596000) == "2026-08-14T13:53:16.000Z"
    assert iso_utc(1786715596787) == "2026-08-14T13:53:16.787Z"


# Door event saved (25 stills, stills 6-15 open)
@respx.mock
def test_door_event_saved(aws, ring_http):
    ring_serves(stills_open_at(set(range(6, 16))))
    out = run(ring_http)
    assert out["outcome"] == "door_open"
    assert out["door_sk"] == DOOR_SK
    assert len(out["still_keys"]) == 4
    [event] = door_events()
    assert event["sk"] == DOOR_SK
    assert event["device_id"] == "ava1.ring.device.D1"
    assert event["ring_event_id"] == "evt_1786715596000"
    assert event["opened_at"] == "2026-08-14T13:53:21.769Z"
    assert event["closed_at"] == "2026-08-14T13:53:31.384Z"
    assert event["duration_s"] == 10
    assert event["status"] == "analyzing"
    assert event["still_keys"] == out["still_keys"]


# Four stills saved (from the open span: stills 6, 9, 13, 16)
@respx.mock
def test_four_stills_saved_from_the_open_span(aws, ring_http):
    images = stills_open_at(set(range(6, 16)))
    ring_serves(images)
    seen = []
    out = run(ring_http, blurrer=FakeBlurrer(blurred=lambda data: seen.append(data) or data))
    assert out["outcome"] == "door_open"
    assert seen == [images[n - 1] for n in (6, 9, 13, 16)]
    assert stored_keys() == [f"{PREFIX}still-{n}.jpg" for n in range(1, 5)]
    bodies = [
        boto3.client("s3").get_object(Bucket=BUCKET, Key=k)["Body"].read()
        for k in out["still_keys"]
    ]
    assert bodies == seen


# Short open span (only still 10 open: stills 10 and 11 go on)
@respx.mock
def test_short_open_span(aws, ring_http):
    images = stills_open_at({10})
    ring_serves(images)
    seen = []
    out = run(ring_http, blurrer=FakeBlurrer(blurred=lambda data: seen.append(data) or data))
    assert out["outcome"] == "door_open"
    assert seen == [images[9], images[10]]
    assert stored_keys() == [f"{PREFIX}still-1.jpg", f"{PREFIX}still-2.jpg"]


# Door still open at the end of the window
@respx.mock
def test_door_still_open_at_the_end_of_the_window(aws, ring_http):
    ring_serves(stills_open_at({23, 24, 25}))
    run(ring_http)
    [event] = door_events()
    times = window_times()
    assert event["opened_at"] == iso_utc(times[22])
    assert event["closed_at"] == "2026-08-14T13:53:41.000Z"
    assert event["duration_s"] == round((1786715621000 - times[22]) / 1000)


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
    # Too few stills keep the window times
    assert event["opened_at"] == "2026-08-14T13:53:16.000Z"
    assert event["closed_at"] == "2026-08-14T13:53:41.000Z"
    assert event["duration_s"] == 25


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


# Closed door costs no face detection (25 stills downloaded)
@respx.mock
def test_closed_door_costs_no_face_detection(aws, ring_http):
    ring_serves([closed(30), closed(60), closed(230), closed(30)])
    blurrer = FakeBlurrer()
    out = run(ring_http, blurrer=blurrer)
    assert len(respx.calls) == 2 * 25
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


# Fridge area wins over STILL_CROP
@respx.mock
def test_fridge_area_wins_over_still_crop(aws, ring_http):
    big_open = color_jpeg(GREY, [((0.4, 0.4, 0.15, 0.4), (40, 90, 200))], size=(2560, 1440))
    ring_serves([big_open])
    asked = []

    def area_for(account_id, device_id):
        asked.append((account_id, device_id))
        return (0.362, 0.329, 0.233, 0.611)

    check = DoorCheck(zones=((0.4, 0.4, 0.15, 0.4),), threshold=0.02)
    out = run(ring_http, check=check, crop=(0.30, 0.0, 0.34, 1.0), area_for=area_for)
    assert out["outcome"] == "door_open"
    assert asked == [(STATE["account_id"], STATE["device_id"])]  # once per motion
    body = boto3.client("s3").get_object(Bucket=BUCKET, Key=out["still_keys"][0])["Body"].read()
    w, h = size(body)
    assert abs(w - 716) <= 2 and abs(h - 968) <= 2


# Crop to the visible strip (device without a fridge area)
@respx.mock
def test_still_crop_without_a_fridge_area(aws, ring_http):
    big_open = color_jpeg(GREY, [((0.4, 0.4, 0.15, 0.4), (40, 90, 200))], size=(2560, 1440))
    ring_serves([big_open])
    check = DoorCheck(zones=((0.4, 0.4, 0.15, 0.4),), threshold=0.02)
    out = run(
        ring_http, check=check, crop=(0.30, 0.0, 0.34, 1.0), area_for=lambda a, d: None
    )
    body = boto3.client("s3").get_object(Bucket=BUCKET, Key=out["still_keys"][0])["Body"].read()
    w, h = size(body)
    assert abs(w - 870) <= 1 and h == 1440


# Stills of a closed fridge are never cropped or stored
@respx.mock
def test_closed_fridge_is_not_cropped(aws, ring_http):
    ring_serves([closed(30), closed(60)])
    blurrer = FakeBlurrer()
    assert run(ring_http, blurrer=blurrer, crop=(0.25, 0.0, 0.5, 1.0))["outcome"] == "not_door"
    assert blurrer.contexts == []
    assert stored_keys() == []


def logged(caplog, event: str) -> dict:
    [line] = [r.getMessage() for r in caplog.records if event in r.getMessage()]
    return json.loads(line[line.index("{") :])


def setup(*rules: ZoneRule):
    check = DoorCheck(rules=rules, source="setup")
    return lambda account_id, device_id: check


RIGHT = (0.6, 0.0, 0.4, 1.0)
RIGHT_LIT = color_jpeg(GREY, [(RIGHT, (40, 90, 200))])


# Setup result used for the device
@respx.mock
def test_setup_result_used_for_the_device(aws, ring_http, caplog):
    caplog.set_level(logging.INFO)
    ring_serves([RIGHT_LIT])
    env_check = DoorCheck(zones=((0.0, 0.0, 0.4, 1.0),), threshold=0.02)
    out = run(ring_http, check=env_check, setup_for=setup(ZoneRule(RIGHT, "color", "above", 0.3)))
    assert out["outcome"] == "door_open"
    line = logged(caplog, "door_event_recorded")
    assert line["zones_source"] == "setup"
    assert line["feature"] == "color"


# Setup threshold applied
@respx.mock
def test_setup_threshold_applied(aws, ring_http, caplog):
    caplog.set_level(logging.INFO)
    # 20% of the right zone is colourful: above DOOR_THRESHOLD (0.02), below the setup's 0.3
    ring_serves([color_jpeg(GREY, [((0.6, 0.0, 0.4, 0.2), (40, 90, 200))])])
    out = run(ring_http, setup_for=setup(ZoneRule(RIGHT, "color", "above", 0.3)))
    assert out["outcome"] == "not_door"
    line = logged(caplog, "motion_not_door")
    assert line["zones_source"] == "setup"
    assert line["feature"] == "color"
    assert line["threshold"] == 0.3
    assert line["score"] == pytest.approx(0.2, abs=0.01)


WHOLE = (0.0, 0.0, 1.0, 1.0)


# Brightness rule applied
@respx.mock
@pytest.mark.parametrize("level, outcome", [(200, "door_open"), (100, "not_door")])
def test_brightness_rule_applied(aws, ring_http, level, outcome):
    ring_serves([closed(level)])
    rule = ZoneRule(WHOLE, "brightness", "above", 0.6)
    assert run(ring_http, setup_for=setup(rule))["outcome"] == outcome


# Darker rule applied
@respx.mock
def test_darker_rule_applied(aws, ring_http):
    ring_serves([closed(90)])
    rule = ZoneRule(WHOLE, "brightness", "below", 0.5)
    assert run(ring_http, setup_for=setup(rule))["outcome"] == "door_open"


# Change rule applied
@respx.mock
@pytest.mark.parametrize(
    "still, outcome",
    [
        (color_jpeg((40, 40, 40), [((0.5, 0.0, 0.5, 1.0), (216, 216, 216))]), "door_open"),
        (closed(130), "not_door"),
    ],
)
def test_change_rule_applied(aws, ring_http, still, outcome):
    ring_serves([still])
    rule = ZoneRule(WHOLE, "change", "above", 0.2, baseline_of([closed(128)], WHOLE))
    assert run(ring_http, setup_for=setup(rule))["outcome"] == outcome


# Fallback when setup never ran
@respx.mock
def test_fallback_when_setup_never_ran(aws, ring_http, caplog):
    caplog.set_level(logging.INFO)
    ring_serves([RIGHT_LIT])
    env_check = DoorCheck(zones=(RIGHT,), threshold=0.02)
    out = run(ring_http, check=env_check, setup_for=lambda a, d: None)
    assert out["outcome"] == "door_open"
    assert logged(caplog, "door_event_recorded")["zones_source"] == "default"


# Setup lookup fails
@respx.mock
def test_setup_lookup_fails(aws, ring_http, caplog):
    caplog.set_level(logging.INFO)
    ring_serves([OPEN])

    def broken(account_id, device_id):
        raise RuntimeError("table down")

    out = run(ring_http, setup_for=broken)
    assert out["outcome"] == "door_open"
    assert logged(caplog, "door_setup_unavailable")["error"] == "RuntimeError"
    assert logged(caplog, "door_event_recorded")["zones_source"] == "default"


# Door stayed closed (logs the source and feature)
@respx.mock
def test_door_stayed_closed_logs_source_and_feature(aws, ring_http, caplog):
    caplog.set_level(logging.INFO)
    ring_serves([closed(30)])
    assert run(ring_http)["outcome"] == "not_door"
    line = logged(caplog, "motion_not_door")
    assert line["zones_source"] == "default"
    assert line["feature"] == "blue"


PLATE = (220, 170, 40)


# Food in front of closed doors
@respx.mock
def test_food_in_front_of_closed_doors(aws, ring_http):
    ring_serves([color_jpeg(GREY, [((0.2, 0.2, 0.3, 0.33), PLATE)])])
    out = run(ring_http, check=DoorCheck.from_config("0,0,1,1", None))
    assert out["outcome"] == "not_door"
    assert out["score"] == 0
    assert door_events() == []


# Stored color setup still works
@respx.mock
def test_stored_color_setup_still_works(aws, ring_http):
    ring_serves([color_jpeg(GREY, [((0.2, 0.2, 0.3, 0.33), PLATE)])])
    out = run(ring_http, setup_for=setup(ZoneRule(WHOLE, "color", "above", 0.05)))
    assert out["outcome"] == "door_open"


# --- paused camera (fridge-monitoring) ---


# Scenario: Paused after the run started
@respx.mock
def test_paused_after_the_run_started(aws, ring_http):
    download = respx.post(DOWNLOAD).respond(403)
    blurred = []
    asked = []
    out = run(
        ring_http,
        blurrer=FakeBlurrer(blurred=lambda data: blurred.append(data) or data),
        paused_for=lambda account_id, device_id: asked.append((account_id, device_id)) or True,
    )
    assert out == {**STATE, "outcome": "paused"}
    assert asked == [(ACCOUNT, "ava1.ring.device.D1")]
    assert not download.called
    assert blurred == []
    assert door_events() == []
    assert stored_keys() == []


# Scenario: Resumed before the stills step
@respx.mock
def test_resumed_before_the_stills_step(aws, ring_http):
    ring_serves(stills_open_at(set(range(6, 16))))
    out = run(ring_http, paused_for=lambda account_id, device_id: False)
    assert out["outcome"] == "door_open"
    assert len(door_events()) == 1
