"""door-event-detection: a long closed run splits a motion into several openings."""

from fridgesense.door_events import MIN_CLOSED_GAP_MS, open_spans


def seconds(n: int) -> list[int]:
    """Request times one second apart: index i is still i + 1, at i * 1000 ms."""
    return [i * 1000 for i in range(n)]


def opened_at(n: int, stills: set[int]) -> list[bool]:
    """Open flags for stills numbered 1..n."""
    return [k in stills for k in range(1, n + 1)]


def as_stills(spans: list[list[int]]) -> list[list[int]]:
    return [[i + 1 for i in span] for span in spans]


def test_short_closed_run_stays_inside_the_opening():
    opened = opened_at(25, set(range(6, 11)) | set(range(15, 21)))
    assert as_stills(open_spans(opened, seconds(25))) == [list(range(6, 22))]


def test_long_closed_run_splits_the_opening():
    opened = opened_at(30, set(range(3, 7)) | set(range(20, 25)))
    assert as_stills(open_spans(opened, seconds(30))) == [list(range(3, 8)), list(range(20, 26))]


def test_gap_of_exactly_ten_seconds_splits():
    # closed stills 6..15: 10 s from still 6 to the next open still 16
    opened = opened_at(20, {3, 4, 5, 16})
    assert MIN_CLOSED_GAP_MS == 10_000
    assert as_stills(open_spans(opened, seconds(20))) == [[3, 4, 5, 6], [16, 17]]


def test_gap_just_under_ten_seconds_stays_one_opening():
    opened = opened_at(20, {3, 4, 5, 15})
    assert as_stills(open_spans(opened, seconds(20))) == [list(range(3, 17))]


def test_opening_runs_to_the_end():
    opened = opened_at(30, {2} | set(range(25, 31)))
    assert as_stills(open_spans(opened, seconds(30))) == [[2, 3], list(range(25, 31))]


def test_no_open_still_gives_no_span():
    assert open_spans(opened_at(10, set()), seconds(10)) == []


def test_gap_measured_in_time_not_stills():
    # 500 ms frames: 13 closed frames is only 6.5 s, so one opening
    opened = [True] * 4 + [False] * 13 + [True] * 2 + [False]
    times = [i * 500 for i in range(len(opened))]
    assert open_spans(opened, times) == [list(range(0, 20))]
