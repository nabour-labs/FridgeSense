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
        level = max(rng.randrange(0, 256), 24)  # nothing as dark as a privacy mask
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


# Lighting change alone
def test_lighting_change_alone():
    dim = Image.eval(view(), lambda v: round(v * 0.6))
    result = alignment.align_bookends(ANCHOR, dim, dim)
    assert result.ok
    assert (result.dx, result.dy) == (0, 0)


def test_default_limit():
    assert alignment.ALIGN_MIN_MATCH == 0.5


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


# --- Visible map stored with the anchor ---


def masked(img: Image.Image, left: float, right: float) -> Image.Image:
    """`img` painted black in its left `left` and right `right` share of columns, like a
    privacy mask."""
    out = img.copy()
    draw = ImageDraw.Draw(out)
    if left:
        draw.rectangle([0, 0, round(W * left) - 1, H], fill=(0, 0, 0))
    if right:
        draw.rectangle([W - round(W * right), 0, W, H], fill=(0, 0, 0))
    return out


def visible_cols(vis: Image.Image, y: int = 36) -> list[int]:
    return [x for x in range(128) if vis.getpixel((x, y)) == 255]


# Map from the newest closed reference
def test_map_from_masked_reference():
    vis = alignment.visible_map(masked(view(), 0.3125, 0.34375))
    assert vis.size == (128, 72) and vis.mode == "L"
    cols = visible_cols(vis)
    # columns 0-39 and 84-127 are black at 128 wide; grown by 2 px
    assert cols[0] == 40 + 2
    assert cols[-1] == 83 - 2
    assert all(c in cols for c in range(cols[0], cols[-1] + 1))


def test_unmasked_reference_all_visible():
    vis = alignment.visible_map(view())
    assert vis.getextrema() == (255, 255)


# Overlay text in the mask stays masked
def test_overlay_text_in_the_mask_stays_masked():
    img = masked(view(), 0.0, 0.35)
    draw = ImageDraw.Draw(img)
    for line in range(3):  # three lines of white text, ~2 px high at 128x72
        draw.text(
            (W - 400, 30 + line * 50), "Generated-At: 2026-10-18", fill=(255,) * 3, font_size=22
        )
    vis = alignment.visible_map(img)
    for x in range(128 - 40, 128):
        for y in range(2, 20):
            assert vis.getpixel((x, y)) == 0, (x, y)


# Dark but unmasked detail stays visible
def test_dark_but_unmasked_detail_stays_visible():
    img = Image.new("RGB", (W, H), (200, 200, 200))
    ImageDraw.Draw(img).rectangle([600, 300, 639, 339], fill=(0, 0, 0))  # 4x4 at 128x72
    vis = alignment.visible_map(img)
    assert vis.getextrema() == (255, 255)


def test_visible_map_round_trip():
    vis = alignment.visible_map(masked(view(), 0.3, 0.3))
    assert alignment.visible_from_bytes(alignment.visible_to_bytes(vis)).tobytes() == vis.tobytes()


# --- Alignment ignores masked pixels and blocked views ---


def masked_anchor(left: float, right: float, px: int = 0, py: int = 0):
    source = masked(view(px, py), left, right)
    return alignment.edge_map(source), alignment.visible_map(source)


# Wider mask after setup
def test_wider_mask_after_setup():
    anchor, vis = masked_anchor(0.25, 0.25)
    bookend = masked(view(), 0.31, 0.31)
    result = alignment.align_bookends(anchor, bookend, bookend, vis)
    assert result.ok
    assert (result.dx, result.dy) == (0, 0)


# Known shift with a mask
def test_known_shift_with_a_mask():
    anchor, vis = masked_anchor(0.2, 0.2)
    bookend = masked(view(3, 1), 0.2, 0.2)  # content moved, mask fixed on the screen
    result = alignment.align_bookends(anchor, bookend, bookend, vis)
    assert result.ok
    assert result.dx == pytest.approx(3 / 128, abs=0.001)
    assert result.dy == pytest.approx(1 / 72, abs=0.001)


# Person in front of the zones in both bookends
def test_person_in_front_of_the_zones_in_both_bookends():
    person = view()
    ImageDraw.Draw(person).rectangle([int(W * 0.35), 0, int(W * 0.65), H], fill=(60, 50, 40))
    result = alignment.align_bookends(ANCHOR, person, person)
    assert result.ok
    assert (result.dx, result.dy) == (0, 0)
    assert 1 - result.error < 0.9  # the person really did block some blocks


# Rotated camera still fails
def test_rotated_camera_still_fails():
    rotated = view(source=SCENE.rotate(5, resample=Image.Resampling.BICUBIC, fillcolor=(120,) * 3))
    result = alignment.align_bookends(ANCHOR, rotated, rotated)
    assert not result.ok
    assert 1 - result.error < alignment.ALIGN_MIN_MATCH


# Too little left to compare
def test_too_little_left_to_compare():
    anchor, vis = masked_anchor(0.45, 0.45)
    result = alignment.align_bookends(
        anchor, masked(view(), 0.45, 0.45), masked(view(), 0.45, 0.45), vis
    )
    assert not result.ok


