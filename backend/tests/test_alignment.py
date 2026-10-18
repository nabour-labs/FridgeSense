"""door-self-calibration: aligning an event's bookends with the closed anchor, and its state."""

import random
import time

import pytest
from PIL import Image, ImageDraw

from fridgesense import alignment
from fridgesense.table import FridgeTable

W, H = 1280, 720  # 10 px here is 1 px at the 128x72 alignment size
MARGIN = 200


def scene() -> Image.Image:
    """Seeded random grey rectangles, larger than the view so shifts show real content."""
    rng = random.Random(7)
    img = Image.new("RGB", (W + 2 * MARGIN, H + 2 * MARGIN), (120, 120, 120))
    draw = ImageDraw.Draw(img)
    for _ in range(90):
        x, y = rng.randrange(0, img.width - 60), rng.randrange(0, img.height - 60)
        w, h = rng.randrange(40, 260), rng.randrange(40, 200)
        level = rng.randrange(0, 256)
        draw.rectangle([x, y, x + w, y + h], fill=(level, level, level))
    return img


SCENE = scene()


def view(px: int = 0, py: int = 0, source: Image.Image = SCENE) -> Image.Image:
    """The camera's view with the content moved `px`, `py` pixels (at 128x72) right and down."""
    x, y = MARGIN - px * 10, MARGIN - py * 10
    return source.crop((x, y, x + W, y + H))


ANCHOR = alignment.edge_map(view())


# Known shift found
def test_known_shift_found():
    result = alignment.align_bookends(ANCHOR, view(5, 2), view(5, 2))
    assert result.ok
    assert result.dx == pytest.approx(5 / 128, abs=0.001)
    assert result.dy == pytest.approx(2 / 72, abs=0.001)
    assert result.error < 0.02


def test_shift_found_left_and_up():
    shift = alignment.best_shift(ANCHOR, alignment.edge_map(view(-7, -3)))
    assert (shift.px, shift.py) == (-7, -3)


