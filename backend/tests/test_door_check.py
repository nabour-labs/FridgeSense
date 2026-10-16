"""door-event-detection: still timing and the door-open check."""

import pytest

from fridgesense.door_events import (
    DoorCheck,
    ZoneRule,
    baseline_of,
    measure,
    still_times,
)
from tests.conftest import color_jpeg

HALVES = ((0.0, 0.0, 0.5, 1.0), (0.5, 0.0, 0.5, 1.0))
GREY = (128, 128, 128)
FRIDGE_BLUE = (40, 90, 200)


def test_still_times_spread_across_window():
    assert still_times(1786715596000, 1786715621000) == [
        1786715601000,
        1786715606000,
        1786715611000,
        1786715616000,
    ]


# Fridge light visible
def test_fridge_light_visible():
    # 10% of the left zone (100x100 px): a 20x50 px block
    still = color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), FRIDGE_BLUE)], size=(200, 100))
    check = DoorCheck(zones=HALVES, threshold=0.02)
    open_, score, zone = check.evaluate([color_jpeg(GREY, size=(200, 100)), still])
    assert open_ is True
    assert score == pytest.approx(0.10, abs=0.01)
    assert zone == 1


# Drawer opening seen only in the drawers zone
def test_drawer_opening_seen_only_in_drawers_zone():
    # 5% of the right zone: a 10x50 px block
    still = color_jpeg(GREY, [((0.7, 0.25, 0.05, 0.5), FRIDGE_BLUE)], size=(200, 100))
    open_, score, zone = DoorCheck(zones=HALVES, threshold=0.02).evaluate([still])
    assert open_ is True
    assert score == pytest.approx(0.05, abs=0.01)
    assert zone == 2


# Brightness alone does not count
@pytest.mark.parametrize("level", [(230, 230, 230), (30, 30, 30)])
def test_brightness_alone_does_not_count(level):
    open_, score, _ = DoorCheck(zones=HALVES, threshold=0.02).evaluate([color_jpeg(level)])
    assert open_ is False
    assert score == 0


# Dark colored clothing does not count
def test_dark_colored_clothing_does_not_count():
    navy = color_jpeg(GREY, [((0.0, 0.0, 0.5, 1.0), (20, 25, 60))])
    open_, score, _ = DoorCheck(zones=HALVES, threshold=0.02).evaluate([navy])
    assert open_ is False
    assert score == 0


# Threshold is inclusive
def test_threshold_is_inclusive():
    still = color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), FRIDGE_BLUE)], size=(200, 100))
    level = measure(still, HALVES[0], "blue")
    assert DoorCheck(zones=HALVES, threshold=level).evaluate([still])[0] is True


# Box and threshold from config
def test_zones_and_threshold_from_config():
    still = color_jpeg(GREY, [((0.6, 0.0, 0.4, 1.0), FRIDGE_BLUE)])
    right = DoorCheck.from_config("0.6,0.0,0.4,1.0", "0.02")
    left = DoorCheck.from_config("0.0,0.0,0.4,1.0", "0.02")
    assert right.evaluate([still])[0] is True
    assert left.evaluate([still])[0] is False


def test_several_zones_from_config():
    check = DoorCheck.from_config("0,0,0.5,1; 0.5,0,0.5,1", "0.1")
    assert check.zones == HALVES
    assert check.threshold == 0.1


def test_config_defaults():
    default = DoorCheck.from_config(None, None)
    assert default.zones == ((0.38, 0.32, 0.21, 0.30), (0.455, 0.60, 0.12, 0.18))
    assert default.threshold == 0.01


# Invalid zone config
@pytest.mark.parametrize("zones", ["0.9,0,0.5,1", "0,0,1", ";", "0,0,1,1;0,0,1"])
def test_invalid_zone_config(zones):
    with pytest.raises(ValueError, match="DOOR_ZONES"):
        DoorCheck.from_config(zones, "0.02")


