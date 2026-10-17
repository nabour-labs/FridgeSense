"""door-event-detection: the event clip cut down to the door's open span."""

import pytest

from fridgesense.clip_frames import ClipUnavailable, cut_clip
from tests.clip_video import door_clip

GOP = 8  # a keyframe every 8 frames of 250 ms: every 2.0 s


def stored(path) -> tuple[float, float, list[float]]:
    """(first frame time, last frame time, keyframe times) of the stored clip, in seconds."""
    import av

    with av.open(str(path)) as c:
        s = c.streams.video[0]
        times = [
            (float(p.pts * s.time_base), p.is_keyframe) for p in c.demux(s) if p.pts is not None
        ]
    return times[0][0], times[-1][0], [t for t, key in times if key]


# Clip cut to the open span
def test_clip_cut_to_the_open_span(tmp_path):
    clip = door_clip(tmp_path / "event.mp4", [(4500, 12_500)], gop=GOP)
    out, span = cut_clip(clip, 4500, 12_500, tmp_path)
    first, last, keys = stored(out)
    assert out.parent == tmp_path and out != clip
    assert first == 0.0 and keys[0] == 0.0  # starts on the 4.0 s keyframe
    assert span == (0.5, 8.5)
    assert last >= 8.5  # the closed frame at 12.5 s is in
    assert last < 9.0
    assert clip.exists()  # the caller deletes the source


# Door still open at the end of the clip
def test_door_still_open_at_the_end_of_the_clip(tmp_path):
    clip = door_clip(tmp_path / "event.mp4", [(15_000, 20_000)], gop=GOP)
    out, span = cut_clip(clip, 15_000, None, tmp_path)
    first, last, _ = stored(out)
    assert first == 0.0
    assert span[0] == 1.0  # 15.0 s is 1.0 s past the 14.0 s keyframe
    assert span[1] == pytest.approx(6.0, abs=0.05)  # to the clip's end at 20.0 s
    assert last == pytest.approx(5.96, abs=0.05)


# Cut fails
def test_cut_fails_on_an_unreadable_clip(tmp_path):
    bad = tmp_path / "event.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(ClipUnavailable) as e:
        cut_clip(bad, 4500, 12_500, tmp_path)
    assert e.value.reason == "cut_failed"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["event.mp4"]  # no half-written cut
