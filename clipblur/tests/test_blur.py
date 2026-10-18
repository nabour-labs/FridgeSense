"""clip-face-blur: faces blurred in every frame, and nothing outside them."""

import av
import numpy as np
import pytest

from clipblur.blur import ClipUnreadable, blur_clip
from tests.clips import FakeDetector, box_mask, ellipse_mask, luma_frames, make_clip

FACE = (256, 72, 384, 216)
FACE_ENLARGED = (237, 50, 403, 238)  # 30% bigger about its centre


@pytest.fixture
def raw(tmp_path):
    return make_clip(tmp_path / "clip-raw.mp4")


def blurred(raw, tmp_path, detector):
    out = tmp_path / "clip.mp4"
    stats = blur_clip(raw, out, detector)
    return out, stats


def assert_blurred(frame, box):
    assert frame[ellipse_mask(frame.shape, box)].std() < 10


def assert_unchanged_outside(frame, before, boxes):
    outside = ~np.any([box_mask(frame.shape, b) for b in boxes], axis=0) if boxes else None
    diff = np.abs(frame - before)
    assert (diff[outside] if outside is not None else diff).mean() <= 3


# Scenario: One face blurred
def test_one_face_blurred(raw, tmp_path):
    out, _ = blurred(raw, tmp_path, FakeDetector([[*FACE, 0.9]]))
    for frame, before in zip(luma_frames(out), luma_frames(raw), strict=True):
        assert_blurred(frame, FACE_ENLARGED)
        assert_unchanged_outside(frame, before, [FACE_ENLARGED])


# Scenario: Two faces blurred
def test_two_faces_blurred(raw, tmp_path):
    faces = [(32, 36, 128, 144), (448, 108, 544, 216)]
    enlarged = [(18, 20, 142, 160), (434, 92, 558, 232)]
    out, _ = blurred(raw, tmp_path, FakeDetector([[*f, 0.9] for f in faces]))
    for frame, before in zip(luma_frames(out), luma_frames(raw), strict=True):
        for box in enlarged:
            assert_blurred(frame, box)
        assert_unchanged_outside(frame, before, enlarged)


# Scenario: Face at the frame edge
def test_face_at_the_frame_edge(raw, tmp_path):
    out, stats = blurred(raw, tmp_path, FakeDetector([[600, 300, 660, 380, 0.9]]))
    assert stats.frames_with_faces == 30
    for frame, before in zip(luma_frames(out), luma_frames(raw), strict=True):
        assert_unchanged_outside(frame, before, [(591, 288, 640, 360)])


# Scenario: No faces
def test_no_faces(raw, tmp_path):
    out, stats = blurred(raw, tmp_path, FakeDetector([]))
    assert stats.frames_with_faces == 0
    for frame, before in zip(luma_frames(out), luma_frames(raw), strict=True):
        assert_unchanged_outside(frame, before, [])


# Scenario: Face in some frames
def test_face_in_some_frames(raw, tmp_path):
    detector = FakeDetector([[*FACE, 0.9]], frames=range(10, 20))
    out, stats = blurred(raw, tmp_path, detector)
    assert detector.calls == 30
    assert (stats.frames, stats.frames_with_faces) == (30, 10)
    for n, (frame, before) in enumerate(zip(luma_frames(out), luma_frames(raw), strict=True)):
        if 10 <= n < 20:
            assert_blurred(frame, FACE_ENLARGED)
        else:
            assert_unchanged_outside(frame, before, [])


# Scenario: Low score ignored
def test_low_score_ignored(raw, tmp_path):
    out, stats = blurred(raw, tmp_path, FakeDetector([[*FACE, 0.15]]))
    assert stats.frames_with_faces == 0
    for frame, before in zip(luma_frames(out), luma_frames(raw), strict=True):
        assert_unchanged_outside(frame, before, [])


# Scenario: Same timing
def test_same_timing(tmp_path):
    raw = make_clip(tmp_path / "clip-raw.mp4", width=1920, height=1080, frames=120, fps=15)
    out, stats = blurred(raw, tmp_path, FakeDetector([]))
    assert stats.frames == 120
    with av.open(str(out)) as c:
        [video] = c.streams.video
        assert not c.streams.audio
        assert (video.codec_context.width, video.codec_context.height) == (1920, 1080)
        assert video.codec_context.name == "h264"
        assert video.codec_context.pix_fmt == "yuv420p"
        assert video.average_rate == 15
        assert sum(1 for _ in c.decode(video=0)) == 120
    # +faststart: the moov box comes before the media data
    data = out.read_bytes()
    assert data.index(b"moov") < data.index(b"mdat")


# Scenario: Detector fails
def test_detector_fails(raw, tmp_path):
    out = tmp_path / "clip.mp4"
    with pytest.raises(RuntimeError):
        blur_clip(raw, out, FakeDetector([], fail_on=5))
    assert not out.exists()


# Scenario: Decode error
def test_decode_error(tmp_path):
    raw = tmp_path / "clip-raw.mp4"
    raw.write_bytes(b"not a video")
    out = tmp_path / "clip.mp4"
    with pytest.raises(ClipUnreadable):
        blur_clip(raw, out, FakeDetector([]))
    assert not out.exists()
