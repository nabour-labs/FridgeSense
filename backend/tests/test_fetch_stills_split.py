"""door-event-detection: several door openings in one motion, one door event each."""

import io

import boto3
import respx

from fridgesense.door_events import iso_utc
from tests import test_fetch_stills_clip as clip_tests
from tests.conftest import BUCKET, FakeBlurrer
from tests.test_fetch_stills_clip import START, run, serve_clip, serve_stills
from tests.test_fetch_stills_task import (
    PREFIX,
    STATE,
    door_events,
    ring_serves,
    stills_open_at,
    stored_keys,
    window_times,
)
from tests.test_fetch_stills_task import run as run_stills

ring_http = clip_tests.ring_http  # the clip tests' fake Ring, as a fixture here too
STATE30 = {**STATE, "window": {**STATE["window"], "end_ms": START + 30_000}}
TWO = [(1000, 6000), (18_000, 24_000)]  # frames open at 1000-5500 and 18000-23500 ms
DOOR_SK = "DOOR#2026-08-14T13:53:16.000Z#ava1.ring.device.D1"
DOOR_SK2 = f"{DOOR_SK}#2"
PREFIX2 = f"{PREFIX}opening-2/"


def two_openings(ring_http, tmp_path, openings=TWO, **kwargs):
    serve_clip(tmp_path, openings, 30_000)
    serve_stills()
    return run(ring_http, state=STATE30, clip_dir=tmp_path, **kwargs)


def by_sk() -> dict[str, dict]:
    return {e["sk"]: e for e in door_events()}


def at(offset_ms: int) -> str:
    return iso_utc(START + offset_ms)


def video_seconds(key: str) -> float:
    import av

    body = boto3.client("s3").get_object(Bucket=BUCKET, Key=key)["Body"].read()
    with av.open(io.BytesIO(body)) as container:
        return float(container.duration / av.time_base)


# Two openings in one clip
@respx.mock
def test_two_openings_in_one_clip(aws, ring_http, tmp_path):
    out = two_openings(ring_http, tmp_path, face_blur=False)
    assert out["outcome"] == "door_open"
    events = by_sk()
    assert sorted(events) == [DOOR_SK, DOOR_SK2]
    first, second = events[DOOR_SK], events[DOOR_SK2]
    assert (first["opened_at"], first["closed_at"], first["duration_s"]) == (
        "2026-08-14T13:53:17.000Z",
        "2026-08-14T13:53:22.000Z",
        5,
    )
    assert (second["opened_at"], second["closed_at"], second["duration_s"]) == (
        "2026-08-14T13:53:34.000Z",
        "2026-08-14T13:53:40.000Z",
        6,
    )
    assert first["ring_event_id"] == second["ring_event_id"] == "evt_1786715596000"
    assert first["status"] == second["status"] == "analyzing"


# Brief closed run in one opening
@respx.mock
def test_brief_closed_run_in_one_opening(aws, ring_http, tmp_path):
    two_openings(ring_http, tmp_path, openings=[(4000, 8500), (12_000, 14_500)], face_blur=False)
    [event] = door_events()
    assert event["sk"] == DOOR_SK
    assert (event["opened_at"], event["closed_at"]) == (at(4000), at(14_500))


# Stills from each opening
@respx.mock
def test_stills_from_each_opening(aws, ring_http, tmp_path):
    out = two_openings(ring_http, tmp_path, face_blur=False)
    first, second = out["openings"]
    assert first["still_ms"] == [START + ms for ms in (1000, 2500, 4500, 6000)]
    assert second["still_ms"] == [START + ms for ms in (18_000, 20_000, 22_000, 24_000)]
    assert first["still_keys"] == [f"{PREFIX}still-{n}.jpg" for n in range(1, 5)]
    assert second["still_keys"] == [f"{PREFIX2}still-{n}.jpg" for n in range(1, 5)]
    events = by_sk()
    assert events[DOOR_SK]["still_keys"] == first["still_keys"]
    assert events[DOOR_SK2]["still_keys"] == second["still_keys"]
    assert all(k in stored_keys() for k in first["still_keys"] + second["still_keys"])


# Keys per opening
@respx.mock
def test_keys_per_opening(aws, ring_http, tmp_path):
    out = two_openings(ring_http, tmp_path, face_blur=False)
    second = out["openings"][1]
    assert second["door_sk"] == DOOR_SK2
    assert by_sk()[DOOR_SK2]["clip_key"] == f"{PREFIX2}clip.mp4"
    assert by_sk()[DOOR_SK]["clip_key"] == f"{PREFIX}clip.mp4"
    assert second["analysis_video"]["key"] == f"{PREFIX2}analysis.mp4"
    assert out["openings"][0]["analysis_video"]["key"] == f"{PREFIX}analysis.mp4"