# Features measured in a zone: color, brightness and change (shared by setup and the check)
WHOLE = (0.0, 0.0, 1.0, 1.0)
HALVES_DARK_LIGHT = [((0.0, 0.0, 0.5, 1.0), (40, 40, 40)), ((0.5, 0.0, 0.5, 1.0), (216, 216, 216))]


def test_measure_color():
    still = color_jpeg(GREY, [((0.1, 0.25, 0.1, 0.5), FRIDGE_BLUE)], size=(200, 100))
    assert measure(still, (0.0, 0.0, 0.5, 1.0), "color") == pytest.approx(0.10, abs=0.01)


# Blue-lit colour: the fridge's LED-lit interior, not warm food held in front of it
PLATE, PACKET, NAVY = (220, 170, 40), (200, 40, 40), (20, 25, 60)


def test_measure_blue_counts_the_lit_interior():
    still = color_jpeg(GREY, [((0.0, 0.0, 0.1, 1.0), FRIDGE_BLUE)])
    assert measure(still, WHOLE, "blue") == pytest.approx(0.10, abs=0.01)


@pytest.mark.parametrize(
    "fill, block",
    [(GREY, PLATE), (GREY, PACKET), (GREY, NAVY), ((230, 230, 230), None), ((30, 30, 30), None)],
)
def test_measure_blue_ignores_warm_dark_and_grey(fill, block):
    still = color_jpeg(fill, [((0.0, 0.0, 0.1, 1.0), block)] if block else [])
    assert measure(still, WHOLE, "blue") == pytest.approx(0.0, abs=0.002)


def test_measure_color_still_counts_warm_food():
    still = color_jpeg(GREY, [((0.0, 0.0, 0.1, 1.0), PLATE)])
    assert measure(still, WHOLE, "color") == pytest.approx(0.10, abs=0.01)


def test_measure_brightness():
    assert measure(color_jpeg((200, 200, 200)), WHOLE, "brightness") == pytest.approx(
        200 / 255, abs=0.01
    )
    assert measure(color_jpeg((0, 0, 0)), WHOLE, "brightness") == pytest.approx(0.0, abs=0.01)


def test_measure_change_against_baseline():
    baseline = baseline_of([color_jpeg(GREY)], WHOLE)
    assert len(baseline) == 32 * 32 * 3
    assert measure(color_jpeg(GREY), WHOLE, "change", baseline) == pytest.approx(0.0, abs=0.01)
    halves = color_jpeg(GREY, HALVES_DARK_LIGHT)
    assert measure(halves, WHOLE, "change", baseline) == pytest.approx(88 / 255, abs=0.02)


def test_baseline_is_the_mean_of_closed_references():
    baseline = baseline_of([color_jpeg((100, 100, 100)), color_jpeg((200, 200, 200))], WHOLE)
    assert measure(color_jpeg((150, 150, 150)), WHOLE, "change", baseline) == pytest.approx(
        0.0, abs=0.01
    )


def test_rule_above_is_inclusive():
    rule = ZoneRule(WHOLE, "brightness", "above", 0.6)
    assert rule.is_open(0.6) and rule.is_open(0.9) and not rule.is_open(0.59)


def test_rule_below_is_inclusive():
    rule = ZoneRule(WHOLE, "brightness", "below", 0.5)
    assert rule.is_open(0.5) and rule.is_open(0.1) and not rule.is_open(0.51)


def test_config_builds_blue_rules():
    check = DoorCheck.from_config("0,0,0.5,1;0.5,0,0.5,1", "0.03")
    assert [(r.box, r.feature, r.direction, r.threshold) for r in check.rules] == [
        ((0.0, 0.0, 0.5, 1.0), "blue", "above", 0.03),
        ((0.5, 0.0, 0.5, 1.0), "blue", "above", 0.03),
    ]


