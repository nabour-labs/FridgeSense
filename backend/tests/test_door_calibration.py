"""door-calibration: door references, the setup run and its storage."""

import pytest

from fridgesense import alignment
from fridgesense import door_calibration as dc
from fridgesense.analysis_config import Invalid
from fridgesense.table import FridgeTable
from tests.conftest import color_jpeg

ACCOUNT = "ava1.ring.account.A1"
D1, D2 = "ava1.ring.device.D1", "ava1.ring.device.D2"
T0 = 1792092000000
GREY = (128, 128, 128)
BLUE = (40, 90, 200)
LEFT = {"x": 0, "y": 0, "width": 0.5, "height": 1}
WHOLE = {"x": 0, "y": 0, "width": 1, "height": 1}


def add(image, zone_id, status, device=D1, at=T0):
    return dc.add_reference(FridgeTable(), ACCOUNT, device, image, zone_id, status, now_ms=at)


def run(device=D1, at=T0 + 60_000):
    return dc.run(FridgeTable(), ACCOUNT, device, now_ms=at)


def halves(left: int, right: int) -> bytes:
    return color_jpeg((left,) * 3, [((0.5, 0.0, 0.5, 1.0), (right,) * 3)], size=(200, 100))


def plain(level: int) -> bytes:
    return color_jpeg((level,) * 3, size=(200, 100))


def zone(box=LEFT, name="Doors", device=D1, at=T0):
    return dc.add_zone(FridgeTable(), ACCOUNT, device, name, box, now_ms=at)


def zones(device=D1):
    return dc.list_zones(FridgeTable(), ACCOUNT, device)


# Zone added
def test_zone_added(aws):
    zone(LEFT, "Doors")
    added = zone({"x": 0.38, "y": 0.65, "width": 0.2, "height": 0.25}, "Freezer drawer", at=T0 + 1)
    assert added.sk.startswith(dc.zone_prefix(D1))
    assert [(z.name, z.box) for z in zones()] == [
        ("Doors", (0.0, 0.0, 0.5, 1.0)),
        ("Freezer drawer", (0.38, 0.65, 0.2, 0.25)),
    ]
    assert zones(D2) == []


def test_zone_name_trimmed(aws):
    assert zone(name="  Doors ").name == "Doors"


# Invalid zone rejected
@pytest.mark.parametrize("name", ["", "   ", "x" * 31, None, 5])
def test_invalid_zone_name_rejected(name):
    with pytest.raises(Invalid, match="name must be 1 to 30 characters"):
        dc.validate_name(name)


def test_invalid_zone_box_rejected(aws):
    with pytest.raises(Invalid, match="box must be inside the image"):
        zone({"x": 0.9, "y": 0, "width": 0.2, "height": 1})
    assert zones() == []


# Zone limit
def test_zone_limit(aws):
    for n in range(6):
        zone(at=T0 + n)
    with pytest.raises(dc.TooManyZones):
        zone(at=T0 + 6)
    zone(device=D2)  # per device


# Zone redrawn
def test_zone_redrawn(aws):
    z = zone()
    add(plain(200), z.sk, "open", at=T0 + 1)
    add(plain(100), z.sk, "closed", at=T0 + 2)
    run(at=T0 + 10)
    box = {"x": 0.36, "y": 0.3, "width": 0.25, "height": 0.4}
    assert dc.update_zone(FridgeTable(), ACCOUNT, D1, z.sk, box=box, now_ms=T0 + 20) is True
    [after] = zones()
    assert (after.name, after.box) == ("Doors", (0.36, 0.3, 0.25, 0.4))
    assert {r.box for r in dc.list_references(FridgeTable(), ACCOUNT, D1)} == {after.box}
    assert dc.load_setup(FridgeTable(), ACCOUNT, D1).stale is True


def test_zone_renamed(aws):
    z = zone()
    dc.update_zone(FridgeTable(), ACCOUNT, D1, z.sk, name="Fridge doors", now_ms=T0 + 1)
    assert [(x.name, x.box) for x in zones()] == [("Fridge doors", (0.0, 0.0, 0.5, 1.0))]


