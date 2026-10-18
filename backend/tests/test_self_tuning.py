"""door-self-calibration: event samples from recent activity, and rules re-tuned from them."""

import pytest

from fridgesense import door_calibration as dc
from fridgesense import self_tuning
from fridgesense.alignment import Alignment
from fridgesense.door_events import DoorCheck, ZoneRule, measure
from fridgesense.table import FridgeTable
from tests.conftest import color_jpeg

ACCOUNT = "ava1.ring.account.A1"
DEVICE = "ava1.ring.device.D1"
T0 = 1792092000000
GREY = (128, 128, 128)
BLUE = (40, 90, 200)
RED = (200, 60, 40)
LEFT_BOX = (0.0, 0.0, 0.5, 1.0)
LEFT = {"x": 0, "y": 0, "width": 0.5, "height": 1}
ALIGNED = Alignment(True, 0.0, 0.0, 0.01, "last")
CHECK = DoorCheck(rules=(ZoneRule(LEFT_BOX, "blue", "above", 0.05),), source="setup")


def block(share: float, colour=BLUE) -> bytes:
    """A grey 200x100 still with a `colour` block covering `share` of the left half."""
    return color_jpeg(GREY, [((0.05, 0.25, share, 0.5), colour)], size=(200, 100))


CLOSED = color_jpeg(GREY, size=(200, 100))


def learn(frames, aligned=ALIGNED, check=CHECK, at=T0):
    return self_tuning.learn(FridgeTable(), ACCOUNT, DEVICE, check, frames, aligned, at)


def samples():
    return self_tuning.list_samples(FridgeTable(), ACCOUNT, DEVICE)


# Opening sampled
def test_opening_sampled(aws):
    lit = block(0.4)
    frames = [CLOSED, CLOSED, block(0.1), CLOSED, CLOSED, lit, block(0.2), CLOSED]
    assert learn(frames)
    [event] = samples()
    [zone] = event.zones
    assert zone.closed is not None and zone.open is not None
    assert zone.open.blue == pytest.approx(measure(lit, LEFT_BOX, "blue"), abs=0.001)
    assert zone.open.color == pytest.approx(measure(lit, LEFT_BOX, "color"), abs=0.001)
    assert zone.closed.blue == pytest.approx(0.0, abs=0.001)
    assert len(zone.closed.thumb) == 32 * 32 * 3


# Missed opening still sampled
def test_missed_opening_still_sampled(aws):
    strict = DoorCheck(rules=(ZoneRule(LEFT_BOX, "blue", "above", 0.9),), source="setup")
    learn([CLOSED, block(0.4), CLOSED], check=strict)
    [zone] = samples()[0].zones
    assert zone.open is not None


# No clear opening
def test_no_clear_opening(aws):
    learn([CLOSED, block(0.02, (130, 130, 130)), CLOSED])
    [zone] = samples()[0].zones
    assert zone.closed is not None
    assert zone.open is None


# Bookend not closed
def test_bookend_not_closed(aws):
    learn([CLOSED, CLOSED, block(0.4)])  # the "last" bookend is open
    [zone] = samples()[0].zones
    assert zone.closed is None
    assert zone.open is None


def test_first_bookend_used(aws):
    learn([CLOSED, block(0.4), block(0.4)], aligned=Alignment(True, 0, 0, 0.01, "first"))
    [zone] = samples()[0].zones
    assert zone.closed is not None and zone.open is not None


# Oldest dropped
def test_oldest_dropped(aws):
    for k in range(21):
        learn([CLOSED, block(0.4), CLOSED], at=T0 + k)
    kept = samples()
    assert len(kept) == 20
    assert min(s.at_ms for s in kept) == T0 + 1


# Unaligned event not sampled
@pytest.mark.parametrize("aligned", [None, Alignment(False, 0, 0, 0.2, "first")])
def test_unaligned_event_not_sampled(aws, aligned):
    assert not learn([CLOSED, block(0.4), CLOSED], aligned=aligned)
    assert samples() == []


def test_sample_uses_the_shifted_zone(aws):
    """Measured where the zone is now: the check passed in is already shifted."""
    right = DoorCheck(rules=(ZoneRule((0.5, 0.0, 0.5, 1.0), "blue", "above", 0.05),))
    learn([CLOSED, block(0.4), CLOSED], check=right)  # the lit block is in the left half
    [zone] = samples()[0].zones
    assert zone.open is None


# --- Rules re-tuned from samples ---


