"""door-event-detection: the door check follows the camera (aligned zones, recorded shift)."""

import io
import json
import logging
import random

import boto3
import pytest
import respx
from PIL import Image, ImageDraw

from fridgesense import alignment, door_calibration
from fridgesense.door_events import DoorCheck, fetch_stills
from fridgesense.table import FridgeTable, account_pk
from fridgesense.traces import TraceWriter
from tests import test_fetch_stills_clip as clip_tests
from tests.clip_video import write_images
from tests.conftest import BUCKET, FakeBlurrer
from tests.test_fetch_stills_clip import CLIP_LINK, CLIP_URL, START, STATE20, serve_stills
from tests.test_fetch_stills_task import PREFIX

ACCOUNT, DEVICE = STATE20["account_id"], STATE20["device_id"]
ring_http = clip_tests.ring_http  # the shared Ring client fixture
W, H = 640, 360  # 5 px here is 1 px at the 128x72 alignment size
MARGIN = 80
ZONE = (0.38, 0.32, 0.04, 0.30)  # narrower than a 6 px shift (0.047), so only alignment finds it
LIT = (30, 80, 210)
DEFAULT = DoorCheck(zones=((0.0, 0.0, 0.1, 0.1),), threshold=0.5)


def scene(lit: bool) -> Image.Image:
    rng = random.Random(3)
    img = Image.new("RGB", (W + 2 * MARGIN, H + 2 * MARGIN), (120, 120, 120))
    draw = ImageDraw.Draw(img)
    for _ in range(70):
        x, y = rng.randrange(0, img.width - 40), rng.randrange(0, img.height - 40)
        w, h, level = rng.randrange(20, 140), rng.randrange(20, 110), rng.randrange(0, 256)
        draw.rectangle([x, y, x + w, y + h], fill=(level,) * 3)
    x, y, w, h = ZONE
    door = [MARGIN + x * W, MARGIN + y * H, MARGIN + (x + w) * W - 1, MARGIN + (y + h) * H - 1]
    draw.rectangle(door, fill=LIT if lit else (150, 150, 150))
    return img


CLOSED, OPEN = scene(False), scene(True)


def view(source: Image.Image, px: int = 0) -> Image.Image:
    """The camera's view with the content moved `px` pixels (at 128x72) to the right."""
    x = MARGIN - px * 5
    return source.crop((x, MARGIN, x + W, MARGIN + H))


def jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def set_up(keep_anchor=True):
    box = dict(zip(("x", "y", "width", "height"), ZONE, strict=True))
    table = FridgeTable()
    door_calibration.add_reference(table, ACCOUNT, DEVICE, jpeg(view(OPEN)), box, "open", START)
    door_calibration.add_reference(
        table, ACCOUNT, DEVICE, jpeg(view(CLOSED)), box, "closed", START + 1
    )
    door_calibration.run(table, ACCOUNT, DEVICE, START + 2)
    if not keep_anchor:  # a setup run from before anchors existed
        item = table.get(account_pk(ACCOUNT), door_calibration.setup_sk(DEVICE))
        del item["anchor"]
        table.put(item)


def serve_clip(tmp_path, px: int, open_ms=(2000, 4500), duration_ms=6000):
    frames = [
        (t, view(OPEN if open_ms[0] <= t < open_ms[1] else CLOSED, px))
        for t in range(0, duration_ms - 40 + 1, 250)
    ]
    data = write_images(tmp_path / "served.mp4", frames).read_bytes()
    (tmp_path / "served.mp4").unlink()
    respx.post(CLIP_URL).respond(303, headers={"Location": CLIP_LINK})
    respx.get(CLIP_LINK).respond(200, content=data)


STATE6 = {**STATE20, "window": {**STATE20["window"], "end_ms": START + 6000}}


