"""door-calibration: camera snapshots (blurred, downscaled, never stored)."""

import base64
import io
import json

import boto3
import httpx
import pytest
import respx
from botocore.stub import Stubber
from PIL import Image, ImageStat

from fridgesense.camera import NoFootage, SnapshotFailed, snapshot
from fridgesense.faces import FaceBlurrer, enlarge_box
from fridgesense.oauth import OAUTH_URL, OAuthClient, OAuthUnavailable
from fridgesense.ring import API_BASE, RingClient
from fridgesense.store import Tokens
from tests.conftest import MemoryTokenStore, checkerboard_jpeg, color_jpeg, load_fixture

NOW = 1792092010.0  # 2026-10-15T19:20:10Z
DEVICE = "ava1.ring.device.D1"
DOWNLOAD = f"{API_BASE}/v1/devices/{DEVICE}/media/image/download"
LINK = "https://dl.example.com/snap"
HISTORY = f"{API_BASE}/v1/history/devices/{DEVICE}/events"


@pytest.fixture
def rekognition():
    client = boto3.client(
        "rekognition",
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    with Stubber(client) as stub:
        yield client, stub


def ring_and_http(expires_in: int = 3600):
    tokens = Tokens(
        account_id="ava1.ring.account.A1",
        access_token="at1",
        refresh_token="rt1",
        expires_at=int(NOW) + expires_in,
        link_status="linked",
    )
    http = httpx.Client()
    return RingClient(
        http, MemoryTokenStore(tokens), OAuthClient(http, "c", "s"), lambda: NOW
    ), http


class Sleeps(list):
    def __call__(self, seconds):
        self.append(seconds)


def take(rekognition, sleep=None, expires_in=3600):
    client, _ = rekognition
    ring, http = ring_and_http(expires_in)
    with http:
        return snapshot(
            ring,
            http,
            FaceBlurrer(client),
            DEVICE,
            int(NOW * 1000),
            Sleeps() if sleep is None else sleep,
        )


def faces_found(stub, response: dict) -> None:
    stub.add_response("detect_faces", response)


def size(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


# Snapshot taken
@respx.mock
def test_snapshot_taken(aws, rekognition):
    post = respx.post(DOWNLOAD).respond(303, headers={"Location": LINK})
    get = respx.get(LINK).respond(200, content=color_jpeg((90, 120, 150), size=(1920, 1080)))
    faces_found(rekognition[1], {"FaceDetails": []})
    image, captured_ms = take(rekognition)
    assert json.loads(post.calls.last.request.content) == {
        "type": "at_timestamp",
        "timestamp": 1792092007000,
        "image_options": {"format": "jpeg"},
    }
    assert "authorization" not in get.calls.last.request.headers
    assert captured_ms == 1792092007000
    assert size(image) == (960, 540)
    assert len(image) <= 300_000
    # nothing stored
    assert (
        boto3.client("s3").list_objects_v2(Bucket="fridgesense-stills-test").get("KeyCount", 0) == 0
    )


def test_narrow_still_is_not_enlarged(aws, rekognition):
    with respx.mock:
        respx.post(DOWNLOAD).respond(303, headers={"Location": LINK})
        respx.get(LINK).respond(200, content=color_jpeg(size=(640, 360)))
        faces_found(rekognition[1], {"FaceDetails": []})
        image, _ = take(rekognition)
    assert size(image) == (640, 360)


def test_busy_still_stays_under_300_kb(aws, rekognition):
    noise = Image.effect_noise((1920, 1080), 120).convert("RGB")
    buf = io.BytesIO()
    noise.save(buf, format="JPEG", quality=95)
    with respx.mock:
        respx.post(DOWNLOAD).respond(303, headers={"Location": LINK})
        respx.get(LINK).respond(200, content=buf.getvalue())
        faces_found(rekognition[1], {"FaceDetails": []})
        image, _ = take(rekognition)
    assert len(image) <= 300_000


# Face blurred in the snapshot
@respx.mock
def test_face_blurred_in_the_snapshot(aws, rekognition):
    respx.post(DOWNLOAD).respond(303, headers={"Location": LINK})
    respx.get(LINK).respond(200, content=checkerboard_jpeg(size=(1920, 1080), square=16))
    faces_found(rekognition[1], load_fixture("rekognition/detect_faces_one.json"))
    image, _ = take(rekognition)
    img = Image.open(io.BytesIO(image)).convert("L")
    x, y, w, h = enlarge_box((0.40, 0.20, 0.20, 0.30))
    W, H = img.size
    face = img.crop(
        (round(x * W) + 4, round(y * H) + 4, round((x + w) * W) - 4, round((y + h) * H) - 4)
    )
    assert ImageStat.Stat(face).stddev[0] < 10


def requested_times(post) -> list[int]:
    return [json.loads(c.request.content)["timestamp"] for c in post.calls]


# Snapshot from the latest motion event
@respx.mock
def test_snapshot_from_the_latest_motion_event(aws, rekognition):
    latest = 1786715608500

    def answer(request):
        if json.loads(request.content)["timestamp"] == latest:
            return httpx.Response(303, headers={"Location": LINK})
        return httpx.Response(416, json={"errors": [{"code": "MEDIA_NOT_FOUND"}]})

    post = respx.post(DOWNLOAD).mock(side_effect=answer)
    history = respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events.json"))
    respx.get(LINK).respond(200, content=color_jpeg(size=(960, 540)))
    faces_found(rekognition[1], {"FaceDetails": []})
    image, captured_ms = take(rekognition)
    assert requested_times(post) == [1792092007000, 1792092007000, latest]
    assert history.calls.last.request.url.params["event_types"] == "motion"
    assert captured_ms == latest
    assert size(image) == (960, 540)


@respx.mock
def test_latest_event_without_end_uses_its_start(aws, rekognition):
    attrs = {"event_type": "motion", "start": 1786715596000}
    events = {"data": [{"id": "e1", "attributes": attrs}]}
    post = respx.post(DOWNLOAD).mock(
        side_effect=lambda r: (
            httpx.Response(303, headers={"Location": LINK})
            if json.loads(r.content)["timestamp"] == 1786715596000
            else httpx.Response(416)
        )
    )
    respx.get(HISTORY).respond(200, json=events)
    respx.get(LINK).respond(200, content=color_jpeg(size=(960, 540)))
    faces_found(rekognition[1], {"FaceDetails": []})
    _, captured_ms = take(rekognition)
    assert captured_ms == 1786715596000
    assert requested_times(post)[-1] == 1786715596000


# No recent footage
@respx.mock
@pytest.mark.parametrize("status", [416, 425])
def test_no_recent_footage(aws, rekognition, status):
    post = respx.post(DOWNLOAD).respond(status, json={"errors": [{"status": str(status)}]})
    respx.get(HISTORY).respond(200, json={"data": []})
    sleeps = Sleeps()
    with pytest.raises(NoFootage):
        take(rekognition, sleeps)
    assert post.call_count == 2
    assert sleeps == [2]


@respx.mock
@pytest.mark.parametrize("history_status", [500, 503])
def test_no_recent_footage_when_history_unreadable(aws, rekognition, history_status):
    respx.post(DOWNLOAD).respond(416)
    respx.get(HISTORY).respond(history_status)
    with pytest.raises(NoFootage):
        take(rekognition)


@respx.mock
def test_no_recent_footage_when_latest_event_has_no_still(aws, rekognition):
    post = respx.post(DOWNLOAD).respond(416)
    respx.get(HISTORY).respond(200, json=load_fixture("ring/history_events.json"))
    with pytest.raises(NoFootage):
        take(rekognition)
    assert requested_times(post)[-1] == 1786715608500


@respx.mock
def test_second_attempt_succeeds(aws, rekognition):
    answers = iter([httpx.Response(416), httpx.Response(303, headers={"Location": LINK})])
    respx.post(DOWNLOAD).mock(side_effect=lambda r: next(answers))
    respx.get(LINK).respond(200, content=color_jpeg(size=(960, 540)))
    faces_found(rekognition[1], {"FaceDetails": []})
    image, _ = take(rekognition)
    assert size(image) == (960, 540)


# Camera or face detection unavailable
@respx.mock
def test_ring_error_is_unavailable(aws, rekognition):
    respx.post(DOWNLOAD).respond(500)
    with pytest.raises(SnapshotFailed):
        take(rekognition)


@respx.mock
def test_token_refresh_failure_is_unavailable(aws, rekognition, monkeypatch):
    def fail(*args, **kwargs):
        raise OAuthUnavailable("down")

    monkeypatch.setattr(OAuthClient, "refresh", fail)
    respx.post(DOWNLOAD).respond(303, headers={"Location": LINK})
    with pytest.raises(SnapshotFailed):
        take(rekognition, expires_in=-10)


@respx.mock
def test_face_detection_failure_returns_no_image(aws, rekognition):
    respx.post(DOWNLOAD).respond(303, headers={"Location": LINK})
    respx.get(LINK).respond(200, content=color_jpeg(size=(960, 540)))
    rekognition[1].add_client_error("detect_faces", "InternalServerError")
    with pytest.raises(SnapshotFailed):
        take(rekognition)


def test_snapshot_is_base64_safe():
    # The API sends the bytes as base64; make sure a snapshot round-trips.
    data = color_jpeg(size=(960, 540))
    assert base64.b64decode(base64.b64encode(data)) == data


# Camera unavailable: the refreshed Ring token can't be saved (the API may only read secrets)
@respx.mock
def test_token_save_denied_is_unavailable(aws, rekognition, monkeypatch):
    from botocore.exceptions import ClientError

    from tests.conftest import MemoryTokenStore

    def denied(self, tokens):
        raise ClientError({"Error": {"Code": "AccessDeniedException"}}, "PutSecretValue")

    monkeypatch.setattr(MemoryTokenStore, "save", denied)
    respx.post(OAUTH_URL).respond(200, json=load_fixture("ring/oauth_refresh.json"))
    respx.post(DOWNLOAD).respond(303, headers={"Location": LINK})
    with pytest.raises(SnapshotFailed):
        take(rekognition, expires_in=-10)
