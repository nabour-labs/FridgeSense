"""door-calibration: door references, the setup run and its storage."""

import pytest

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


def add(image, box, status, device=D1, at=T0):
    return dc.add_reference(FridgeTable(), ACCOUNT, device, image, box, status, now_ms=at)


def run(device=D1, at=T0 + 60_000):
    return dc.run(FridgeTable(), ACCOUNT, device, now_ms=at)


def halves(left: int, right: int) -> bytes:
    return color_jpeg((left,) * 3, [((0.5, 0.0, 0.5, 1.0), (right,) * 3)], size=(200, 100))


def plain(level: int) -> bytes:
    return color_jpeg((level,) * 3, size=(200, 100))


# Reference added
def test_reference_added(aws):
    image = color_jpeg(size=(960, 540))
    add(image, {"x": 0.38, "y": 0.32, "width": 0.21, "height": 0.30}, "open")
    [ref] = dc.list_references(FridgeTable(), ACCOUNT, D1)
    assert ref.sk
    assert ref.box == (0.38, 0.32, 0.21, 0.30)
    assert ref.status == "open"
    assert ref.image == image
    assert ref.created_at == "2026-10-15T19:20:00.000Z"


def test_references_listed_oldest_first(aws):
    add(plain(10), LEFT, "open", at=T0 + 2)
    add(plain(20), LEFT, "closed", at=T0 + 1)
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


# Reference limit
def test_reference_limit(aws):
    for n in range(12):
        add(plain(10), LEFT, "open", at=T0 + n)
    with pytest.raises(dc.TooMany):
        add(plain(10), LEFT, "open", at=T0 + 12)
    add(plain(10), LEFT, "open", device=D2)  # per device


# Reference deleted
def test_reference_deleted(aws):
    ref = add(plain(10), LEFT, "open")
    assert dc.delete_reference(FridgeTable(), ACCOUNT, D1, ref.sk) is True
    assert dc.list_references(FridgeTable(), ACCOUNT, D1) == []
    assert dc.delete_reference(FridgeTable(), ACCOUNT, D1, ref.sk) is False
    assert dc.delete_reference(FridgeTable(), ACCOUNT, D1, "ITEM#milk") is False


# Setup marked stale
def test_setup_marked_stale(aws):
    add(color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), BLUE)], size=(200, 100)), LEFT, "open")
    add(plain(128), LEFT, "closed", at=T0 + 1)
    run(at=T0 + 10)
    assert dc.load_setup(FridgeTable(), ACCOUNT, D1).stale is False
    new = add(plain(128), LEFT, "closed", at=T0 + 20)
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


def test_no_setup_yet(aws):
    assert dc.load_setup(FridgeTable(), ACCOUNT, D1) is None


# Setup from one open and one closed reference
def test_setup_from_one_open_and_one_closed_reference(aws):
    opened = add(color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), BLUE)], size=(200, 100)), LEFT, "open")
    shut = add(plain(128), LEFT, "closed", at=T0 + 1)
    setup = run()
    [zone] = setup.zones
    assert zone.box == (0.0, 0.0, 0.5, 1.0)
    assert zone.feature == "blue"
    assert zone.direction == "above"
    assert zone.threshold == pytest.approx(0.05, abs=0.005)
    assert zone.margin == pytest.approx(0.1, abs=0.005)
    assert setup.stale is False
    assert setup.ran_at == "2026-10-15T19:21:00.000Z"
    scores = dc.reference_scores(dc.list_references(FridgeTable(), ACCOUNT, D1), setup)
    assert scores[opened.sk] == pytest.approx(0.1, abs=0.005)
    assert scores[shut.sk] == pytest.approx(0.0, abs=0.005)
    assert dc.load_setup(FridgeTable(), ACCOUNT, D1) == setup


# Brightness chosen when there is no color
def test_brightness_chosen_when_there_is_no_color(aws):
    add(plain(100), WHOLE, "closed")
    add(halves(40, 160), WHOLE, "closed", at=T0 + 1)
    add(plain(200), WHOLE, "open", at=T0 + 2)
    [zone] = run().zones
    assert zone.feature == "brightness"
    assert zone.direction == "above"
    assert zone.margin == pytest.approx(0.39, abs=0.02)
    assert zone.threshold == pytest.approx(0.59, abs=0.02)


# Change chosen when brightness is the same
def test_change_chosen_when_brightness_is_the_same(aws):
    add(plain(128), WHOLE, "closed")
    add(halves(40, 216), WHOLE, "open", at=T0 + 1)
    [zone] = run().zones
    assert zone.feature == "change"
    assert zone.direction == "above"
    assert zone.margin == pytest.approx(0.35, abs=0.02)
    assert len(zone.baseline) == 32 * 32 * 3


# Darker when open
def test_darker_when_open(aws):
    add(plain(220), WHOLE, "closed")
    add(halves(180, 240), WHOLE, "closed", at=T0 + 1)
    add(plain(90), WHOLE, "open", at=T0 + 2)
    [zone] = run().zones
    assert zone.feature == "brightness"
    assert zone.direction == "below"
    assert zone.margin == pytest.approx(0.47, abs=0.02)
    assert zone.threshold == pytest.approx(0.59, abs=0.02)