# Media from its own span only (blurring on: raw clips for the blur step)
@respx.mock
def test_media_from_its_own_span_only(aws, ring_http, tmp_path):
    out = two_openings(ring_http, tmp_path, face_blur=True)
    first, second = out["openings"]
    assert first["clip"]["raw_key"] == f"{PREFIX}clip-raw.mp4"
    assert second["clip"]["raw_key"] == f"{PREFIX2}clip-raw.mp4"
    assert "clip_key" not in by_sk()[DOOR_SK2]
    # each raw clip lasts about its own span (5.0 s and 6.0 s), not the 23 s from 1 s to 24 s
    assert video_seconds(first["clip"]["raw_key"]) < 7.0
    assert video_seconds(second["clip"]["raw_key"]) < 8.0
    # the analysis video starts one frame before its own span
    assert first["analysis_video"]["start_ms"] == START + 500
    assert first["analysis_video"]["frames"] == 12
    assert second["analysis_video"]["start_ms"] == START + 17_500
    assert second["analysis_video"]["frames"] == 14
    assert all(START + 1000 <= ms <= START + 6000 for ms in first["still_ms"])
    assert all(START + 18_000 <= ms <= START + 24_000 for ms in second["still_ms"])


# Output for two openings
@respx.mock
def test_output_for_two_openings(aws, ring_http, tmp_path):
    out = two_openings(ring_http, tmp_path, face_blur=True)
    assert out["outcome"] == "door_open"
    first, second = out["openings"]
    assert first["door_sk"] != second["door_sk"]
    for key in ("door_sk", "still_keys", "still_ms", "clip", "analysis_video"):
        assert out[key] == first[key]
    for opening in out["openings"]:
        assert opening["account_id"] == STATE["account_id"]
        assert opening["window"] == STATE30["window"]
        assert "openings" not in opening


# Output for one opening
@respx.mock
def test_output_for_one_opening(aws, ring_http, tmp_path):
    out = two_openings(ring_http, tmp_path, openings=[(4000, 12_500)], face_blur=True)
    [opening] = out["openings"]
    assert opening == {k: v for k, v in out.items() if k != "openings"}


class DropFirstOpening(FakeBlurrer):
    """Face detection fails for every still of the first opening only."""

    def blur(self, jpeg: bytes, context: dict) -> bytes | None:
        self.contexts.append(context)
        return None if len(self.contexts) <= 4 else jpeg


# Each opening has its own status
@respx.mock
def test_each_opening_has_its_own_status(aws, ring_http, tmp_path):
    out = two_openings(ring_http, tmp_path, face_blur=False, blurrer=DropFirstOpening())
    events = by_sk()
    assert events[DOOR_SK]["status"] == "no_media"
    assert events[DOOR_SK2]["status"] == "analyzing"
    assert out["outcome"] == "door_open"
    [opening] = out["openings"]
    assert opening["door_sk"] == DOOR_SK2
    assert out["door_sk"] == DOOR_SK2


# Two openings in a re-run
@respx.mock
def test_two_openings_in_a_rerun(aws, ring_http, tmp_path):
    two_openings(ring_http, tmp_path, face_blur=True)
    again = run(ring_http, state=STATE30, clip_dir=tmp_path, face_blur=True)
    assert again["outcome"] == "duplicate"
    assert sorted(by_sk()) == [DOOR_SK, DOOR_SK2]
    assert [k for k in stored_keys() if k.endswith("clip-raw.mp4")] == []


# Two openings in one window (stills path: 30 stills about a second apart)
@respx.mock
def test_two_openings_in_one_window(aws, ring_http):
    ring_serves(stills_open_at(set(range(3, 7)) | set(range(20, 25)), 30), state=STATE30)
    out = run_stills(ring_http, state=STATE30)
    times = window_times(STATE30)
    assert out["outcome"] == "door_open"
    events = by_sk()
    assert sorted(events) == [DOOR_SK, DOOR_SK2]
    first, second = events[DOOR_SK], events[DOOR_SK2]
    assert (first["opened_at"], first["closed_at"]) == (iso_utc(times[2]), iso_utc(times[6]))
    assert (second["opened_at"], second["closed_at"]) == (iso_utc(times[19]), iso_utc(times[24]))
    assert first["duration_s"] == round((times[6] - times[2]) / 1000)
    assert second["duration_s"] == round((times[24] - times[19]) / 1000)
