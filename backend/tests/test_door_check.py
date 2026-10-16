"""door-event-detection: still timing and the door-open check."""

import pytest

from fridgesense.door_events import DoorCheck, colorful_fraction, still_times
from tests.conftest import color_jpeg

HALVES = ((0.0, 0.0, 0.5, 1.0), (0.5, 0.0, 0.5, 1.0))
GREY = (128, 128, 128)
FRIDGE_BLUE = (40, 90, 200)


def test_still_times_spread_across_window():
    assert still_times(1786715596000, 1786715621000) == [
        1786715601000,
        1786715606000,
        1786715611000,
        1786715616000,
    ]


# Fridge light visible
def test_fridge_light_visible():
    # 10% of the left zone (100x100 px): a 20x50 px block
    still = color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), FRIDGE_BLUE)], size=(200, 100))
    check = DoorCheck(zones=HALVES, threshold=0.02)
    open_, score, zone = check.evaluate([color_jpeg(GREY, size=(200, 100)), still])
    assert open_ is True
    assert score == pytest.approx(0.10, abs=0.01)
    assert zone == 1


# Drawer opening seen only in the drawers zone
def test_drawer_opening_seen_only_in_drawers_zone():
    # 5% of the right zone: a 10x50 px block
    still = color_jpeg(GREY, [((0.7, 0.25, 0.05, 0.5), (200, 60, 40))], size=(200, 100))
    open_, score, zone = DoorCheck(zones=HALVES, threshold=0.02).evaluate([still])
    assert open_ is True
    assert score == pytest.approx(0.05, abs=0.01)
    assert zone == 2


# Brightness alone does not count
@pytest.mark.parametrize("level", [(230, 230, 230), (30, 30, 30)])
def test_brightness_alone_does_not_count(level):
    open_, score, _ = DoorCheck(zones=HALVES, threshold=0.02).evaluate([color_jpeg(level)])
    assert open_ is False
    assert score == 0


# Dark colored clothing does not count
def test_dark_colored_clothing_does_not_count():
    navy = color_jpeg(GREY, [((0.0, 0.0, 0.5, 1.0), (20, 25, 60))])
    open_, score, _ = DoorCheck(zones=HALVES, threshold=0.02).evaluate([navy])
    assert open_ is False
    assert score == 0


# Threshold is inclusive
def test_threshold_is_inclusive():
    still = color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), FRIDGE_BLUE)], size=(200, 100))
    level = colorful_fraction(still, HALVES[0])
    assert DoorCheck(zones=HALVES, threshold=level).evaluate([still])[0] is True


# Box and threshold from config
def test_zones_and_threshold_from_config():
    still = color_jpeg(GREY, [((0.6, 0.0, 0.4, 1.0), FRIDGE_BLUE)])
    right = DoorCheck.from_config("0.6,0.0,0.4,1.0", "0.02")
    left = DoorCheck.from_config("0.0,0.0,0.4,1.0", "0.02")
    assert right.evaluate([still])[0] is True
    assert left.evaluate([still])[0] is False


def test_several_zones_from_config():
    check = DoorCheck.from_config("0,0,0.5,1; 0.5,0,0.5,1", "0.1")
    assert check.zones == HALVES
    assert check.threshold == 0.1


def test_config_defaults():
    default = DoorCheck.from_config(None, None)
    assert default.zones == ((0.38, 0.32, 0.21, 0.30), (0.455, 0.60, 0.12, 0.18))
    assert default.threshold == 0.02


# Invalid zone config
@pytest.mark.parametrize("zones", ["0.9,0,0.5,1", "0,0,1", ";", "0,0,1,1;0,0,1"])
def test_invalid_zone_config(zones):
    with pytest.raises(ValueError, match="DOOR_ZONES"):
        DoorCheck.from_config(zones, "0.02")