def run(ring_http, tmp_path, writer=None):
    ring, http = ring_http
    return fetch_stills(
        ring,
        http,
        boto3.client("s3"),
        FridgeTable(),
        BUCKET,
        DEFAULT,
        FakeBlurrer(),
        STATE6,
        sleep=lambda s: None,
        frame_interval_ms=500,
        clip_dir=tmp_path,
        setup_for=lambda a, d: door_calibration.setup_check(FridgeTable(), a, d),
        writer=writer,
    )


def logged(caplog, event: str) -> dict:
    [line] = [r.getMessage() for r in caplog.records if f'"{event}"' in r.getMessage()]
    return json.loads(line)


# Shifted camera still detects the opening
@respx.mock
def test_shifted_camera_still_detects_the_opening(aws, ring_http, tmp_path):
    set_up()
    serve_clip(tmp_path, px=6)
    serve_stills()
    out = run(ring_http, tmp_path)
    assert out["outcome"] == "door_open"
    s = alignment.load_alignment(FridgeTable(), ACCOUNT, DEVICE)
    assert s.dx == pytest.approx(6 / 128, abs=0.001)
    assert s.error < alignment.ALIGN_MAX_ERROR


# Same clip without alignment misses it
@respx.mock
def test_same_clip_without_alignment_misses_it(aws, ring_http, tmp_path):
    set_up(keep_anchor=False)
    serve_clip(tmp_path, px=6)
    serve_stills()
    assert run(ring_http, tmp_path)["outcome"] == "not_door"


@respx.mock
def test_stored_shift_used_before_alignment(aws, ring_http, tmp_path):
    """A shift stored by an earlier event is applied from the first frame on."""
    set_up()
    shifted = alignment.Alignment(True, 6 / 128, 0, 0.01, "first")
    alignment.record(FridgeTable(), ACCOUNT, DEVICE, shifted, START + 3)
    serve_clip(tmp_path, px=6)
    serve_stills()
    assert run(ring_http, tmp_path)["outcome"] == "door_open"


# Alignment error does not drop an opening
@respx.mock
def test_alignment_error_does_not_drop_an_opening(aws, ring_http, tmp_path, caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    set_up()

    def broken(*args):
        raise RuntimeError("table hiccup")

    monkeypatch.setattr(alignment, "load_alignment", broken)
    serve_clip(tmp_path, px=0)
    serve_stills()
    assert run(ring_http, tmp_path)["outcome"] == "door_open"
    assert logged(caplog, "door_alignment_unavailable")["error"] == "RuntimeError"


# Trace records the shift
@respx.mock
def test_trace_records_the_shift(aws, ring_http, tmp_path):
    set_up()
    serve_clip(tmp_path, px=2)
    serve_stills()
    s3 = boto3.client("s3")
    run(ring_http, tmp_path, writer=TraceWriter(s3, FridgeTable(), BUCKET))
    doc = json.loads(s3.get_object(Bucket=BUCKET, Key=f"{PREFIX}debug/door.json")["Body"].read())
    assert doc["alignment"]["ok"] is True
    assert doc["alignment"]["dx"] == pytest.approx(0.016, abs=0.001)
    assert doc["alignment"]["dy"] == 0
    assert 0 <= doc["alignment"]["error"] < alignment.ALIGN_MAX_ERROR
    assert doc["rules"] == "setup"
    # the zone the frames were scored with is the shifted one
    assert doc["rule"]["zones"][0]["box"]["x"] == pytest.approx(0.38 + 2 / 128, abs=0.001)


@respx.mock
def test_trace_without_alignment(aws, ring_http, tmp_path):
    set_up(keep_anchor=False)
    serve_clip(tmp_path, px=0)
    serve_stills()
    s3 = boto3.client("s3")
    run(ring_http, tmp_path, writer=TraceWriter(s3, FridgeTable(), BUCKET))
    doc = json.loads(s3.get_object(Bucket=BUCKET, Key=f"{PREFIX}debug/door.json")["Body"].read())
    assert doc["alignment"] is None
