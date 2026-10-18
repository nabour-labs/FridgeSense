"""door-event-detection: the fetch-stills task checking the door on the event clip's frames."""

import io
import json
import logging

import boto3
import httpx
import pytest
import respx
from PIL import Image

from fridgesense import door_events as door_events_module
from fridgesense.door_events import DoorCheck, ZoneRule, fetch_stills, iso_utc
from fridgesense.oauth import OAuthClient
from fridgesense.ring import RingClient
from fridgesense.store import Tokens
from fridgesense.table import FridgeTable
from tests.clip_video import door_clip
from tests.conftest import BUCKET, FakeBlurrer, MemoryTokenStore, color_jpeg
from tests.test_fetch_stills_task import (
    DOWNLOAD,
    PREFIX,
    STATE,
    door_events,
    ring_serves,
    stills_open_at,
    stored_keys,
)

NOW = 1_786_715_700.0
CLIP_URL = DOWNLOAD.replace("/media/image/download", "/media/video/download")
CLIP_LINK = "https://clip.example.com/clip.mp4"
START = 1786715596000
STATE20 = {**STATE, "window": {**STATE["window"], "end_ms": START + 20_000}}
CHECK = DoorCheck(zones=((0.0, 0.0, 1.0, 1.0),), threshold=0.02)
STILL = color_jpeg((200, 60, 60))  # Ring's still: a different moment, never what the check scored


@pytest.fixture
def ring_http():
    tokens = Tokens(
        account_id=STATE["account_id"],
        access_token="at1",
        refresh_token="rt1",
        expires_at=int(NOW) + 3600,
        link_status="linked",
    )
    with httpx.Client() as http:
        ring = RingClient(http, MemoryTokenStore(tokens), OAuthClient(http, "c", "s"), lambda: NOW)
        yield ring, http


def run(ring_http, state=STATE20, blurrer=None, clip_dir=None, sleeps=None, face_blur=True):
    ring, http = ring_http
    return fetch_stills(
        ring,
        http,
        boto3.client("s3"),
        FridgeTable(),
        BUCKET,
        CHECK,
        FakeBlurrer() if blurrer is None else blurrer,
        state,
        sleep=(sleeps.append if sleeps is not None else lambda s: None),
        frame_interval_ms=500,
        clip_dir=clip_dir,
        face_blur=face_blur,
    )


def serve_clip(tmp_path, open_ms, duration_ms=20_000):
    """Ring answers the clip request with a 303 to a generated MP4."""
    data = door_clip(tmp_path / "served.mp4", open_ms, duration_ms).read_bytes()
    (tmp_path / "served.mp4").unlink()
    post = respx.post(CLIP_URL).respond(303, headers={"Location": CLIP_LINK})
    respx.get(CLIP_LINK).respond(200, content=data)
    return post


def serve_stills(missing=()):
    """Ring answers still requests with STILL, or 403 at the `missing` offsets (ms)."""
    post = respx.post(DOWNLOAD).mock(
        side_effect=lambda request: httpx.Response(
            403 if json.loads(request.content)["timestamp"] - START in missing else 303,
            headers={
                "Location": f"https://dl.example.com/{json.loads(request.content)['timestamp']}"
            },
        )
    )
    respx.get(url__regex=r"https://dl\.example\.com/\d+").respond(200, content=STILL)
    return post


def stored_stills() -> list[str]:
    """The stored keys other than the open-span clip (raw or not)."""
    return [k for k in stored_keys() if not k.endswith(".mp4")]


def logged(caplog, event: str) -> dict:
    [line] = [r.getMessage() for r in caplog.records if f'"{event}"' in r.getMessage()]
    return json.loads(line)


# Not a door opening
@respx.mock
def test_not_a_door_opening(aws, ring_http, tmp_path):
    clip = serve_clip(tmp_path, [])
    stills = serve_stills()
    out = run(ring_http, clip_dir=tmp_path)
    assert out["outcome"] == "not_door"
    assert clip.call_count == 1
    assert stills.call_count == 0
    assert stored_keys() == []
    assert door_events() == []


# Open and close times
@respx.mock
def test_open_and_close_times(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(4000, 12_500)])
    serve_stills()
    out = run(ring_http, clip_dir=tmp_path)
    assert out["outcome"] == "door_open"
    [event] = door_events()
    assert event["opened_at"] == "2026-08-14T13:53:20.000Z"
    assert event["closed_at"] == "2026-08-14T13:53:28.500Z"
    assert event["duration_s"] == 8