# Better bookend used
def test_better_bookend_used():
    first = view(-3, 0)
    ImageDraw.Draw(first).rectangle([0, 0, W // 2, H], fill=(60, 50, 40))  # a person
    result = alignment.align_bookends(ANCHOR, first, view(-3, 0))
    assert result.ok
    assert result.used == "last"
    assert result.dx == pytest.approx(-3 / 128, abs=0.001)
    assert result.dy == 0


# Alignment fails
def test_alignment_fails_when_rotated():
    rotated = SCENE.rotate(15, resample=Image.Resampling.BICUBIC, fillcolor=(120, 120, 120))
    result = alignment.align_bookends(ANCHOR, view(source=rotated), view(source=rotated))
    assert not result.ok
    assert result.error > alignment.ALIGN_MAX_ERROR


# Lighting change alone
def test_lighting_change_alone():
    dim = Image.eval(view(), lambda v: round(v * 0.6))
    result = alignment.align_bookends(ANCHOR, dim, dim)
    assert result.ok
    assert (result.dx, result.dy) == (0, 0)


def test_default_limit():
    assert alignment.ALIGN_MAX_ERROR == 0.05


def test_edge_map_size_and_round_trip():
    edges = alignment.edge_map(view())
    assert edges.size == (128, 72)
    assert edges.mode == "L"
    restored = alignment.edges_from_bytes(alignment.edges_to_bytes(edges))
    assert restored.tobytes() == edges.tobytes()


def test_edge_map_takes_jpeg_bytes():
    import io

    buf = io.BytesIO()
    view().save(buf, format="JPEG", quality=95)
    assert alignment.edge_map(buf.getvalue()).size == (128, 72)


def test_best_shift_is_fast():
    edges = alignment.edge_map(view(4, 1))
    started = time.perf_counter()
    alignment.best_shift(ANCHOR, edges)
    assert time.perf_counter() - started < 0.3


# Shifted zones
def test_shifted_zones():
    box = alignment.shift_box((0.38, 0.32, 0.21, 0.30), 0.03, -0.02)
    assert box == pytest.approx((0.41, 0.30, 0.21, 0.30))


# Clamped at the edge
def test_clamped_at_the_edge():
    assert alignment.shift_box((0.85, 0.5, 0.12, 0.2), 0.05, 0) == pytest.approx(
        (0.88, 0.5, 0.12, 0.2)
    )
    assert alignment.shift_box((0.01, 0.02, 0.2, 0.2), -0.05, -0.05) == pytest.approx(
        (0.0, 0.0, 0.2, 0.2)
    )


# --- Alignment state stored per device, camera moved detection ---

ACCOUNT = "ava1.ring.account.A1"
DEVICE = "ava1.ring.device.D1"
T0 = 1792092000000
ANCHOR_BYTES = alignment.edges_to_bytes(ANCHOR)
ROTATED = view(source=SCENE.rotate(15, resample=Image.Resampling.BICUBIC, fillcolor=(120,) * 3))


def event(px=0, py=0, at=T0, frame=None, anchor=ANCHOR_BYTES):
    still = frame if frame is not None else view(px, py)
    return alignment.align_event(FridgeTable(), ACCOUNT, DEVICE, anchor, still, still, at)


def state():
    return alignment.load_alignment(FridgeTable(), ACCOUNT, DEVICE)


def test_first_success_stored(aws):
    event(2, 0, at=T0 + 5)
    s = state()
    assert (s.dx, s.dy, s.failures, s.moved) == (pytest.approx(2 / 128), 0, 0, False)
    assert s.error < 0.02
    assert s.checked_at_ms == T0 + 5


# Success resets failures
def test_success_resets_failures(aws):
    event(frame=ROTATED, at=T0)
    event(frame=ROTATED, at=T0 + 1)
    assert state().failures == 2
    result = event(1, 0, at=T0 + 2)
    assert result.ok
    s = state()
    assert (s.dx, s.dy, s.failures) == (pytest.approx(1 / 128), 0, 0)


# Failure counts up
def test_failure_counts_up(aws):
    event(2, 1, at=T0)
    event(frame=ROTATED, at=T0 + 1)
    s = state()
    assert s.failures == 1
    assert (s.dx, s.dy) == (pytest.approx(2 / 128), pytest.approx(1 / 72))
    assert s.checked_at_ms == T0 + 1


# Three failed alignments
def test_three_failed_alignments(aws):
    for k in range(3):
        event(frame=ROTATED, at=T0 + k)
    s = state()
    assert s.moved
    assert s.moved_at_ms == T0 + 2
    assert s.last_moved_at_ms == T0 + 2


def test_two_failures_not_moved(aws):
    event(frame=ROTATED, at=T0)
    event(frame=ROTATED, at=T0 + 1)
    assert not state().moved


# Large shift
def test_large_shift(aws):
    result = event(6, 0, at=T0 + 9)  # 6/128 = 0.047
    assert result.ok
    s = state()
    assert s.moved
    assert s.moved_at_ms == T0 + 9
    assert s.dx == pytest.approx(6 / 128)


def test_shift_below_limit_not_moved(aws):
    event(5, 2, at=T0)  # 0.039 across, 0.028 down
    assert not state().moved


# Stays moved after a good event
def test_stays_moved_after_a_good_event(aws):
    event(6, 0, at=T0)
    event(0, 0, at=T0 + 1)
    s = state()
    assert s.moved
    assert s.moved_at_ms == T0
    assert (s.dx, s.dy) == (0, 0)


# No anchor
def test_no_anchor(aws):
    event(2, 0, at=T0)
    before = state()
    assert event(5, 0, at=T0 + 1, anchor=None) is None
    assert state() == before


def test_no_anchor_nothing_stored(aws):
    assert event(5, 0, anchor=None) is None
    assert state() is None


def test_reset_keeps_last_moved_at(aws):
    event(6, 0, at=T0)
    alignment.reset(FridgeTable(), ACCOUNT, DEVICE)
    s = state()
    assert (s.dx, s.dy, s.failures, s.moved, s.moved_at_ms) == (0, 0, 0, False, None)
    assert s.error is None and s.checked_at_ms is None
    assert s.last_moved_at_ms == T0


def test_alignment_kept_per_device(aws):
    event(2, 0)
    assert alignment.load_alignment(FridgeTable(), ACCOUNT, "ava1.ring.device.D2") is None


# --- Suspect streak per device ---


def streak() -> int:
    s = alignment.load_alignment(FridgeTable(), ACCOUNT, DEVICE)
    return 0 if s is None else s.suspect_streak


# Three suspect events in a row
def test_three_suspect_events_in_a_row(aws):
    for _ in range(3):
        alignment.record_suspect(FridgeTable(), ACCOUNT, DEVICE, True)
    assert streak() == 3


# Normal event resets the streak
def test_normal_event_resets_the_streak(aws):
    for _ in range(2):
        alignment.record_suspect(FridgeTable(), ACCOUNT, DEVICE, True)
    alignment.record_suspect(FridgeTable(), ACCOUNT, DEVICE, False)
    assert streak() == 0


def test_streak_kept_by_an_alignment(aws):
    alignment.record_suspect(FridgeTable(), ACCOUNT, DEVICE, True)
    ok = alignment.Alignment(True, 0.01, 0, 0.01, "first")
    alignment.record(FridgeTable(), ACCOUNT, DEVICE, ok, T0)
    assert streak() == 1


# Setup run resets the streak
def test_setup_run_resets_the_streak(aws):
    for _ in range(5):
        alignment.record_suspect(FridgeTable(), ACCOUNT, DEVICE, True)
    alignment.reset(FridgeTable(), ACCOUNT, DEVICE)
    assert streak() == 0