def set_up():
    table = FridgeTable()
    z = dc.add_zone(table, ACCOUNT, DEVICE, "Doors", LEFT, T0).sk
    dc.add_reference(table, ACCOUNT, DEVICE, block(0.06), z, "open", T0)
    dc.add_reference(table, ACCOUNT, DEVICE, CLOSED, z, "closed", T0 + 1)
    dc.run(table, ACCOUNT, DEVICE, T0 + 2)


def retune(at=T0 + 100):
    return self_tuning.retune(FridgeTable(), ACCOUNT, DEVICE, at)


def check():
    return dc.setup_check(FridgeTable(), ACCOUNT, DEVICE)


# Tuned rules adopted
def test_tuned_rules_adopted(aws):
    set_up()
    for k in range(4):  # openings lit warm, not blue: only color separates them all
        learn([CLOSED, block(0.3, RED), CLOSED], check=check(), at=T0 + 10 + k)
    assert retune(T0 + 100)
    setup = dc.load_setup(FridgeTable(), ACCOUNT, DEVICE)
    assert setup.tuned_from == 8
    assert setup.tuned_at == "2026-10-15T19:20:00.100Z"
    tuned = check()
    assert tuned.source == "tuned"
    [rule] = tuned.rules
    assert (rule.box, rule.feature, rule.direction) == (LEFT_BOX, "color", "above")
    assert rule.margin == pytest.approx(0.06, abs=0.01)


# Samples overlap
def test_samples_overlap(aws):
    set_up()
    for k in range(3):
        learn([CLOSED, block(0.4), CLOSED], check=check(), at=T0 + 10 + k)
    # an "open" sample that looks exactly like a closed one: no feature can separate them
    closed = samples()[0].zones[0].closed
    self_tuning.store_sample(
        FridgeTable(), ACCOUNT, DEVICE, T0 + 20, [self_tuning.ZoneSample(closed, open=closed)]
    )
    assert not retune()
    assert check().source == "setup"


def test_overlap_keeps_previous_tuned_rules(aws):
    set_up()
    for k in range(4):
        learn([CLOSED, block(0.3, RED), CLOSED], check=check(), at=T0 + 10 + k)
    assert retune()
    self_tuning.store_sample(
        FridgeTable(),
        ACCOUNT,
        DEVICE,
        T0 + 50,
        [self_tuning.ZoneSample(closed=samples()[0].zones[0].open, open=None)],
    )  # a "closed" sample that looks open: no feature separates any more
    assert not retune(T0 + 200)
    assert check().source == "tuned"
    assert dc.load_setup(FridgeTable(), ACCOUNT, DEVICE).tuned_at == "2026-10-15T19:20:00.100Z"


# Too few samples
def test_too_few_samples(aws):
    set_up()
    for k in range(2):
        learn([CLOSED, block(0.4), CLOSED], check=check(), at=T0 + 10 + k)
    assert not retune()
    assert dc.load_setup(FridgeTable(), ACCOUNT, DEVICE).tuned_at is None


def test_no_setup_no_retune(aws):
    learn([CLOSED, block(0.4), CLOSED])
    assert not retune()


# Re-running setup resets tuning
def test_rerunning_setup_resets_tuning(aws):
    set_up()
    for k in range(4):
        learn([CLOSED, block(0.3, RED), CLOSED], check=check(), at=T0 + 10 + k)
    assert retune()
    dc.run(FridgeTable(), ACCOUNT, DEVICE, T0 + 300)
    assert check().source == "setup"
    assert samples() == []
    assert dc.load_setup(FridgeTable(), ACCOUNT, DEVICE).tuned_at is None


# Re-tune keeps blue
BRIGHT_LIT = color_jpeg(
    GREY,
    [((0.0, 0.0, 0.5, 1.0), (230, 230, 230)), ((0.05, 0.25, 0.03, 0.5), BLUE)],
    size=(200, 100),
)  # the interior light floods the zone: brightness moves far more than the blue-lit share


def test_retune_keeps_blue(aws):
    table = FridgeTable()
    z = dc.add_zone(table, ACCOUNT, DEVICE, "Doors", LEFT, T0).sk
    dc.add_reference(table, ACCOUNT, DEVICE, BRIGHT_LIT, z, "open", T0)
    dc.add_reference(table, ACCOUNT, DEVICE, CLOSED, z, "closed", T0 + 1)
    dc.run(table, ACCOUNT, DEVICE, T0 + 2)
    for k in range(3):
        learn([CLOSED, BRIGHT_LIT, CLOSED], check=check(), at=T0 + 10 + k)
    assert retune()
    [rule] = check().rules
    assert check().source == "tuned"
    assert rule.feature == "blue"