def test_used_bookend_visible_map_returned():
    bookend = masked(view(), 0.31, 0.31)
    result = alignment.align_bookends(ANCHOR, bookend, bookend)
    assert result.visible == alignment.visible_to_bytes(alignment.visible_map(bookend))


# Recorded clip after a mask change
def test_recorded_clip_after_a_mask_change():
    """The 2026-10-18 prod case at 128x72 grayscale: setup's newest closed reference, and the
    first and last frames of a clip taken after the owner changed the privacy mask, with the
    owner in front of the fridge in both."""
    from pathlib import Path

    folder = Path(__file__).parent / "fixtures" / "alignment" / "mask_change"
    reference = Image.open(folder / "closed_reference.png")
    first, last = Image.open(folder / "first.png"), Image.open(folder / "last.png")
    result = alignment.align_bookends(
        alignment.edge_map(reference), first, last, alignment.visible_map(reference)
    )
    assert result.ok
    assert (result.dx, result.dy) == (0, 0)


# --- Privacy mask change detected ---

ZONES = [  # (name, box) in setup order
    ("Chiller", (0.40, 0.30, 0.20, 0.30)),
    ("Freezer Drawer 1", (0.40, 0.65, 0.20, 0.10)),
]


def vis_bytes(left: float, right: float) -> bytes:
    return alignment.visible_to_bytes(alignment.visible_map(masked(view(), left, right)))


OLD_MAP = vis_bytes(0.25, 0.25)


def mask_event(new_map: bytes, at=T0, anchor_map=OLD_MAP, zones=ZONES):
    return alignment.record_mask(FridgeTable(), ACCOUNT, DEVICE, new_map, anchor_map, zones, at)


def map_diff(a: bytes, b: bytes) -> float:
    return sum(x != y for x, y in zip(a, b, strict=True)) / len(a)


# Mask change that misses every zone
def test_mask_change_that_misses_every_zone(aws):
    new = vis_bytes(0.31, 0.31)  # still clear of both zones
    assert map_diff(new, OLD_MAP) > 0.03
    assert mask_event(new, at=T0) is None
    assert mask_event(new, at=T0 + 1) == new  # adopt it
    s = state()
    assert s.mask_zones == () and s.mask_changed_at_ms is None and s.mask_streak == 0
    assert not s.moved


# Mask change that covers a zone
def test_mask_change_that_covers_a_zone(aws):
    new = alignment.visible_to_bytes(
        alignment.visible_map(masked(view(), 0.48, 0.25))  # hides the left 40% of Chiller
    )
    assert mask_event(new, at=T0) is None
    assert mask_event(new, at=T0 + 1) is None  # keep the old map until setup runs
    s = state()
    assert s.mask_zones == ("Chiller", "Freezer Drawer 1")  # both start at x = 0.40
    assert s.mask_changed_at_ms == T0 + 1


def test_mask_change_that_covers_one_of_two_zones(aws):
    zones = [("Chiller", (0.40, 0.30, 0.20, 0.30)), ("Side", (0.55, 0.65, 0.15, 0.10))]
    new = vis_bytes(0.48, 0.25)
    mask_event(new, at=T0, zones=zones)
    mask_event(new, at=T0 + 1, zones=zones)
    assert state().mask_zones == ("Chiller",)


# One odd event
def test_one_odd_event(aws):
    mask_event(vis_bytes(0.31, 0.31), at=T0)
    assert state().mask_streak == 1
    assert mask_event(OLD_MAP, at=T0 + 1) is None
    s = state()
    assert s.mask_streak == 0 and s.mask_zones == () and s.mask_changed_at_ms is None


# Small difference ignored
def test_small_difference_ignored(aws):
    new = vis_bytes(0.26, 0.25)
    assert 0 < map_diff(new, OLD_MAP) <= 0.03
    assert mask_event(new, at=T0) is None
    assert mask_event(new, at=T0 + 1) is None
    s = state() or alignment.AlignState()  # nothing to store
    assert s.mask_streak == 0 and s.mask_zones == ()


def test_no_anchor_map_counts_everything_visible(aws):
    assert mask_event(OLD_MAP, at=T0, anchor_map=None) is None
    assert state().mask_streak == 1


# Setup run clears the mask change
def test_setup_run_clears_the_mask_change(aws):
    new = vis_bytes(0.48, 0.25)
    mask_event(new, at=T0)
    mask_event(new, at=T0 + 1)
    alignment.reset(FridgeTable(), ACCOUNT, DEVICE)
    s = state()
    assert s.mask_zones == () and s.mask_changed_at_ms is None and s.mask_streak == 0


# Mask change while the camera also moved
def test_mask_change_while_the_camera_also_moved(aws):
    new = vis_bytes(0.48, 0.25)
    for k in range(3):
        event(frame=ROTATED, at=T0 + k)
        mask_event(new, at=T0 + k)
    s = state()
    assert s.moved
    assert s.mask_zones == ("Chiller", "Freezer Drawer 1")
