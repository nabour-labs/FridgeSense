"""door-event-detection: the analysis video stored by the fetch-stills step."""

import io
import json
import logging

import boto3
import respx
from botocore.exceptions import ClientError

from fridgesense.table import FridgeTable
from tests import test_fetch_stills_clip as clip_tests
from tests.conftest import BUCKET, FakeBlurrer, color_jpeg
from tests.test_fetch_stills_clip import (
    CLIP_URL,
    START,
    STATE20,
    run,
    serve_clip,
    serve_stills,
)
from tests.test_fetch_stills_task import PREFIX, STATE, ring_serves, stills_open_at

ring_http = clip_tests.ring_http  # the clip tests' fake Ring, as a fixture here too
VIDEO_KEY = f"{PREFIX}analysis.mp4"
AREA = (0.25, 0.2, 0.5, 0.6)  # analysis box (0.2, 0.17, 0.6, 0.66): 192x118 of 320x180


def decode(data: bytes) -> tuple[int, tuple[int, int], float]:
    """(frames, (width, height), duration s) of an MP4."""
    import av

    with av.open(io.BytesIO(data)) as container:
        stream = container.streams.video[0]
        frames = [f for f in container.decode(stream)]
        duration = float(container.duration / av.time_base)
        return len(frames), (frames[0].width, frames[0].height), duration


def tags(key: str) -> dict:
    tagging = boto3.client("s3").get_object_tagging(Bucket=BUCKET, Key=key)["TagSet"]
    return {t["Key"]: t["Value"] for t in tagging}


# Short opening
@respx.mock
def test_short_opening(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(1000, 5500)])  # frames open at 1000-5000 ms (indexes 2-10)
    serve_stills()
    out = run(ring_http, clip_dir=tmp_path, face_blur=False, area_for=lambda a, d: AREA)
    assert out["outcome"] == "door_open"
    assert out["analysis_video"] == {
        "key": VIDEO_KEY,
        "start_ms": START + 500,
        "frame_ms": 500,
        "frames": 11,
    }
    body = boto3.client("s3").get_object(Bucket=BUCKET, Key=VIDEO_KEY)["Body"].read()
    frames, (w, h), duration = decode(body)
    assert frames == 11
    assert abs(w - 192) <= 2 and abs(h - 118) <= 2
    assert abs(duration - 11.0) <= 0.5
    assert tags(VIDEO_KEY) == {"transient": "true"}


def stored_videos() -> list[str]:
    listing = boto3.client("s3").list_objects_v2(Bucket=BUCKET)
    return sorted(o["Key"] for o in listing.get("Contents", []) if o["Key"].endswith(".mp4"))


def logged(caplog, event: str) -> dict:
    [line] = [r.getMessage() for r in caplog.records if f'"{event}"' in r.getMessage()]
    return json.loads(line)


def door_event() -> dict:
    [event] = [
        i
        for i in FridgeTable().query(STATE20["account_id"], "DOOR#")
        if i["sk"].startswith("DOOR#")
    ]
    return event


# Encoding or upload fails
@respx.mock
def test_encoding_fails(aws, ring_http, tmp_path, caplog, monkeypatch):
    from fridgesense import clip_frames

    def broken(images):
        raise RuntimeError("no encoder")

    monkeypatch.setattr(clip_frames, "encode_video", broken)
    caplog.set_level(logging.INFO)
    serve_clip(tmp_path, [(1000, 5500)])
    serve_stills()
    out = run(ring_http, clip_dir=tmp_path, face_blur=False)
    assert out["outcome"] == "door_open"
    assert "analysis_video" not in out
    assert len(out["still_keys"]) == 4
    assert logged(caplog, "analysis_video_not_stored")["reason"] == "encode_failed"


