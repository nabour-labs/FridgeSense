"""analysis-evaluation: the opening labels fixture."""

import json

import pytest

from tests.analysis_eval.harness import LabelError, LabelItem, OpeningLabel, load_labels


def write(tmp_path, openings: dict):
    path = tmp_path / "labels.json"
    path.write_text(json.dumps({"openings": openings}))
    return path


# Valid labels load
def test_valid_labels_load(tmp_path):
    entry = {
        "added": [],
        "removed": [{"item": "chocolate milk", "quantity": 1, "also": ["chocomilk"]}],
    }
    labels = load_labels(write(tmp_path, {"1790000000000": entry}))
    assert labels == {
        "1790000000000": OpeningLabel(
            added=[], removed=[LabelItem("chocolate milk", 1, ("chocomilk",))]
        )
    }


# Nothing moved
def test_nothing_moved(tmp_path):
    labels = load_labels(write(tmp_path, {"1790000000000": {"added": [], "removed": []}}))
    assert labels["1790000000000"] == OpeningLabel(added=[], removed=[])


# Bad quantity
@pytest.mark.parametrize(
    "item, field",
    [({"item": "milk", "quantity": 0}, "quantity"), ({"quantity": 1}, "item")],
)
def test_bad_quantity(tmp_path, item, field):
    with pytest.raises(LabelError, match=rf"1790000000000.*{field}"):
        load_labels(write(tmp_path, {"1790000000000": {"added": [item], "removed": []}}))


def test_missing_list_rejected(tmp_path):
    with pytest.raises(LabelError, match=r"1790000000000.*removed"):
        load_labels(write(tmp_path, {"1790000000000": {"added": []}}))
