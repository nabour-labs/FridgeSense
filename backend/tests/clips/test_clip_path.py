"""door-event-detection on local clips: the door check on clip frames vs sampled stills."""

import pytest

from fridgesense.door_events import DoorCheck
from tests.clip_video import door_clip
from tests.clips.harness import AvSource, ColourSource, Opening, evaluate_clip

CLIP = "Ring_Fridge_20261015_2023.mp4"
CHECK = DoorCheck(zones=((0.0, 0.0, 1.0, 1.0),), threshold=0.02)
OPENING = [Opening(63.7, 66.7)]


@pytest.fixture(autouse=True)
def _default_config(monkeypatch):
    for name in ("DOOR_ZONES", "DOOR_THRESHOLD", "STILL_INTERVAL_MS", "DOOR_FRAME_INTERVAL_MS"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="module")
def short_opening(tmp_path_factory):
    """121.9 s of closed doors, open only from 63.7 s to 66.7 s."""
    path = tmp_path_factory.mktemp("clip") / CLIP
    return door_clip(path, [(63_700, 66_700)], duration_ms=121_900, step_ms=100)


# Short opening between stills
def test_short_opening_between_stills(short_opening):
    result = evaluate_clip(CLIP, AvSource(short_opening), OPENING, CHECK)
    assert result.verdict == "TP", result.failures
    assert result.passed, result.failures
    assert result.tolerance_s == pytest.approx(0.75)  # 1.5 x the 500 ms frame interval


def test_stills_alone_miss_it(short_opening):
    result = evaluate_clip(CLIP, AvSource(short_opening), OPENING, CHECK, frame_interval_ms=None)
    assert result.verdict == "FN"  # 30 stills ~3.9 s apart all fall outside the opening


def test_frame_interval_from_config(short_opening, monkeypatch):
    monkeypatch.setenv("DOOR_FRAME_INTERVAL_MS", "250")
    result = evaluate_clip(CLIP, AvSource(short_opening), OPENING, CHECK)
    assert result.tolerance_s == pytest.approx(0.375)
    assert len(result.trace.stills) == 488  # 121.9 s / 250 ms


def test_stand_in_clip_without_a_file_uses_stills():
    """A solid-colour stand-in has no MP4 to serve: Ring has no clip, stills are sampled."""
    source = ColourSource(
        [(0.0, (128, 128, 128)), (4.0, (40, 90, 200)), (12.5, (128, 128, 128))], 20.0
    )
    result = evaluate_clip(CLIP, source, [Opening(4.0, 12.5)], CHECK)
    assert result.verdict == "TP"
    assert len(result.trace.stills) == 20  # one still per second, as before