# Zone deleted with its references
def test_zone_deleted_with_its_references(aws):
    z, other = zone(), zone(WHOLE, "Drawer", at=T0 + 1)
    add(plain(200), z.sk, "open", at=T0 + 2)
    add(plain(100), z.sk, "closed", at=T0 + 3)
    kept = add(plain(100), other.sk, "closed", at=T0 + 4)
    assert dc.delete_zone(FridgeTable(), ACCOUNT, D1, z.sk, now_ms=T0 + 5) is True
    assert [x.sk for x in zones()] == [other.sk]
    assert [r.sk for r in dc.list_references(FridgeTable(), ACCOUNT, D1)] == [kept.sk]
    assert dc.delete_zone(FridgeTable(), ACCOUNT, D1, z.sk, now_ms=T0 + 6) is False
    assert dc.update_zone(FridgeTable(), ACCOUNT, D1, z.sk, name="x", now_ms=T0 + 6) is False
    assert dc.delete_zone(FridgeTable(), ACCOUNT, D1, kept.sk, now_ms=T0 + 6) is False


# Reference added
def test_reference_added(aws):
    image = color_jpeg(size=(960, 540))
    z = zone({"x": 0.38, "y": 0.32, "width": 0.21, "height": 0.30})
    add(image, z.sk, "open")
    [ref] = dc.list_references(FridgeTable(), ACCOUNT, D1)
    assert ref.sk
    assert ref.zone_id == z.sk
    assert ref.box == (0.38, 0.32, 0.21, 0.30)
    assert ref.status == "open"
    assert ref.image == image
    assert ref.created_at == "2026-10-15T19:20:00.000Z"


def test_references_listed_oldest_first(aws):
    z = zone()
    add(plain(10), z.sk, "open", at=T0 + 2)
    add(plain(20), z.sk, "closed", at=T0 + 1)
    assert [r.status for r in dc.list_references(FridgeTable(), ACCOUNT, D1)] == ["closed", "open"]


# Invalid reference rejected
@pytest.mark.parametrize(
    "box",
    [
        {"x": 0.9, "y": 0, "width": 0.2, "height": 1},
        {"x": 0, "y": 0, "width": 0.01, "height": 1},
        {"x": 0, "y": 0, "width": 0.5},
        {"x": "0.1", "y": 0, "width": 0.5, "height": 0.5},
        {"x": True, "y": 0, "width": 0.5, "height": 0.5},
        "0,0,1,1",
        None,
    ],
)
def test_invalid_box_rejected(box):
    with pytest.raises(Invalid, match="box must be inside the image and at least 2% wide and tall"):
        dc.validate_box(box)


@pytest.mark.parametrize("status", ["ajar", "", None, "OPEN"])
def test_invalid_status_rejected(status):
    with pytest.raises(Invalid, match="status must be open or closed"):
        dc.validate_status(status)


@pytest.mark.parametrize("image", ["iVBORw0KGgo=", "not base64!", None, "/9j/" + "A" * 400_004])
def test_invalid_image_rejected(image):
    with pytest.raises(Invalid, match="image must be a JPEG of at most 300 KB"):
        dc.decode_image(image)


def test_image_decoded():
    import base64

    data = color_jpeg()
    assert dc.decode_image(base64.b64encode(data).decode()) == data


# Unknown zone
@pytest.mark.parametrize("zone_id", [None, "", "DOORZONE#ava1.ring.device.D1#nope", 5])
def test_unknown_zone(aws, zone_id):
    zone()
    with pytest.raises(Invalid, match="pick a door zone"):
        add(plain(10), zone_id, "open")
    assert dc.list_references(FridgeTable(), ACCOUNT, D1) == []


# Zones kept per device
def test_zone_of_another_device(aws):
    z = zone(device=D1)
    with pytest.raises(Invalid, match="pick a door zone"):
        add(plain(10), z.sk, "open", device=D2)


# Reference limit
def test_reference_limit(aws):
    z = zone()
    old_reference(at=T0 - 1)  # old references do not count
    for n in range(24):
        add(plain(10), z.sk, "open", at=T0 + n)
    with pytest.raises(dc.TooMany):
        add(plain(10), z.sk, "open", at=T0 + 24)
    add(plain(10), zone(device=D2).sk, "open", device=D2)  # per device


# Reference deleted
def test_reference_deleted(aws):
    ref = add(plain(10), zone().sk, "open")
    assert dc.delete_reference(FridgeTable(), ACCOUNT, D1, ref.sk) is True
    assert dc.list_references(FridgeTable(), ACCOUNT, D1) == []
    assert dc.delete_reference(FridgeTable(), ACCOUNT, D1, ref.sk) is False
    assert dc.delete_reference(FridgeTable(), ACCOUNT, D1, "ITEM#milk") is False


