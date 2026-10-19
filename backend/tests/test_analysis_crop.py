"""door-event-detection: Analysis crop from the fridge area."""

import pytest

from fridgesense.fridge_area import analysis_box


def rounded(box):
    return tuple(round(v, 4) for v in box)


# Box from the fridge area
def test_box_from_the_fridge_area():
    box = analysis_box((0.362, 0.329, 0.233, 0.611), None)
    assert rounded(box) == pytest.approx((0.3387, 0.2985, 0.2796, 0.6721), abs=1e-4)


# Box clamped at the frame edge
def test_box_clamped_at_the_frame_edge():
    box = analysis_box((0.0, 0.5, 0.4, 0.5), None)
    assert rounded(box) == pytest.approx((0.0, 0.475, 0.44, 0.525), abs=1e-4)


# No fridge area
def test_no_fridge_area():
    assert analysis_box(None, (0.30, 0.0, 0.34, 1.0)) == (0.30, 0.0, 0.34, 1.0)


def test_no_fridge_area_and_no_still_crop():
    assert analysis_box(None, None) is None
