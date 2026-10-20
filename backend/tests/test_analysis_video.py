"""door-event-detection: Analysis video built from the open span."""

from fridgesense.door_events import MAX_VIDEO_FRAMES, video_frame_indexes


def test_short_opening_starts_one_frame_before_the_span():
    # open span is frames 3-12 (indexes 2-11): the video is frames 2-12
    assert video_frame_indexes(list(range(2, 12))) == (list(range(1, 12)), 1)


# Long opening thinned
def test_long_opening_thinned():
    span = list(range(1, 231))  # with the frame before it: indexes 0-230, 231 frames
    indexes, step = video_frame_indexes(span)
    assert MAX_VIDEO_FRAMES == 40
    assert step == 6
    assert indexes == list(range(0, 231, 6))
    assert len(indexes) == 39


# Span starts at the first frame
def test_span_starts_at_the_first_frame():
    assert video_frame_indexes([0, 1, 2]) == ([0, 1, 2], 1)


def test_exactly_forty_frames_kept_whole():
    indexes, step = video_frame_indexes(list(range(1, 40)))
    assert (len(indexes), step) == (40, 1)