def old_reference(image=None, status="open", at=T0 - 1):
    """A reference stored before zones existed: a box and no zone."""
    FridgeTable().put(
        {
            "pk": f"ACCOUNT#{ACCOUNT}",
            "sk": f"{dc.ref_prefix(D1)}{at:013d}-abcdef",
            "image": image or plain(200),
            "box": {"x": 0, "y": 0, "width": 0.5, "height": 1},
            "status": status,
            "created_at": "2026-10-15T19:19:59.999Z",
        }
    )


# Old references without a zone
def test_old_references_without_a_zone(aws):
    old_reference()
    assert dc.list_references(FridgeTable(), ACCOUNT, D1) == []


def test_references_of_a_missing_zone_skipped(aws):
    z = zone()
    add(plain(10), z.sk, "open")
    FridgeTable().delete(f"ACCOUNT#{ACCOUNT}", z.sk)  # a zone delete that stopped partway
    assert dc.list_references(FridgeTable(), ACCOUNT, D1) == []


def lit() -> bytes:
    return color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), BLUE)], size=(200, 100))


# Setup marked stale
def test_setup_marked_stale(aws):
    z = zone()
    add(lit(), z.sk, "open")
    add(plain(128), z.sk, "closed", at=T0 + 1)
    run(at=T0 + 10)
    assert dc.load_setup(FridgeTable(), ACCOUNT, D1).stale is False
    new = add(plain(128), z.sk, "closed", at=T0 + 20)
    setup = dc.load_setup(FridgeTable(), ACCOUNT, D1)
    assert setup.stale is True
    scores = dc.reference_scores(dc.list_references(FridgeTable(), ACCOUNT, D1), setup)
    assert scores[new.sk] == pytest.approx(0.0, abs=0.005)
    dc.delete_reference(FridgeTable(), ACCOUNT, D1, new.sk)  # deletes also mark it stale
    run(at=T0 + 30)
    dc.delete_reference(
        FridgeTable(), ACCOUNT, D1, dc.list_references(FridgeTable(), ACCOUNT, D1)[0].sk
    )
    assert dc.load_setup(FridgeTable(), ACCOUNT, D1).stale is True


def test_zone_changes_mark_setup_stale(aws):
    z = zone()
    add(lit(), z.sk, "open")
    add(plain(128), z.sk, "closed", at=T0 + 1)
    run(at=T0 + 10)
    zone(WHOLE, "Drawer", at=T0 + 20)
    assert dc.load_setup(FridgeTable(), ACCOUNT, D1).stale is True
    with pytest.raises(dc.SetupFailed):  # Drawer has no references yet
        run(at=T0 + 30)
    assert dc.load_setup(FridgeTable(), ACCOUNT, D1).stale is True


# Reference of a zone added after setup
def test_reference_of_a_zone_added_after_setup(aws):
    z = zone()
    add(lit(), z.sk, "open")
    add(plain(128), z.sk, "closed", at=T0 + 1)
    run(at=T0 + 10)
    later = add(plain(128), zone(WHOLE, "Drawer", at=T0 + 20).sk, "closed", at=T0 + 21)
    setup = dc.load_setup(FridgeTable(), ACCOUNT, D1)
    assert (
        dc.reference_scores(dc.list_references(FridgeTable(), ACCOUNT, D1), setup)[later.sk] is None
    )


def test_setup_from_before_zones_scores_null(aws):
    z = zone()
    ref = add(lit(), z.sk, "open")
    add(plain(128), z.sk, "closed", at=T0 + 1)
    run(at=T0 + 10)
    item = FridgeTable().get(f"ACCOUNT#{ACCOUNT}", dc.setup_sk(D1))
    for entry in item["zones"]:
        del entry["zone_id"], entry["name"]
    FridgeTable().put(item)
    setup = dc.load_setup(FridgeTable(), ACCOUNT, D1)
    assert (
        dc.reference_scores(dc.list_references(FridgeTable(), ACCOUNT, D1), setup)[ref.sk] is None
    )


def test_no_setup_yet(aws):
    assert dc.load_setup(FridgeTable(), ACCOUNT, D1) is None


