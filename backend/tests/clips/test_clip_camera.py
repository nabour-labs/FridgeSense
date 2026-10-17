"""door-clip-evaluation: the clip camera answers still downloads with clip frames."""

import io

import httpx
import respx
from PIL import Image

from fridgesense.door_events import download_all_stills, fetch_still
from tests.clips.harness import EPOCH_MS, ColourSource, clip_camera, ring_client

RED, BLUE = (200, 30, 30), (30, 60, 200)
SOURCE = ColourSource([(0.0, RED), (7.0, BLUE)], duration_s=20.0, size=(640, 360))


def colour_of(jpeg: bytes) -> tuple[int, int, int]:
    return Image.open(io.BytesIO(jpeg)).convert("RGB").getpixel((320, 180))


def near(a, b, slack=12) -> bool:
    return all(abs(x - y) <= slack for x, y in zip(a, b, strict=True))


# Frame at the requested time
def test_frame_at_the_requested_time():
    with respx.mock(assert_all_mocked=True) as router, httpx.Client() as http:
        clip_camera(router, SOURCE, EPOCH_MS)
        ring = ring_client(http)
        data, status = fetch_still(ring, http, "clip.device", EPOCH_MS + 7000, lambda s: None)
        before, _ = fetch_still(ring, http, "clip.device", EPOCH_MS + 6999, lambda s: None)
    assert status is None
    img = Image.open(io.BytesIO(data))
    assert img.format == "JPEG"
    assert img.size == (640, 360)
    assert near(colour_of(data), BLUE)
    assert near(colour_of(before), RED)


# Request past the end of the clip
def test_request_past_the_end_of_the_clip():
    with respx.mock(assert_all_mocked=True) as router, httpx.Client() as http:
        clip_camera(router, SOURCE, EPOCH_MS)
        ring = ring_client(http)
        data, status = fetch_still(ring, http, "clip.device", EPOCH_MS + 25_000, lambda s: None)
        assert (data, status) == (None, 404)
        window = {"start_ms": EPOCH_MS, "end_ms": EPOCH_MS + 30_000}
        state = {"device_id": "clip.device", "window": window}
        stills = download_all_stills(ring, http, state, sleep=lambda s: None)
    missing = [s for s in stills if s.data is None]
    assert missing and all(s.status == 404 and s.at_ms > EPOCH_MS + 20_000 for s in missing)
    assert all(s.data is not None for s in stills if s.at_ms <= EPOCH_MS + 20_000)