# Still open at the end of the clip
@respx.mock
def test_still_open_at_the_end_of_the_clip(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(15_000, 20_000)])
    serve_stills()
    run(ring_http, clip_dir=tmp_path)
    [event] = door_events()
    assert event["opened_at"] == iso_utc(START + 15_000)
    assert event["closed_at"] == "2026-08-14T13:53:36.000Z"


def frame_colours(seen: list[bytes]) -> list[str]:
    """Each stored still as "lit" (open frame) or "closed" (closed frame); fails on Ring's still."""
    out = []
    for data in seen:
        img = Image.open(io.BytesIO(data))
        assert img.format == "JPEG" and img.size == (320, 180)  # a clip frame, not Ring's still
        r, g, b = img.convert("RGB").getpixel((160, 90))
        assert r < 150, "Ring's still was stored instead of the clip frame"
        out.append("lit" if b > 150 and r < 90 else "closed")
    return out


def run_seen(ring_http, tmp_path):
    seen = []
    out = run(
        ring_http, blurrer=FakeBlurrer(blurred=lambda d: seen.append(d) or d), clip_dir=tmp_path
    )
    return out, seen


# Four stills from the open span
@respx.mock
def test_four_stills_from_the_open_span(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(4000, 12_500)])
    serve_stills()
    out, seen = run_seen(ring_http, tmp_path)
    # frames at 4000, 7000, 9500 (lit) and 12500 (the first closed frame)
    assert frame_colours(seen) == ["lit", "lit", "lit", "closed"]
    assert stored_stills() == [f"{PREFIX}still-{n}.jpg" for n in range(1, 5)]
    assert out["still_keys"] == stored_stills()


# Short open span
@respx.mock
def test_short_open_span(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(6000, 6500)])
    serve_stills()
    _, seen = run_seen(ring_http, tmp_path)
    assert frame_colours(seen) == ["lit", "closed"]  # frames at 6000 and 6500
    assert stored_stills() == [f"{PREFIX}still-1.jpg", f"{PREFIX}still-2.jpg"]


# No Ring still requested
@respx.mock
def test_no_ring_still_requested(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(4000, 12_500)])
    stills = serve_stills()
    out, seen = run_seen(ring_http, tmp_path)
    assert out["outcome"] == "door_open"
    assert stills.call_count == 0
    assert frame_colours(seen)[1] == "lit"  # still-2.jpg is the frame at 7000 ms


# Still missing, frame used
@respx.mock
def test_still_missing_frame_used(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(4000, 12_500)])
    serve_stills(missing={7000})
    out, seen = run_seen(ring_http, tmp_path)
    assert out["outcome"] == "door_open"
    assert len(out["still_keys"]) == 4
    assert frame_colours(seen)[1] == "lit"  # the lit frame at 7.0 s


# Door opening processed: blurred stills and only the open-span clip reach S3
@respx.mock
def test_door_opening_processed_stores_only_the_open_span_clip(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(4000, 12_500)])
    serve_stills()
    run(ring_http, clip_dir=tmp_path, face_blur=False)
    keys = stored_keys()
    assert [k for k in keys if k.endswith(".mp4")] == [f"{PREFIX}clip.mp4"]
    assert all(k.endswith(".mp4") or (k.endswith(".jpg") and "/still-" in k) for k in keys)