# Setup from one open and one closed reference
def test_setup_from_one_open_and_one_closed_reference(aws):
    z = zone(LEFT, "Doors")
    opened = add(lit(), z.sk, "open")
    shut = add(plain(128), z.sk, "closed", at=T0 + 1)
    setup = run()
    [only] = setup.zones
    assert (only.zone_id, only.name) == (z.sk, "Doors")
    assert only.box == (0.0, 0.0, 0.5, 1.0)
    assert only.feature == "blue"
    assert only.direction == "above"
    assert only.threshold == pytest.approx(0.05, abs=0.005)
    assert only.margin == pytest.approx(0.1, abs=0.005)
    assert setup.stale is False
    assert setup.ran_at == "2026-10-15T19:21:00.000Z"
    scores = dc.reference_scores(dc.list_references(FridgeTable(), ACCOUNT, D1), setup)
    assert scores[opened.sk] == pytest.approx(0.1, abs=0.005)
    assert scores[shut.sk] == pytest.approx(0.0, abs=0.005)
    assert dc.load_setup(FridgeTable(), ACCOUNT, D1) == setup


# Brightness chosen when there is no color
def test_brightness_chosen_when_there_is_no_color(aws):
    z = zone(WHOLE)
    add(plain(100), z.sk, "closed")
    add(halves(40, 160), z.sk, "closed", at=T0 + 1)
    add(plain(200), z.sk, "open", at=T0 + 2)
    [only] = run().zones
    assert only.feature == "brightness"
    assert only.direction == "above"
    assert only.margin == pytest.approx(0.39, abs=0.02)
    assert only.threshold == pytest.approx(0.59, abs=0.02)


# Change chosen when brightness is the same
def test_change_chosen_when_brightness_is_the_same(aws):
    z = zone(WHOLE)
    add(plain(128), z.sk, "closed")
    add(halves(40, 216), z.sk, "open", at=T0 + 1)
    [only] = run().zones
    assert only.feature == "change"
    assert only.direction == "above"
    assert only.margin == pytest.approx(0.35, abs=0.02)
    assert len(only.baseline) == 32 * 32 * 3


# Darker when open
def test_darker_when_open(aws):
    z = zone(WHOLE)
    add(plain(220), z.sk, "closed")
    add(halves(180, 240), z.sk, "closed", at=T0 + 1)
    add(plain(90), z.sk, "open", at=T0 + 2)
    [only] = run().zones
    assert only.feature == "brightness"
    assert only.direction == "below"
    assert only.margin == pytest.approx(0.47, abs=0.02)
    assert only.threshold == pytest.approx(0.59, abs=0.02)


def separating_pair(z, at):
    still = color_jpeg(GREY, [((0.0, 0.0, 1.0, 1.0), BLUE)], size=(200, 100))
    add(still, z.sk, "open", at=at)
    add(plain(128), z.sk, "closed", at=at + 1)


# One setup zone per defined zone
def test_one_setup_zone_per_defined_zone(aws):
    doors = zone({"x": 0.35, "y": 0.32, "width": 0.24, "height": 0.38}, "Doors")
    drawer = zone({"x": 0.37, "y": 0.64, "width": 0.22, "height": 0.28}, "Drawer", at=T0 + 1)
    separating_pair(drawer, T0 + 2)  # references added in the other order
    separating_pair(doors, T0 + 4)
    got = run().zones
    assert [(z.name, z.zone_id, z.box) for z in got] == [
        ("Doors", doors.sk, (0.35, 0.32, 0.24, 0.38)),
        ("Drawer", drawer.sk, (0.37, 0.64, 0.22, 0.28)),
    ]


