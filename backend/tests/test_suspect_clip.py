"""door-event-detection: a clip whose door check says "open" nearly throughout is suspect."""

from fridgesense.door_events import is_suspect


def frames(n: int, open_at: set[int]) -> list[bool]:
    """Open verdicts for frames 1..n."""
    return [k in open_at for k in range(1, n + 1)]


# Every frame open
def test_every_frame_open():
    assert is_suspect(frames(41, set(range(1, 42))), "setup")


# Open at both ends
def test_open_at_both_ends():
    assert is_suspect(frames(40, {1, 2, 3, 38, 39, 40}), "setup")


# Normal opening
def test_normal_opening():
    assert not is_suspect(frames(54, set(range(18, 27))), "setup")


# Long opening that starts closed
def test_long_opening_that_starts_closed():
    assert is_suspect(frames(100, set(range(9, 101))), "setup")


def test_just_under_ninety_percent_open():
    assert not is_suspect(frames(100, set(range(12, 101))), "setup")  # 89% open, ends open


# Short clip
def test_short_clip():
    assert not is_suspect(frames(8, set(range(1, 9))), "setup")


# Default rules
def test_default_rules():
    assert not is_suspect(frames(41, set(range(1, 42))), "default")


# Tuned rules
def test_tuned_rules():
    assert is_suspect(frames(41, set(range(1, 42))), "tuned")
