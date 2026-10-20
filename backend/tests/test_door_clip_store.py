"""door-event-detection: the open-span clip stored for each door opening."""

import logging

import boto3
import respx

from fridgesense import clip_frames
from fridgesense.clip_frames import ClipUnavailable
from tests import test_fetch_stills_clip as clip_tests
from tests.clip_video import door_clip
from tests.conftest import BUCKET
from tests.test_fetch_stills_clip import (
    CLIP_LINK,
    CLIP_URL,
    STATE,
    logged,
    run,
    serve_stills,
)
from tests.test_fetch_stills_task import (
    PREFIX,
    door_events,
    ring_serves,
    stills_open_at,
    stored_keys,
)

CLIP_KEY = f"{PREFIX}clip.mp4"
RAW_KEY = f"{PREFIX}clip-raw.mp4"
ANALYSIS_KEY = f"{PREFIX}analysis.mp4"
ring_http = clip_tests.ring_http  # the fixture


def serve_clip(tmp_path, open_ms, duration_ms=20_000) -> int:
    """Ring answers the clip request with a 303 to a 2 s-GOP MP4; returns its size."""
    src = door_clip(tmp_path / "served.mp4", open_ms, duration_ms, gop=8)
    data = src.read_bytes()
    src.unlink()
    respx.post(CLIP_URL).respond(303, headers={"Location": CLIP_LINK})
    respx.get(CLIP_LINK).respond(200, content=data)
    return len(data)


def stored_size(key: str) -> int:
    return boto3.client("s3").head_object(Bucket=BUCKET, Key=key)["ContentLength"]


# Clip cut to the open span
@respx.mock
def test_clip_cut_to_the_open_span(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(4500, 12_500)])
    serve_stills()
    out = run(ring_http, clip_dir=tmp_path, face_blur=False)
    assert out["outcome"] == "door_open"
    [event] = door_events()
    assert event["clip_key"] == CLIP_KEY
    assert [float(s) for s in event["clip_span"]] == [0.5, 8.5]
    head = boto3.client("s3").head_object(Bucket=BUCKET, Key=CLIP_KEY)
    assert head["ContentType"] == "video/mp4"


# Door opening processed: stills and one shorter clip.mp4
@respx.mock
def test_door_opening_processed(aws, ring_http, tmp_path):
    served = serve_clip(tmp_path, [(4500, 12_500)])
    serve_stills()
    run(ring_http, clip_dir=tmp_path, face_blur=False)
    keys = stored_keys()
    # the fetch step's videos: clip.mp4 and the transient analysis.mp4 (deleted by analyze)
    assert [k for k in keys if k.endswith(".mp4")] == [ANALYSIS_KEY, CLIP_KEY]
    assert all(
        k in (CLIP_KEY, ANALYSIS_KEY) or (k.startswith(f"{PREFIX}still-") and k.endswith(".jpg"))
        for k in keys
    )
    assert stored_size(CLIP_KEY) < served


# Temporary file removed after the cut
@respx.mock
def test_temporary_file_removed_after_the_cut(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(4500, 12_500)])
    serve_stills()
    run(ring_http, clip_dir=tmp_path, face_blur=False)
    assert CLIP_KEY in stored_keys()
    assert list(tmp_path.iterdir()) == []


# No clip on the fallback path
@respx.mock
def test_no_clip_on_the_fallback_path(aws, ring_http, tmp_path):
    respx.post(CLIP_URL).respond(403)
    ring_serves(stills_open_at(set(range(6, 16))))
    out = run(ring_http, state=STATE, clip_dir=tmp_path, face_blur=False)
    assert out["outcome"] == "door_open"
    assert not any(k.endswith(".mp4") for k in stored_keys())
    [event] = door_events()
    assert "clip_key" not in event


# Not a door opening
@respx.mock
def test_not_a_door_opening_stores_no_clip(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [])
    serve_stills()
    assert run(ring_http, clip_dir=tmp_path, face_blur=False)["outcome"] == "not_door"
    assert stored_keys() == []


# Cut fails
@respx.mock
def test_cut_fails(aws, ring_http, tmp_path, caplog, monkeypatch):
    caplog.set_level(logging.INFO)

    def broken(*args, **kwargs):
        raise ClipUnavailable("cut_failed")

    monkeypatch.setattr(clip_frames, "cut_clip", broken)
    serve_clip(tmp_path, [(4500, 12_500)])
    serve_stills()
    out = run(ring_http, clip_dir=tmp_path, face_blur=False)
    assert out["outcome"] == "door_open"
    assert len(out["still_keys"]) == 4
    assert logged(caplog, "clip_not_stored")["reason"] == "cut_failed"
    [event] = door_events()
    assert "clip_key" not in event and "clip_span" not in event
    assert CLIP_KEY not in stored_keys()
    assert list(tmp_path.iterdir()) == []


