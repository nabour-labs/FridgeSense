"""door-event-detection: blocked suspect clips leave the suspect streak unchanged."""

import random
from pathlib import Path

from PIL import Image, ImageDraw

from fridgesense import alignment
from fridgesense.door_events import DoorCheck, ZoneRule, ZoneValue, is_blocked

W, H = 1280, 720  # 10 px here is 1 px at the 128x72 alignment size
MARGIN = 200
ZONE_A = (0.40, 0.30, 0.20, 0.30)
ZONE_B = (0.10, 0.60, 0.15, 0.20)
CHECK = DoorCheck(
    rules=(ZoneRule(ZONE_A, "change", "above", 0.05), ZoneRule(ZONE_B, "change", "above", 0.05)),
    source="setup",
)


def scene() -> Image.Image:
    rng = random.Random(11)
    img = Image.new("RGB", (W + 2 * MARGIN, H + 2 * MARGIN), (120, 120, 120))
    draw = ImageDraw.Draw(img)
    for _ in range(90):
        x, y = rng.randrange(0, img.width - 60), rng.randrange(0, img.height - 60)
        w, h = rng.randrange(40, 260), rng.randrange(40, 200)
        level = max(rng.randrange(0, 256), 24)
        draw.rectangle([x, y, x + w, y + h], fill=(level,) * 3)
    return img


SCENE = scene()


def view(px: int = 0) -> Image.Image:
    x = MARGIN - px * 10
    return SCENE.crop((x, MARGIN, x + W, MARGIN + H))


ANCHOR = alignment.edges_to_bytes(alignment.edge_map(view()))


def person(img: Image.Image, box=ZONE_A) -> Image.Image:
    """`img` with a flat rectangle over `box` grown 5% each way, like someone standing there."""
    out = img.copy()
    x, y, w, h = box
    ImageDraw.Draw(out).rectangle(
        [(x - 0.05) * W, (y - 0.05) * H, (x + w + 0.05) * W, (y + h + 0.05) * H],
        fill=(150, 40, 60),
    )
    return out


def reads(*opens: bool) -> list[ZoneValue]:
    """Zone verdicts at a bookend, zone 1 first."""
    return [
        ZoneValue(n, 1.0 if o else 0.0, 0.05, o, 0.1 if o else -0.1) for n, o in enumerate(opens, 1)
    ]


OPEN_A = reads(True, False)


# Person in front of the zones at both bookends
def test_person_in_front_of_the_zones_at_both_bookends():
    blocked = person(view())
    assert is_blocked(ANCHOR, CHECK, 0, 0, [(blocked, OPEN_A), (blocked, OPEN_A)])


# Wrong rules on a clear view
def test_wrong_rules_on_a_clear_view():
    assert not is_blocked(ANCHOR, CHECK, 0, 0, [(view(), OPEN_A), (view(), OPEN_A)])


# One bookend clear is enough to count
def test_one_bookend_clear_is_enough_to_count():
    assert not is_blocked(ANCHOR, CHECK, 0, 0, [(person(view()), OPEN_A), (view(), OPEN_A)])


# Two zones, only the open one is checked
def test_two_zones_only_the_open_one_is_checked():
    blocked = person(view())  # zone B stays clear and looks closed, but reads closed
    assert is_blocked(ANCHOR, CHECK, 0, 0, [(blocked, OPEN_A), (blocked, OPEN_A)])


def test_a_closed_bookend_is_not_evidence():
    blocked = person(view())
    closed = reads(False, False)
    assert is_blocked(ANCHOR, CHECK, 0, 0, [(blocked, OPEN_A), (view(), closed)])


# Shift applied to the zone box
def test_shift_applied_to_the_zone_box():
    moved = view(4)
    assert not is_blocked(ANCHOR, CHECK, 4 / 128, 0, [(moved, OPEN_A), (moved, OPEN_A)])


def test_shift_ignored_would_look_blocked():
    """Without the shift the moved view would not match: the shift really is applied."""
    moved = view(4)
    assert is_blocked(ANCHOR, CHECK, 0, 0, [(moved, OPEN_A), (moved, OPEN_A)])


# Suspect by share alone
def test_suspect_by_share_alone():
    closed = reads(False, False)
    assert not is_blocked(ANCHOR, CHECK, 0, 0, [(person(view()), closed), (view(), closed)])


# No anchor stored
def test_no_anchor_stored():
    blocked = person(view())
    assert not is_blocked(None, CHECK, 0, 0, [(blocked, OPEN_A), (blocked, OPEN_A)])


# Recorded clip with the owner in front
def test_recorded_clip_with_the_owner_in_front():
    folder = Path(__file__).parent / "fixtures" / "alignment" / "mask_change"
    reference = Image.open(folder / "closed_reference.png")
    anchor = alignment.edges_to_bytes(alignment.edge_map(reference))
    prod = DoorCheck(  # the prod setup's three zones (2026-10-17)
        rules=(
            ZoneRule((0.376, 0.362, 0.206, 0.3), "change", "above", 0.0454),
            ZoneRule((0.392, 0.658, 0.18, 0.075), "change", "above", 0.1149),
            ZoneRule((0.38, 0.714, 0.193, 0.156), "change", "above", 0.0536),
        ),
        source="setup",
    )
    all_open = reads(True, True, True)
    first, last = Image.open(folder / "first.png"), Image.open(folder / "last.png")
    assert is_blocked(anchor, prod, 0, 0, [(first, all_open), (last, all_open)])
    # ...while the closed reference itself, read open, would count against the rules
    assert not is_blocked(anchor, prod, 0, 0, [(reference, all_open), (reference, all_open)])