def test_per_still_results():
    open_still = color_jpeg(GREY, [((0.6, 0.0, 0.4, 1.0), FRIDGE_BLUE)])
    check = DoorCheck(zones=HALVES, threshold=0.02)
    results = check.results([color_jpeg(GREY), open_still])
    assert [r.is_open for r in results] == [False, True]
    assert results[1].zone == 2
    assert results[1].feature == "blue"
    assert results[1].value == pytest.approx(0.8, abs=0.02)


def test_brightness_rule_check():
    check = DoorCheck(rules=(ZoneRule(WHOLE, "brightness", "above", 0.6),))
    assert check.evaluate([color_jpeg((200, 200, 200))])[0] is True
    assert check.evaluate([color_jpeg((100, 100, 100))])[0] is False


def test_darker_rule_check():
    check = DoorCheck(rules=(ZoneRule(WHOLE, "brightness", "below", 0.5),))
    assert check.evaluate([color_jpeg((90, 90, 90))])[0] is True


def test_change_rule_check():
    baseline = baseline_of([color_jpeg(GREY)], WHOLE)
    check = DoorCheck(rules=(ZoneRule(WHOLE, "change", "above", 0.2, baseline),))
    assert check.evaluate([color_jpeg(GREY, HALVES_DARK_LIGHT)])[0] is True
    assert check.evaluate([color_jpeg((130, 130, 130))])[0] is False


# pipeline-debug-traces: Two zones scored
def test_zone_values_scores_every_zone():
    still = color_jpeg(GREY, [((0.6, 0.0, 0.2, 0.5), FRIDGE_BLUE)], size=(200, 100))
    values = DoorCheck(zones=HALVES, threshold=0.02).zone_values(still)
    assert [(v.zone, v.threshold, v.open) for v in values] == [(1, 0.02, False), (2, 0.02, True)]
    assert values[0].value == 0
    assert values[1].value == pytest.approx(0.2, abs=0.02)


# pipeline-debug-traces: Below-direction rule
def test_zone_values_below_direction_rule():
    check = DoorCheck(rules=(ZoneRule(WHOLE, "brightness", "below", 0.4),))
    [value] = check.zone_values(color_jpeg((89, 89, 89)))
    assert value.value == pytest.approx(0.35, abs=0.01)
    assert value.open is True


def test_zone_values_threshold_is_inclusive():
    check = DoorCheck(rules=(ZoneRule(WHOLE, "brightness", "above", 0.5),))
    [value] = check.zone_values(color_jpeg((128, 128, 128)))
    rule = ZoneRule(WHOLE, "brightness", "above", value.value)
    assert DoorCheck(rules=(rule,)).zone_values(color_jpeg((128, 128, 128)))[0].open is True


def test_result_matches_best_zone_value():
    still = color_jpeg(GREY, [((0.6, 0.0, 0.2, 0.5), FRIDGE_BLUE)], size=(200, 100))
    check = DoorCheck(zones=HALVES, threshold=0.02)
    best = max(check.zone_values(still), key=lambda v: v.value)
    result = check.result(still)
    assert (result.zone, result.value, result.is_open) == (best.zone, best.value, best.open)


# Food in front of closed doors
@pytest.mark.parametrize("food", [PLATE, PACKET])
def test_food_in_front_of_closed_doors(food):
    still = color_jpeg(GREY, [((0.2, 0.2, 0.2, 0.5), food)])
    open_, score, _ = DoorCheck.from_config("0,0,1,1", None).evaluate([still])
    assert open_ is False
    assert score == pytest.approx(0.0, abs=0.002)


# Faint fridge light counts at the default threshold
def test_faint_fridge_light_counts_at_the_default_threshold():
    # 1.5% of a 400x200 still: a 6 px wide, full-height block
    still = color_jpeg(GREY, [((0.5, 0.0, 0.015, 1.0), FRIDGE_BLUE)], size=(400, 200))
    open_, score, _ = DoorCheck.from_config("0,0,1,1", None).evaluate([still])
    assert score == pytest.approx(0.015, abs=0.003)
    assert open_ is True