# Upload fails
@respx.mock
def test_upload_fails(aws, ring_http, tmp_path, caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    real = boto3.client

    def client(name, *args, **kwargs):
        s3 = real(name, *args, **kwargs)
        if name != "s3":
            return s3
        put = s3.put_object

        def put_object(**params):
            if params["Key"].endswith(".mp4"):
                raise RuntimeError("S3 said no")
            return put(**params)

        s3.put_object = put_object
        return s3

    monkeypatch.setattr(boto3, "client", client)
    serve_clip(tmp_path, [(4500, 12_500)])
    serve_stills()
    out = run(ring_http, clip_dir=tmp_path, face_blur=False)
    assert out["outcome"] == "door_open"
    assert logged(caplog, "clip_not_stored")["reason"] == "upload_failed"
    [event] = door_events()
    assert "clip_key" not in event
    assert list(tmp_path.iterdir()) == []


def tags(key: str) -> dict:
    tagging = boto3.client("s3").get_object_tagging(Bucket=BUCKET, Key=key)
    return {t["Key"]: t["Value"] for t in tagging["TagSet"]}


# Raw clip while blurring is on
@respx.mock
def test_raw_clip_while_blurring_is_on(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(4500, 12_500)])
    serve_stills()
    out = run(ring_http, clip_dir=tmp_path, face_blur=True)
    assert out["outcome"] == "door_open"
    assert out["clip"] == {"raw_key": RAW_KEY, "clip_span": [0.5, 8.5]}
    assert tags(RAW_KEY) == {"transient": "true"}
    assert CLIP_KEY not in stored_keys()
    [event] = door_events()
    assert "clip_key" not in event and "clip_span" not in event


# Door opening processed with blurring on (FetchStills' part: only the raw clip so far)
@respx.mock
def test_door_opening_processed_with_blurring_on(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [(4500, 12_500)])
    serve_stills()
    run(ring_http, clip_dir=tmp_path, face_blur=True)
    keys = stored_keys()
    # after the fetch step; the analyze and blur steps remove both (see the pipeline e2e test)
    assert [k for k in keys if k.endswith(".mp4")] == [ANALYSIS_KEY, RAW_KEY]
    assert list(tmp_path.iterdir()) == []


# Upload fails (the raw clip)
@respx.mock
def test_raw_upload_fails(aws, ring_http, tmp_path, caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    real = boto3.client

    def client(name, *args, **kwargs):
        s3 = real(name, *args, **kwargs)
        if name != "s3":
            return s3
        put = s3.put_object

        def put_object(**params):
            if params["Key"].endswith(".mp4"):
                raise RuntimeError("S3 said no")
            return put(**params)

        s3.put_object = put_object
        return s3

    monkeypatch.setattr(boto3, "client", client)
    serve_clip(tmp_path, [(4500, 12_500)])
    serve_stills()
    out = run(ring_http, clip_dir=tmp_path, face_blur=True)
    assert out["outcome"] == "door_open"
    assert "clip" not in out
    assert logged(caplog, "clip_not_stored")["reason"] == "upload_failed"
    [event] = door_events()
    assert "clip_key" not in event


# Not a door opening (blurring on): no raw clip either
@respx.mock
def test_not_a_door_opening_stores_no_raw_clip(aws, ring_http, tmp_path):
    serve_clip(tmp_path, [])
    serve_stills()
    assert run(ring_http, clip_dir=tmp_path, face_blur=True)["outcome"] == "not_door"
    assert stored_keys() == []


# Blur error caught: DropRawClip deletes the raw clip and logs blur_failed
def test_drop_raw_clip(aws, caplog):
    from fridgesense.door_events import drop_raw_clip

    caplog.set_level(logging.INFO)
    s3 = boto3.client("s3")
    s3.put_object(Bucket=BUCKET, Key=RAW_KEY, Body=b"mp4")
    state = {**STATE, "clip": {"raw_key": RAW_KEY, "clip_span": [0.5, 8.5]}}
    out = drop_raw_clip(s3, BUCKET, {**state, "error": {"Error": "States.Timeout"}})
    assert RAW_KEY not in stored_keys()
    line = logged(caplog, "clip_not_stored")
    assert (line["reason"], line["error"]) == ("blur_failed", "States.Timeout")
    assert out["outcome"] == "clip_dropped"


def test_drop_raw_clip_already_gone(aws):
    from fridgesense.door_events import drop_raw_clip

    state = {**STATE, "clip": {"raw_key": RAW_KEY, "clip_span": [0.5, 8.5]}}
    assert drop_raw_clip(boto3.client("s3"), BUCKET, state)["outcome"] == "clip_dropped"