# Temporary file removed (success)
@respx.mock
def test_temporary_file_removed_after_the_step(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(4000, 12_500)])
    serve_stills()
    run(ring_http, clip_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


# --- Fall back to still sampling without the clip ---------------------------------------

STILL_PATH_OPENED = "2026-08-14T13:53:21.769Z"  # what today's still path finds (stills 6-15)


def fallback_run(ring_http, caplog, tmp_path, sleeps=None):
    caplog.set_level(logging.INFO)
    ring_serves(stills_open_at(set(range(6, 16))))
    out = run(ring_http, state=STATE, clip_dir=tmp_path, sleeps=sleeps)
    [event] = door_events()
    assert out["outcome"] == "door_open"
    assert event["opened_at"] == STILL_PATH_OPENED  # exactly as the still path
    assert list(tmp_path.iterdir()) == []
    return logged(caplog, "clip_unavailable")


# Ring refuses the clip
@respx.mock
def test_ring_refuses_the_clip(aws, ring_http, caplog, tmp_path):
    respx.post(CLIP_URL).respond(403, json={"code": "TIME_RANGE_NOT_AUTHORIZED"})
    line = fallback_run(ring_http, caplog, tmp_path)
    assert line["reason"] == "status_403"
    assert line["device_id"] == STATE["device_id"]


# Clip never ready
@respx.mock
def test_clip_never_ready(aws, ring_http, caplog, tmp_path):
    clip = respx.post(CLIP_URL).respond(303, headers={"Location": CLIP_LINK})
    respx.get(CLIP_LINK).respond(416, json={"errors": [{"code": "MEDIA_NOT_FOUND"}]})
    sleeps = []
    assert fallback_run(ring_http, caplog, tmp_path, sleeps)["reason"] == "status_416"
    assert clip.call_count == 3
    assert sleeps[:2] == [3, 6]


# Clip request never ready
@respx.mock
def test_clip_request_never_ready(aws, ring_http, caplog, tmp_path):
    respx.post(CLIP_URL).respond(425, json={"code": "RECORDING_NOT_READY"})
    assert fallback_run(ring_http, caplog, tmp_path)["reason"] == "status_425"


# Unreadable clip (and its temporary file removed)
@respx.mock
def test_unreadable_clip(aws, ring_http, caplog, tmp_path):
    respx.post(CLIP_URL).respond(303, headers={"Location": CLIP_LINK})
    respx.get(CLIP_LINK).respond(200, content=b'{"not": "a video"}')
    assert fallback_run(ring_http, caplog, tmp_path)["reason"] == "decode_failed"


# Clip too large
@respx.mock
def test_clip_too_large(aws, ring_http, caplog, tmp_path):
    respx.post(CLIP_URL).respond(303, headers={"Location": CLIP_LINK})
    respx.get(CLIP_LINK).respond(200, content=b"x", headers={"Content-Length": "300000001"})
    assert fallback_run(ring_http, caplog, tmp_path)["reason"] == "too_large"


# Network error
@respx.mock
def test_network_error(aws, ring_http, caplog, tmp_path):
    respx.post(CLIP_URL).mock(side_effect=httpx.ConnectError("boom"))
    assert fallback_run(ring_http, caplog, tmp_path)["reason"] == "download_failed"


# Clip path off (no frame interval): today's still sampling, no clip request
@respx.mock
def test_no_frame_interval_means_stills_only(aws, ring_http):
    clip = respx.post(CLIP_URL).respond(403)
    ring_serves(stills_open_at(set(range(6, 16))))
    ring, http = ring_http
    out = fetch_stills(
        ring,
        http,
        boto3.client("s3"),
        FridgeTable(),
        BUCKET,
        CHECK,
        FakeBlurrer(),
        STATE,
        sleep=lambda s: None,
    )
    assert out["outcome"] == "door_open"
    assert clip.call_count == 0


# --- Clip-wide sanity guard ---

WHOLE_BOX = (0.0, 0.0, 1.0, 1.0)
# Setup rules that read every grey frame as open: a picture framed unlike the clips
MISCALIBRATED = DoorCheck(rules=(ZoneRule(WHOLE_BOX, "brightness", "above", 0.1),), source="setup")
SETUP_BLUE = DoorCheck(rules=(ZoneRule(WHOLE_BOX, "blue", "above", 0.02),), source="setup")


def run_setup(ring_http, rules, end_ms, clip_dir):
    ring, http = ring_http
    state = {**STATE, "window": {**STATE["window"], "end_ms": START + end_ms}}
    return fetch_stills(
        ring,
        http,
        boto3.client("s3"),
        FridgeTable(),
        BUCKET,
        CHECK,
        FakeBlurrer(),
        state,
        sleep=lambda s: None,
        frame_interval_ms=500,
        clip_dir=clip_dir,
        setup_for=lambda account_id, device_id: rules,
    )


# Fridge light finds the real opening
@respx.mock
def test_fridge_light_finds_the_real_opening(aws, ring_http, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    serve_clip(tmp_path, [(8500, 13_000)], duration_ms=27_000)  # frames 18-26 of 54 lit
    serve_stills()
    out = run_setup(ring_http, MISCALIBRATED, 27_000, tmp_path)
    assert out["outcome"] == "door_open"
    assert out["suspect"] is True
    [event] = door_events()
    assert event["opened_at"] == iso_utc(START + 8500)
    assert event["closed_at"] == iso_utc(START + 13_000)
    assert len(stored_stills()) == 4
    suspect = logged(caplog, "door_check_suspect")
    assert (suspect["frames"], suspect["open_share"], suspect["zones_source"]) == (
        54,
        1.0,
        "setup",
    )
    assert logged(caplog, "door_event_recorded")["zones_source"] == "fallback"


# Fridge light finds no opening
@respx.mock
def test_fridge_light_finds_no_opening(aws, ring_http, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    serve_clip(tmp_path, [], duration_ms=20_500)  # someone walks past: 41 grey frames
    stills = serve_stills()
    out = run_setup(ring_http, MISCALIBRATED, 20_500, tmp_path)
    assert out["outcome"] == "not_door"
    assert out["suspect"] is True
    assert door_events() == []
    assert stored_keys() == []
    assert stills.call_count == 0
    assert logged(caplog, "motion_not_door")["zones_source"] == "fallback"


# Not suspect keeps the setup result
@respx.mock
def test_not_suspect_keeps_the_setup_result(aws, ring_http, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    serve_clip(tmp_path, [(8500, 13_000)], duration_ms=27_000)
    serve_stills()
    out = run_setup(ring_http, SETUP_BLUE, 27_000, tmp_path)
    assert out["outcome"] == "door_open"
    assert "suspect" not in out
    assert not [r for r in caplog.records if '"door_check_suspect"' in r.getMessage()]
    assert logged(caplog, "door_event_recorded")["zones_source"] == "setup"


@pytest.fixture
def follows_camera(monkeypatch):
    """A stored closed anchor (a plain grey frame), so every event aligns and is sampled."""
    from fridgesense import alignment

    grey = Image.new("RGB", (320, 180), (128, 128, 128))
    anchor = alignment.edges_to_bytes(alignment.edge_map(grey))
    monkeypatch.setattr(
        door_events_module,
        "_follow_plan",
        lambda table, account_id, device_id, check: door_events_module.FollowPlan(anchor, 0, 0),
    )


def door_samples() -> list[dict]:
    return FridgeTable().query(STATE["account_id"], "DOORSAMPLE#")


# No sample from a suspect event
@respx.mock
def test_no_sample_from_a_suspect_event(aws, ring_http, tmp_path, follows_camera):
    serve_clip(tmp_path, [(8500, 13_000)], duration_ms=27_000)
    serve_stills()
    out = run_setup(ring_http, MISCALIBRATED, 27_000, tmp_path)
    assert out["suspect"] is True
    assert door_samples() == []


# Normal event still samples
@respx.mock
def test_normal_event_still_samples(aws, ring_http, tmp_path, follows_camera):
    serve_clip(tmp_path, [(8500, 13_000)], duration_ms=27_000)
    serve_stills()
    out = run_setup(ring_http, SETUP_BLUE, 27_000, tmp_path)
    assert "suspect" not in out
    assert len(door_samples()) == 1


def suspect_streak() -> int:
    from fridgesense import alignment

    s = alignment.load_alignment(FridgeTable(), STATE["account_id"], STATE["device_id"])
    return 0 if s is None else s.suspect_streak


@respx.mock
def test_suspect_event_counts_and_a_normal_one_resets(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(8500, 13_000)], duration_ms=27_000)
    serve_stills()
    run_setup(ring_http, MISCALIBRATED, 27_000, tmp_path)
    assert suspect_streak() == 1
    run_setup(ring_http, SETUP_BLUE, 27_000, tmp_path)  # same event again: a duplicate
    assert suspect_streak() == 0


@respx.mock
def test_default_rules_leave_the_streak(aws, ring_http, tmp_path):
    from fridgesense import alignment

    alignment.record_suspect(FridgeTable(), STATE["account_id"], STATE["device_id"], True)
    serve_clip(tmp_path, [(8500, 13_000)], duration_ms=27_000)
    serve_stills()
    run_setup(ring_http, None, 27_000, tmp_path)
    assert suspect_streak() == 1


# Streak write fails
@respx.mock
def test_streak_write_fails(aws, ring_http, tmp_path, caplog, monkeypatch):
    from fridgesense import alignment

    def broken(*args):
        raise RuntimeError("table down")

    monkeypatch.setattr(alignment, "record_suspect", broken)
    caplog.set_level(logging.INFO)
    serve_clip(tmp_path, [(8500, 13_000)], duration_ms=27_000)
    serve_stills()
    out = run_setup(ring_http, MISCALIBRATED, 27_000, tmp_path)
    assert out["outcome"] == "door_open"
    assert logged(caplog, "suspect_streak_failed")["error"] == "RuntimeError"
