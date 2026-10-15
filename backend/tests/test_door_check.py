"""door-event-detection: still timing and the door-open check."""

import pytest

from fridgesense.door_events import DoorCheck, brightness, still_times
from tests.conftest import jpeg


def test_still_times_spread_across_window():
    assert still_times(1786715596000, 1786715621000) == [
        1786715601000,
        1786715606000,
        1786715611000,
        1786715616000,
    ]


# Fridge light visible
def test_fridge_light_visible():
    check = DoorCheck(box=(0.0, 0.0, 1.0, 1.0), threshold=0.5)
    open_, brightest = check.evaluate([jpeg(0.1), jpeg(0.8), jpeg(0.2)])
    assert open_ is True
    assert brightest == pytest.approx(0.8, abs=0.02)


# Door stayed closed
def test_door_stayed_closed_brightness():
    check = DoorCheck(box=(0.0, 0.0, 1.0, 1.0), threshold=0.5)
    open_, brightest = check.evaluate([jpeg(0.1), jpeg(0.3)])
    assert open_ is False
    assert brightest == pytest.approx(0.3, abs=0.02)


def test_threshold_is_inclusive():
    still = jpeg(0.6)
    level = brightness(still, (0.0, 0.0, 1.0, 1.0))
    assert DoorCheck(box=(0.0, 0.0, 1.0, 1.0), threshold=level).evaluate([still])[0] is True


# Box and threshold from config
def test_box_and_threshold_from_config():
    still = jpeg(bright_box=(0.6, 0.0, 0.4, 1.0))
    right = DoorCheck.from_config("0.6,0.0,0.4,1.0", "0.5")
    left = DoorCheck.from_config("0.0,0.0,0.4,1.0", "0.5")
    assert right.evaluate([still])[0] is True
    assert left.evaluate([still])[0] is False


def test_config_defaults_and_validation():
    default = DoorCheck.from_config(None, None)
    assert default.box == (0.25, 0.1, 0.5, 0.8)
    assert default.threshold == 0.5
    with pytest.raises(ValueError):
        DoorCheck.from_config("0.9,0,0.5,1", "0.5")  # box past the right edge
    with pytest.raises(ValueError):
        DoorCheck.from_config("0,0,1", "0.5")
