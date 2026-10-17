"""door-clip-evaluation: scoring the door check on a clip against its labels."""

import httpx
import pytest
import respx

from fridgesense.door_events import DoorCheck
from tests.clips.harness import (
    ColourSource,
    Opening,
    evaluate_clip,
    offline_camera,
    score,
    tolerance_s,
)

CLIP = "Ring_Fridge_20261015_1920.mp4"
GREY, LIT = (128, 128, 128), (40, 90, 200)  # steel doors, lit fridge interior
CHECK = DoorCheck()  # the default zones and threshold


def clip(*changes, duration_s=20.0) -> ColourSource:
    """A clip that starts closed; `changes` are (second, open?) pairs."""
    return ColourSource(
        [(0.0, GREY)] + [(t, LIT if is_open else GREY) for t, is_open in changes], duration_s
    )


@pytest.fixture(autouse=True)
def _default_config(monkeypatch):
    for name in ("DOOR_ZONES", "DOOR_THRESHOLD", "STILL_INTERVAL_MS"):
        monkeypatch.delenv(name, raising=False)


LABELLED = (Opening(4.0, 12.5),)


def gaps(offsets: list[float]) -> list[float]:
    return [b - a for a, b in zip(offsets, offsets[1:], strict=False)]


def scored(detected, openings=LABELLED, tolerance=1.5, best=0.4):
    return score(CLIP, list(openings), 20.0, detected, tolerance, best, 0.02)


# Opening found with correct times
def test_opening_found_with_correct_times():
    result = scored((4.6, 13.0))
    assert result.verdict == "TP"
    assert result.passed, result.failures
    assert result.open_error_s == pytest.approx(0.6)
    assert result.close_error_s == pytest.approx(0.5)


def test_opening_found_on_a_clip():
    result = evaluate_clip(CLIP, clip((4.0, True), (12.5, False)), [Opening(4.0, 12.5)], CHECK)
    assert result.verdict == "TP"
    assert result.passed, result.failures
    assert 0 <= result.open_error_s <= 1.0
    assert 0 <= result.close_error_s <= 1.0


# Open time too far off
def test_open_time_too_far_off():
    result = scored((6.0, 13.0))
    assert not result.passed
    [message] = result.failures
    assert CLIP in message
    assert "labelled 4.0 s" in message
    assert "detected 6.0 s" in message
    assert "tolerance 1.5 s" in message


# Missed opening
def test_missed_opening():
    result = evaluate_clip(CLIP, clip(), [Opening(4.0, 12.5)], CHECK)
    assert result.verdict == "FN"
    [message] = result.failures
    assert CLIP in message
    assert "missed opening" in message
    assert "best zone value 0.000" in message
    assert "threshold 0.01" in message


# False opening
def test_false_opening():
    result = evaluate_clip(CLIP, clip((4.0, True), (12.5, False)), [], CHECK)
    assert result.verdict == "FP"
    [message] = result.failures
    assert CLIP in message
    assert "false opening" in message
    assert f"{result.detected[0]:.1f} s" in message
    assert f"{result.detected[1]:.1f} s" in message


# No opening, none detected
def test_no_opening_none_detected():
    result = evaluate_clip(CLIP, clip(), [], CHECK)
    assert result.verdict == "TN"
    assert result.passed


# Door still open at clip end
def test_door_still_open_at_clip_end():
    result = evaluate_clip(CLIP, clip((3.0, True)), [Opening(3.0, None)], CHECK)
    assert result.verdict == "TP"
    assert result.detected[1] == pytest.approx(20.0)
    assert result.close_error_s == pytest.approx(0.0)
    assert result.passed, result.failures


# Shorter still interval
def test_shorter_still_interval(monkeypatch):
    monkeypatch.setenv("STILL_INTERVAL_MS", "500")
    result = evaluate_clip(CLIP, clip(duration_s=10.0), [], CHECK)
    assert all(0.45 <= g <= 0.5 for g in gaps(result.still_offsets_s))
    assert result.tolerance_s == pytest.approx(0.75)


# Long clip hits the still cap
def test_long_clip_hits_the_still_cap():
    result = evaluate_clip(CLIP, clip(duration_s=120.0), [], CHECK, interval_ms=1000)
    assert len(result.still_offsets_s) == 30
    assert all(3.8 <= g <= 3.95 for g in gaps(result.still_offsets_s))
    assert result.tolerance_s == pytest.approx(1.5 * 120 / 31, abs=0.01)


def test_tolerance_is_one_and_a_half_intervals():
    assert tolerance_s(20_000, 1000) == pytest.approx(1.5)
    assert tolerance_s(120_000, 1000) == pytest.approx(1.5 * 120 / 31)


# Network blocked
def test_network_blocked():
    with offline_camera(clip(), 0) as (ring, http):
        with pytest.raises(respx.models.AllMockedAssertionError):
            http.get("https://example.com/")
        with pytest.raises(respx.models.AllMockedAssertionError):
            httpx.post("https://bedrock-runtime.us-east-1.amazonaws.com/model/x/converse")