# Overlapping boxes become one zone
def test_overlapping_boxes_become_one_zone(aws):
    still = color_jpeg(GREY, [((0.0, 0.0, 1.0, 1.0), BLUE)], size=(200, 100))
    add(still, {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.4}, "open")
    add(plain(128), {"x": 0.12, "y": 0.1, "width": 0.3, "height": 0.4}, "closed", at=T0 + 1)
    add(still, {"x": 0.5, "y": 0.6, "width": 0.1, "height": 0.1}, "open", at=T0 + 2)
    add(plain(128), {"x": 0.5, "y": 0.6, "width": 0.1, "height": 0.1}, "closed", at=T0 + 3)
    zones = run().zones
    assert [z.box for z in zones] == [(0.1, 0.1, 0.32, 0.4), (0.5, 0.6, 0.1, 0.1)]


def assert_fails(message: str):
    before = dc.load_setup(FridgeTable(), ACCOUNT, D1)
    with pytest.raises(dc.SetupFailed, match=message) as failed:
        run(at=T0 + 999_000)
    assert dc.load_setup(FridgeTable(), ACCOUNT, D1) == before
    return failed.value


# Missing a status
def test_missing_a_status_no_references(aws):
    assert_fails("zone 1 needs an open and a closed reference")


@pytest.mark.parametrize("status", ["open", "closed"])
def test_missing_a_status_all_the_same(aws, status):
    add(plain(100), LEFT, status)
    add(plain(120), LEFT, status, at=T0 + 1)
    failed = assert_fails("zone 1 needs an open and a closed reference")
    assert len(failed.scores) == 2


def test_missing_a_status_names_the_zone(aws):
    add(plain(100), LEFT, "closed")
    add(plain(200), LEFT, "open", at=T0 + 1)
    add(plain(100), {"x": 0.6, "y": 0, "width": 0.4, "height": 1}, "closed", at=T0 + 2)
    assert_fails("zone 2 needs an open and a closed reference")


# Open and closed overlap
def test_open_and_closed_overlap(aws):
    # 0.5% of the zone: a 10x5 px block in the 100x100 left half
    add(color_jpeg(GREY, [((0.1, 0.4, 0.05, 0.05), BLUE)], size=(200, 100)), LEFT, "open")
    add(plain(128), LEFT, "closed", at=T0 + 1)
    add(plain(128), LEFT, "closed", at=T0 + 2)
    failed = assert_fails("zone 1: open and closed references overlap")
    refs = dc.list_references(FridgeTable(), ACCOUNT, D1)
    assert failed.scores[refs[0].sk] == pytest.approx(0.005, abs=0.003)
    assert failed.scores[refs[1].sk] == pytest.approx(0.0, abs=0.003)


def test_failure_keeps_the_previous_setup(aws):
    add(color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), BLUE)], size=(200, 100)), LEFT, "open")
    add(plain(128), LEFT, "closed", at=T0 + 1)
    first = run()
    add(plain(128), {"x": 0.6, "y": 0, "width": 0.4, "height": 1}, "closed", at=T0 + 2)
    assert_fails("zone 2 needs an open and a closed reference")
    assert dc.load_setup(FridgeTable(), ACCOUNT, D1).zones == first.zones


# Too many zones
def test_too_many_zones(aws):
    for n in range(7):
        add(plain(100), {"x": n * 0.14, "y": 0, "width": 0.1, "height": 0.1}, "open", at=T0 + n)
    assert_fails("at most 6 separate zones")


# Blue preferred over color on a tie
def test_blue_preferred_over_color_on_a_tie(aws):
    add(color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), BLUE)], size=(200, 100)), LEFT, "open")
    add(plain(128), LEFT, "closed", at=T0 + 1)
    [zone] = run().zones
    assert zone.feature == "blue"
    assert zone.margin == pytest.approx(0.1, abs=0.005)


# Color chosen when the open reference is not blue
def test_color_chosen_when_the_open_reference_is_not_blue(aws):
    add(color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), (200, 60, 40))], size=(200, 100)), LEFT, "open")
    add(plain(128), LEFT, "closed", at=T0 + 1)
    [zone] = run().zones
    assert zone.feature == "color"
    assert zone.margin == pytest.approx(0.1, abs=0.005)


# Setup kept per device / setup turns into the door check's rules
def test_setup_check_for_the_device(aws):
    add(color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), BLUE)], size=(200, 100)), LEFT, "open")
    add(plain(128), LEFT, "closed", at=T0 + 1)
    run()
    check = dc.setup_check(FridgeTable(), ACCOUNT, D1)
    assert check.source == "setup"
    [rule] = check.rules
    assert (rule.box, rule.feature, rule.direction) == ((0.0, 0.0, 0.5, 1.0), "blue", "above")
    assert dc.setup_check(FridgeTable(), ACCOUNT, D2) is None