@respx.mock
def test_upload_fails(aws, ring_http, tmp_path, caplog, monkeypatch):
    real = boto3.client

    def client(name, *args, **kwargs):
        c = real(name, *args, **kwargs)
        if name == "s3":
            put = c.put_object

            def picky(**kw):
                if kw["Key"].endswith("analysis.mp4"):
                    raise ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")
                return put(**kw)

            c.put_object = picky
        return c

    monkeypatch.setattr(boto3, "client", client)
    caplog.set_level(logging.INFO)
    serve_clip(tmp_path, [(1000, 5500)])
    serve_stills()
    out = run(ring_http, clip_dir=tmp_path, face_blur=False)
    assert out["outcome"] == "door_open"
    assert "analysis_video" not in out
    assert logged(caplog, "analysis_video_not_stored")["reason"] == "upload_failed"


# No video on the fallback path
@respx.mock
def test_no_video_on_the_fallback_path(aws, ring_http, tmp_path):
    respx.post(CLIP_URL).respond(403, json={"code": "TIME_RANGE_NOT_AUTHORIZED"})
    ring_serves(stills_open_at(set(range(6, 16))))
    out = run(ring_http, state=STATE, clip_dir=tmp_path)
    assert out["outcome"] == "door_open"
    assert "analysis_video" not in out
    assert stored_videos() == []


# Not a door opening
@respx.mock
def test_no_video_when_not_a_door_opening(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [])
    serve_stills()
    out = run(ring_http, clip_dir=tmp_path)
    assert out["outcome"] == "not_door"
    assert stored_videos() == []


@respx.mock
def test_no_new_video_for_a_duplicate(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(1000, 5500)])
    serve_stills()
    first = run(ring_http, clip_dir=tmp_path, face_blur=False)
    s3 = boto3.client("s3")
    s3.delete_object(Bucket=BUCKET, Key=first["analysis_video"]["key"])
    serve_clip(tmp_path, [(1000, 5500)])
    second = run(ring_http, clip_dir=tmp_path, face_blur=False)
    assert second["outcome"] == "duplicate"
    assert "analysis_video" not in second
    assert VIDEO_KEY not in stored_videos()


# Built while face blurring is on
@respx.mock
def test_built_while_face_blurring_is_on(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(1000, 5500)])
    serve_stills()
    black = color_jpeg((0, 0, 0))  # the fake blurrer turns every still black
    out = run(ring_http, clip_dir=tmp_path, blurrer=FakeBlurrer(blurred=lambda d: black))
    assert out["outcome"] == "door_open"
    s3 = boto3.client("s3")
    still = s3.get_object(Bucket=BUCKET, Key=out["still_keys"][0])["Body"].read()
    assert still == black  # stored stills are the blurred ones
    video = s3.get_object(Bucket=BUCKET, Key=VIDEO_KEY)["Body"].read()
    assert first_frame(video).convert("L").getextrema()[1] > 60  # the video is not blurred
    event = door_event()
    assert not any("analysis.mp4" in str(v) for v in event.values())


def first_frame(data: bytes):
    import av

    with av.open(io.BytesIO(data)) as container:
        return next(container.decode(container.streams.video[0])).to_image()


# Times match the stored stills
@respx.mock
def test_times_match_the_stored_stills(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(1000, 5500)])  # open span indexes 2-11: picks 2, 5, 8, 11
    serve_stills()
    out = run(ring_http, clip_dir=tmp_path, face_blur=False)
    assert out["still_ms"] == [START + 1000, START + 2500, START + 4000, START + 5500]
    assert len(out["still_keys"]) == 4


# Still dropped by face detection
@respx.mock
def test_still_dropped_by_face_detection(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(1000, 5500)])
    serve_stills()
    out = run(ring_http, clip_dir=tmp_path, blurrer=FakeBlurrer(drop={2}))
    assert [k.rsplit("/", 1)[1] for k in out["still_keys"]] == [
        "still-1.jpg",
        "still-3.jpg",
        "still-4.jpg",
    ]
    assert out["still_ms"] == [START + 1000, START + 4000, START + 5500]
