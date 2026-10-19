"""analysis-evaluation: recorded answers and the direction-aware score."""

import json

from tests.analysis_eval.harness import (
    LabelItem,
    OpeningLabel,
    Score,
    load_run,
    score_opening,
    score_run,
)


def label(added=(), removed=()) -> OpeningLabel:
    item = lambda x: x if isinstance(x, LabelItem) else LabelItem(x, 1)  # noqa: E731
    return OpeningLabel(added=[item(a) for a in added], removed=[item(r) for r in removed])


def old(added=(), removed=()) -> dict:
    change = lambda n: {"item": n, "category": "other", "quantity": 1, "confidence": 0.9}  # noqa: E731
    return {"added": [change(a) for a in added], "removed": [change(r) for r in removed]}


# Perfect opening
def test_perfect_opening():
    assert score_opening(label(added=["soda can"]), old(added=["Soda  Can"])) == Score(1, 0, 0, 0)


# Inventory echo
def test_inventory_echo():
    answer = old(added=["soda can", "milk", "eggs"], removed=["bread"])
    assert score_opening(label(added=["soda can"]), answer) == Score(1, 3, 0, 0)


# Direction flipped
def test_direction_flipped():
    assert score_opening(label(removed=["soda can"]), old(added=["soda can"])) == Score(0, 1, 1, 1)


# Alias matches
def test_alias_matches():
    lbl = label(removed=[LabelItem("chocolate milk", 1, ("chocomilk",))])
    assert score_opening(lbl, old(removed=["chocomilk"])) == Score(1, 0, 0, 0)


def test_each_label_matched_once():
    answer = old(added=["bottle", "bottle"])
    assert score_opening(label(added=["bottle"]), answer) == Score(1, 1, 0, 0)


# Totals
def test_totals():
    labels = {"1": label(added=["a", "b"]), "2": label(added=["c", "d"], removed=["e"])}
    answers = {"1": old(added=["a", "x"]), "2": old(added=["c", "d"])}
    report = score_run(labels, answers)
    assert (report.total.tp, report.total.fp, report.total.fn) == (3, 1, 2)
    assert report.precision == 0.75
    assert report.recall == 0.6


# Nothing predicted and nothing labelled
def test_nothing_predicted_and_nothing_labelled():
    report = score_run({"1": label(), "2": label()}, {"1": old(), "2": old()})
    assert report.precision is None
    assert report.recall is None


# Baseline answers in the old shape
def test_baseline_answers_in_old_shape(tmp_path):
    (tmp_path / "1792368091888.json").write_text(
        json.dumps(old(added=["milk"], removed=["soda can"]))
    )
    answers = load_run(tmp_path)
    lbl = label(added=["milk"], removed=["soda can"])
    assert score_opening(lbl, answers["1792368091888"]) == Score(2, 0, 0, 0)


# Missing answer
def test_missing_answer():
    report = score_run({"1": label(added=["milk"]), "2": label()}, {"2": old()})
    assert report.per_opening["1"] == Score(0, 0, 1, 0)
    assert report.missing == ["1"]


# New answers in the evidence shape
def test_new_answers_in_the_evidence_shape():
    def it(name, going_in, coming_out):
        return {
            "item": name,
            "category": "other",
            "quantity": 1,
            "confidence": 0.9,
            "going_in": going_in,
            "coming_out": coming_out,
        }

    answer = {
        "observations": "x",
        "items": [it("eggs", False, True), it("milk", False, False), it("can", True, True)],
    }
    assert score_opening(label(removed=["eggs"]), answer) == Score(1, 0, 0, 0)


# Skipped openings left out of the totals
def test_skipped_openings_left_out_of_the_totals():
    labels = {
        "1": label(added=["a"]),
        "2": label(),
        "3": label(removed=["b"]),
        "4": OpeningLabel(added=[], removed=[], skip="can't see the item"),
    }
    answers = {"1": old(added=["a"]), "2": old(), "3": old(removed=["b"]), "4": old(added=["x"])}
    report = score_run(labels, answers)
    assert (report.total.tp, report.total.fp, report.total.fn) == (2, 0, 0)
    assert report.skipped == {"4": "can't see the item"}
    assert "4" not in report.per_opening
