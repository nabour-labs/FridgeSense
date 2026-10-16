"""door-clip-evaluation: the clip labels fixture and the expected open span."""

import json

import pytest

from tests.clips.harness import LabelError, Opening, expected_span, load_labels

A = "Ring_Fridge_20261015_1920.mp4"
B = "Ring_Fridge_20261015_1934.mp4"


def write(tmp_path, clips: dict) -> str:
    path = tmp_path / "door_labels.json"
    path.write_text(json.dumps({"clips": clips}))
    return path


def openings(*spans) -> dict:
    return {"openings": [{"opened_s": o, "closed_s": c} for o, c in spans]}


# Valid labels load
def test_valid_labels_load(tmp_path):
    labels = load_labels(write(tmp_path, {A: openings((4.0, 12.5)), B: openings()}))
    assert labels == {A: [Opening(4.0, 12.5)], B: []}


# Close before open
def test_close_before_open(tmp_path):
    with pytest.raises(LabelError, match=rf"{A}.*closed_s must be after opened_s"):
        load_labels(write(tmp_path, {A: openings((10, 8))}))


# Overlapping openings
def test_overlapping_openings(tmp_path):
    with pytest.raises(LabelError, match=rf"{A}.*openings overlap"):
        load_labels(write(tmp_path, {A: openings((4, 12), (10, 15))}))


# Negative or missing time
@pytest.mark.parametrize("opening", [{"opened_s": -1, "closed_s": 5}, {"closed_s": 5}])
def test_negative_or_missing_time(tmp_path, opening):
    with pytest.raises(LabelError, match=rf"{A}.*opened_s"):
        load_labels(write(tmp_path, {A: {"openings": [opening]}}))


# Only one opening may stay open
def test_only_one_opening_may_stay_open(tmp_path):
    with pytest.raises(LabelError, match=rf"{A}.*only the last opening may have closed_s = null"):
        load_labels(write(tmp_path, {A: openings((2, None), (8, 9))}))


# Two openings in one clip
def test_two_openings_in_one_clip():
    assert expected_span([Opening(2.0, 6.0), Opening(15.0, 20.0)], 30.0) == (2.0, 20.0)


# Door still open at clip end (span part)
def test_door_still_open_at_clip_end_span():
    assert expected_span([Opening(3.0, None)], 25.1) == (3.0, 25.1)


def test_no_openings_no_span():
    assert expected_span([], 25.1) is None
