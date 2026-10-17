"""door-event-detection: sampling the event clip into frames, and the frame interval setting."""

import pytest

from fridgesense.clip_frames import (
    ClipUnavailable,
    clip_duration_ms,
    frames_at,
    parse_frame_interval,
    sample_frames,
)
from tests.clip_video import door_clip, write_mp4

GREY, BLUE, RED = (128, 128, 128), (40, 90, 200), (200, 50, 50)


def colour(img) -> tuple[int, int, int]:
    return img.getpixel((5, 5))


def near(a, b, tol=6) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b, strict=True))


# Frame every 500 ms
def test_frame_every_500_ms(tmp_path):
    clip = door_clip(tmp_path / "c.mp4", [], duration_ms=20_000)
    assert clip_duration_ms(clip) == 20_000
    offsets = [ms for ms, _ in sample_frames(clip, 500)]
    assert offsets == list(range(0, 20_000, 500))
    assert len(offsets) == 40


# Interval from config
def test_interval_from_config(tmp_path):
    clip = door_clip(tmp_path / "c.mp4", [], duration_ms=20_000)
    offsets = [ms for ms, _ in sample_frames(clip, 1000)]
    assert offsets == list(range(0, 20_000, 1000))


# Frame shown at an offset
def test_frame_shown_at_an_offset(tmp_path):
    clip = write_mp4(tmp_path / "c.mp4", [(0, GREY), (400, BLUE), (800, RED), (1960, RED)])
    frames = dict(frames_at(clip, [0, 500, 799, 800, 1990]))
    assert near(colour(frames[0]), GREY)
    assert near(colour(frames[500]), BLUE)  # the frame that starts at 400 ms
    assert near(colour(frames[799]), BLUE)
    assert near(colour(frames[800]), RED)
    assert near(colour(frames[1990]), RED)  # after the last frame starts: it is still shown


def test_offsets_outside_the_clip_are_skipped(tmp_path):
    clip = write_mp4(tmp_path / "c.mp4", [(0, GREY), (960, GREY)])  # 1.0 s
    assert [ms for ms, _ in frames_at(clip, [-1, 0, 999, 1000, 5000])] == [0, 999]


def test_lit_spans(tmp_path):
    clip = door_clip(tmp_path / "c.mp4", [(4000, 12_500)], duration_ms=20_000)
    lit = [ms for ms, img in sample_frames(clip, 500) if near(colour(img), BLUE, 12)]
    assert lit == list(range(4000, 12_500, 500))


# Unreadable clip
def test_unreadable_clip(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b'{"errors": []}')
    with pytest.raises(ClipUnavailable) as e:
        list(sample_frames(bad, 500))
    assert e.value.reason == "decode_failed"


def test_clip_cut_short_fails_partway(tmp_path):
    clip = door_clip(tmp_path / "c.mp4", [], duration_ms=20_000, size=(640, 360))
    data = clip.read_bytes()
    clip.write_bytes(data[: len(data) // 2])  # header kept, frames cut off
    with pytest.raises(ClipUnavailable) as e:
        list(sample_frames(clip, 500))
    assert e.value.reason in ("decode_failed", "no_frames")


# Invalid interval
@pytest.mark.parametrize("value", ["0", "-5", "abc", "1.5"])
def test_invalid_interval(value):
    with pytest.raises(ValueError, match="DOOR_FRAME_INTERVAL_MS"):
        parse_frame_interval(value)


@pytest.mark.parametrize(
    ("value", "expected"), [(None, 500), ("", 500), (" ", 500), ("1000", 1000)]
)
def test_interval_default_and_value(value, expected):
    assert parse_frame_interval(value) == expected