# Overlapping boxes become one zone (no longer: zones are never merged)
def test_overlapping_zones_are_never_merged(aws):
    a = zone({"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.4}, "A")
    b = zone({"x": 0.12, "y": 0.1, "width": 0.3, "height": 0.4}, "B", at=T0 + 1)
    separating_pair(a, T0 + 2)
    separating_pair(b, T0 + 4)
    assert [z.box for z in run().zones] == [(0.1, 0.1, 0.3, 0.4), (0.12, 0.1, 0.3, 0.4)]


# References in one zone are not regrouped
def test_references_in_one_zone_are_not_regrouped(aws):
    # The bug report: one drawer's open and closed shots looked nothing alike.
    drawer = zone({"x": 0.37, "y": 0.64, "width": 0.22, "height": 0.28}, "Drawer")
    open_drawer = color_jpeg(GREY, [((0.37, 0.64, 0.22, 0.1), BLUE)], size=(200, 100))
    add(open_drawer, drawer.sk, "open")
    add(plain(128), drawer.sk, "closed", at=T0 + 1)
    [only] = run().zones
    assert only.name == "Drawer"


def assert_fails(message: str):
    before = dc.load_setup(FridgeTable(), ACCOUNT, D1)
    with pytest.raises(dc.SetupFailed, match=message) as failed:
        run(at=T0 + 999_000)
    assert dc.load_setup(FridgeTable(), ACCOUNT, D1) == before
    return failed.value


# No zones
def test_no_zones(aws):
    old_reference()
    failed = assert_fails("add a door zone first")
    assert failed.scores == {}


# Missing a status
@pytest.mark.parametrize("status", ["open", "closed"])
def test_missing_a_status_all_the_same(aws, status):
    z = zone(LEFT, "Freezer drawer")
    add(plain(100), z.sk, status)
    add(plain(120), z.sk, status, at=T0 + 1)
    failed = assert_fails("Freezer drawer needs an open and a closed reference")
    assert len(failed.scores) == 2


def test_missing_a_status_names_the_zone(aws):
    doors = zone(LEFT, "Doors")
    add(plain(100), doors.sk, "closed")
    add(plain(200), doors.sk, "open", at=T0 + 1)
    drawer = zone({"x": 0.6, "y": 0, "width": 0.4, "height": 1}, "Freezer drawer", at=T0 + 2)
    assert_fails("Freezer drawer needs an open and a closed reference")
    add(plain(100), drawer.sk, "closed", at=T0 + 3)
    assert_fails("Freezer drawer needs an open and a closed reference")


# Open and closed overlap
def test_open_and_closed_overlap(aws):
    z = zone(LEFT, "Doors")
    # 0.5% of the zone: a 10x5 px block in the 100x100 left half
    add(color_jpeg(GREY, [((0.1, 0.4, 0.05, 0.05), BLUE)], size=(200, 100)), z.sk, "open")
    add(plain(128), z.sk, "closed", at=T0 + 1)
    add(plain(128), z.sk, "closed", at=T0 + 2)
    failed = assert_fails("Doors: open and closed references overlap")
    refs = dc.list_references(FridgeTable(), ACCOUNT, D1)
    assert failed.scores[refs[0].sk] == pytest.approx(0.005, abs=0.003)
    assert failed.scores[refs[1].sk] == pytest.approx(0.0, abs=0.003)


# Old references ignored
def test_old_references_ignored(aws):
    old_reference(plain(128), "open")  # would make the zone overlap if it were used
    z = zone(LEFT, "Doors")
    add(lit(), z.sk, "open")
    add(plain(128), z.sk, "closed", at=T0 + 1)
    [only] = run().zones
    assert only.margin == pytest.approx(0.1, abs=0.005)


def test_failure_keeps_the_previous_setup(aws):
    z = zone()
    add(lit(), z.sk, "open")
    add(plain(128), z.sk, "closed", at=T0 + 1)
    first = run()
    other = zone({"x": 0.6, "y": 0, "width": 0.4, "height": 1}, "Drawer", at=T0 + 2)
    add(plain(128), other.sk, "closed", at=T0 + 3)
    assert_fails("Drawer needs an open and a closed reference")
    assert dc.load_setup(FridgeTable(), ACCOUNT, D1).zones == first.zones


# Too many zones
def test_too_many_zones(aws):
    for n in range(7):  # written directly: the API stops at 6
        FridgeTable().put(
            {
                "pk": f"ACCOUNT#{ACCOUNT}",
                "sk": f"{dc.zone_prefix(D1)}{T0 + n:013d}-00000{n}",
                "name": f"Z{n}",
                "box": {"x": n * 0.14, "y": 0, "width": 0.1, "height": 0.1},
                "created_at": "2026-10-15T19:20:00.000Z",
            }
        )
    assert_fails("at most 6 door zones")


# Blue preferred over color on a tie
def test_blue_preferred_over_color_on_a_tie(aws):
    z = zone()
    add(lit(), z.sk, "open")
    add(plain(128), z.sk, "closed", at=T0 + 1)
    [only] = run().zones
    assert only.feature == "blue"
    assert only.margin == pytest.approx(0.1, abs=0.005)


# Color chosen when the open reference is not blue
def test_color_chosen_when_the_open_reference_is_not_blue(aws):
    z = zone()
    add(color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), (200, 60, 40))], size=(200, 100)), z.sk, "open")
    add(plain(128), z.sk, "closed", at=T0 + 1)
    [only] = run().zones
    assert only.feature == "color"
    assert only.margin == pytest.approx(0.1, abs=0.005)


