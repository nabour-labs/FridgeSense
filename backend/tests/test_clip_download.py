"""door-event-detection: downloading the event clip (door check on the event clip, fallback)."""

import json

import httpx
import pytest
import respx

from fridgesense.clip_frames import ClipUnavailable, download_clip
from fridgesense.oauth import OAuthClient
from fridgesense.ring import API_BASE, RingClient
from fridgesense.store import Tokens
from tests.conftest import MemoryTokenStore, load_fixture

NOW = 1_786_715_700.0
DEVICE = "ava1.ring.device.D1"
CLIP_URL = f"{API_BASE}/v1/devices/{DEVICE}/media/video/download"
LINK = "https://download-us-east-1.prod.phoenix.devices.amazon.dev/v1/download?req_id=1"
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"x" * 1000
START, DURATION = 1786715596000, 20000


@pytest.fixture
def ring_http():
    tokens = Tokens(
        account_id="ava1.ring.account.A1",
        access_token="at1",
        refresh_token="rt1",
        expires_at=int(NOW) + 3600,
        link_status="linked",
    )
    with httpx.Client() as http:
        ring = RingClient(http, MemoryTokenStore(tokens), OAuthClient(http, "c", "s"), lambda: NOW)
        yield ring, http


def download(ring_http, tmp_path, sleeps=None, **kw):
    ring, http = ring_http
    sleep = sleeps.append if sleeps is not None else lambda s: None
    return download_clip(ring, http, DEVICE, START, DURATION, sleep, directory=tmp_path, **kw)


def redirect():
    return httpx.Response(303, headers={"Location": LINK, "Content-Length": "0"})


def not_found():
    return httpx.Response(416, json=load_fixture("ring/video_media_not_found.json")["body"])


def reason_of(ring_http, tmp_path, **kw) -> str:
    with pytest.raises(ClipUnavailable) as e:
        download(ring_http, tmp_path, **kw)
    return e.value.reason


# One clip request per event (body)
@respx.mock
def test_one_clip_request_per_event(ring_http, tmp_path):
    post = respx.post(CLIP_URL).mock(return_value=redirect())
    respx.get(LINK).respond(200, content=MP4)
    path = download(ring_http, tmp_path)
    assert post.call_count == 1
    assert json.loads(post.calls[0].request.content) == {"timestamp": START, "duration": DURATION}
    assert path.read_bytes() == MP4
    assert path.parent == tmp_path


def test_recorded_303_shape():
    recorded = load_fixture("ring/video_download_303.json")
    assert recorded["status"] == 303
    assert set(recorded["request"]) == {"timestamp", "duration"}
    assert recorded["headers"]["location"].startswith("https://")


# Clip link gets no token
@respx.mock
def test_clip_link_gets_no_token(ring_http, tmp_path):
    respx.post(CLIP_URL).mock(return_value=redirect())
    link = respx.get(LINK).respond(200, content=MP4)
    download(ring_http, tmp_path)
    assert respx.calls[0].request.headers["Authorization"] == "Bearer at1"
    assert "Authorization" not in link.calls[0].request.headers


# Clip not ready yet: 425 on the request, then the clip
@respx.mock
def test_clip_request_not_ready_then_ready(ring_http, tmp_path):
    post = respx.post(CLIP_URL).mock(
        side_effect=[httpx.Response(425, json={"code": "RECORDING_NOT_READY"}), redirect()]
    )
    respx.get(LINK).respond(200, content=MP4)
    sleeps = []
    path = download(ring_http, tmp_path, sleeps=sleeps)
    assert post.call_count == 2
    assert sleeps == [3]
    assert path.read_bytes() == MP4


# Clip not ready yet: 416 MEDIA_NOT_FOUND on the link, then the clip
@respx.mock
def test_clip_link_not_found_then_ready(ring_http, tmp_path):
    post = respx.post(CLIP_URL).mock(return_value=redirect())
    respx.get(LINK).mock(side_effect=[not_found(), httpx.Response(200, content=MP4)])
    path = download(ring_http, tmp_path)
    assert post.call_count == 2  # the whole request is repeated
    assert path.read_bytes() == MP4


# Ring refuses the clip
@respx.mock
def test_ring_refuses_the_clip(ring_http, tmp_path):
    respx.post(CLIP_URL).respond(403, json={"code": "TIME_RANGE_NOT_AUTHORIZED"})
    assert reason_of(ring_http, tmp_path) == "status_403"
    assert list(tmp_path.iterdir()) == []


# Clip never ready (link answers 416 every time)
@respx.mock
def test_clip_never_ready(ring_http, tmp_path):
    post = respx.post(CLIP_URL).mock(return_value=redirect())
    respx.get(LINK).mock(side_effect=lambda r: not_found())
    sleeps = []
    assert reason_of(ring_http, tmp_path, sleeps=sleeps) == "status_416"
    assert post.call_count == 3
    assert sleeps == [3, 6]
    assert list(tmp_path.iterdir()) == []


# Clip request never ready (425 every time)
@respx.mock
def test_clip_request_never_ready(ring_http, tmp_path):
    post = respx.post(CLIP_URL).respond(425, json={"code": "RECORDING_NOT_READY"})
    assert reason_of(ring_http, tmp_path) == "status_425"
    assert post.call_count == 3


# Network error
@respx.mock
def test_network_error(ring_http, tmp_path):
    respx.post(CLIP_URL).mock(side_effect=httpx.ConnectError("boom"))
    assert reason_of(ring_http, tmp_path) == "download_failed"


@respx.mock
def test_network_error_on_link(ring_http, tmp_path):
    respx.post(CLIP_URL).mock(return_value=redirect())
    respx.get(LINK).mock(side_effect=httpx.ReadTimeout("slow"))
    assert reason_of(ring_http, tmp_path) == "download_failed"
    assert list(tmp_path.iterdir()) == []


# Clip too large (announced)
@respx.mock
def test_clip_too_large_by_content_length(ring_http, tmp_path):
    respx.post(CLIP_URL).mock(return_value=redirect())
    respx.get(LINK).respond(200, content=MP4, headers={"Content-Length": "5000"})
    assert reason_of(ring_http, tmp_path, max_bytes=4000) == "too_large"
    assert list(tmp_path.iterdir()) == []


# Clip too large (while streaming)
@respx.mock
def test_clip_too_large_while_streaming(ring_http, tmp_path):
    respx.post(CLIP_URL).mock(return_value=redirect())

    def chunks():
        for _ in range(10):
            yield b"x" * 1000

    respx.get(LINK).mock(return_value=httpx.Response(200, content=chunks()))
    assert reason_of(ring_http, tmp_path, max_bytes=4000) == "too_large"
    assert list(tmp_path.iterdir()) == []


def test_default_cap_is_300_mb():
    from fridgesense.clip_frames import MAX_CLIP_BYTES

    assert MAX_CLIP_BYTES == 300_000_000