# Setup kept per device / setup turns into the door check's rules
def test_setup_check_for_the_device(aws):
    z = zone()
    add(lit(), z.sk, "open")
    add(plain(128), z.sk, "closed", at=T0 + 1)
    run()
    check = dc.setup_check(FridgeTable(), ACCOUNT, D1)
    assert check.source == "setup"
    [rule] = check.rules
    assert (rule.box, rule.feature, rule.direction) == ((0.0, 0.0, 0.5, 1.0), "blue", "above")
    assert dc.setup_check(FridgeTable(), ACCOUNT, D2) is None


# --- door-self-calibration: the closed anchor ---


def anchor_of(image: bytes) -> bytes:
    return alignment.edges_to_bytes(alignment.edge_map(image))


def checker_halves(level: int) -> bytes:
    return color_jpeg(
        (level,) * 3, [((0.25, 0.25, 0.25, 0.5), (255 - level,) * 3)], size=(200, 100)
    )


# Anchor from the newest closed reference
def test_anchor_from_the_newest_closed_reference(aws):
    older, newer = checker_halves(30), checker_halves(200)
    z = zone()
    add(older, z.sk, "closed", at=T0)
    add(lit(), z.sk, "open", at=T0 + 1)
    add(newer, z.sk, "closed", at=T0 + 2)
    run()
    assert dc.load_anchor(FridgeTable(), ACCOUNT, D1) == anchor_of(newer)
    s = alignment.load_alignment(FridgeTable(), ACCOUNT, D1)
    assert (s.dx, s.dy, s.failures, s.moved) == (0, 0, 0, False)


def test_no_anchor_before_setup(aws):
    assert dc.load_anchor(FridgeTable(), ACCOUNT, D1) is None


# Failed run keeps the anchor
def test_failed_run_keeps_the_anchor(aws):
    z = zone()
    add(lit(), z.sk, "open")
    add(checker_halves(30), z.sk, "closed", at=T0 + 1)
    run()
    anchor = dc.load_anchor(FridgeTable(), ACCOUNT, D1)
    alignment.record(
        FridgeTable(), ACCOUNT, D1, alignment.Alignment(True, 0.02, 0, 0.01, "first"), T0 + 5
    )
    other = zone({"x": 0.6, "y": 0, "width": 0.4, "height": 1}, "Drawer", at=T0 + 2)
    add(plain(128), other.sk, "closed", at=T0 + 3)
    assert_fails("Drawer needs an open and a closed reference")
    assert dc.load_anchor(FridgeTable(), ACCOUNT, D1) == anchor
    assert alignment.load_alignment(FridgeTable(), ACCOUNT, D1).dx == pytest.approx(0.02)


# Setup run clears moved
def test_setup_run_clears_moved(aws):
    z = zone()
    add(lit(), z.sk, "open")
    add(checker_halves(30), z.sk, "closed", at=T0 + 1)
    moved = alignment.Alignment(True, 0.05, 0, 0.01, "first")
    alignment.record(FridgeTable(), ACCOUNT, D1, moved, T0 + 7)
    assert alignment.load_alignment(FridgeTable(), ACCOUNT, D1).moved
    run()
    s = alignment.load_alignment(FridgeTable(), ACCOUNT, D1)
    assert (s.dx, s.dy, s.failures, s.moved, s.moved_at_ms) == (0, 0, 0, False, None)
    assert s.last_moved_at_ms == T0 + 7


# Fridge light measured strictly in setup
DAYLIT_STEEL = (110, 150, 200)


def _blue_setup_scores(extra: bytes) -> tuple[float, float]:
    """Scores of a lit open reference and `extra` (closed) under a `blue` setup zone."""
    z = zone()
    opened = add(lit(), z.sk, "open")
    add(plain(128), z.sk, "closed", at=T0 + 1)
    setup = run()
    assert setup.zones[0].feature == "blue"
    other = add(extra, z.sk, "closed", at=T0 + 120_000)
    scores = dc.reference_scores(dc.list_references(FridgeTable(), ACCOUNT, D1), setup)
    return scores[opened.sk], scores[other.sk]


# Daylit steel is not fridge light
def test_daylit_steel_is_not_fridge_light(aws):
    daylit = color_jpeg(GREY, [((0.0, 0.0, 0.15, 1.0), DAYLIT_STEEL)], size=(200, 100))
    _, score = _blue_setup_scores(daylit)
    assert score == pytest.approx(0.0, abs=0.002)


# Fridge interior is fridge light
def test_fridge_interior_is_fridge_light(aws):
    opened, _ = _blue_setup_scores(plain(128))
    assert opened == pytest.approx(0.1, abs=0.005)
