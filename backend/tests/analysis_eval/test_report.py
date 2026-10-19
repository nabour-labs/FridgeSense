"""analysis-evaluation: the eval report command."""

import importlib.util
import json
import socket
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "analysis_eval.py"


@pytest.fixture(scope="module")
def report():
    spec = importlib.util.spec_from_file_location("analysis_eval", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def change(name: str) -> dict:
    return {"item": name, "category": "other", "quantity": 1, "confidence": 0.9}


@pytest.fixture
def fixtures(tmp_path) -> Path:
    """labels.json for 2 openings, a `baseline` run that echoes, a `v1` run that is right."""
    labels = {
        "1": {"added": [{"item": "milk", "quantity": 1}], "removed": []},
        "2": {"added": [], "removed": [{"item": "eggs", "quantity": 2}]},
    }
    (tmp_path / "labels.json").write_text(json.dumps({"openings": labels}))
    runs = {
        "baseline": {
            "1": {"added": [change("milk"), change("bread")], "removed": []},
            "2": {"added": [change("eggs")], "removed": []},
        },
        "v1": {
            "1": {"added": [change("milk")], "removed": []},
            "2": {"added": [], "removed": [change("eggs")]},
        },
    }
    for run, answers in runs.items():
        (tmp_path / run).mkdir()
        for key, answer in answers.items():
            (tmp_path / run / f"{key}.json").write_text(json.dumps(answer))
    return tmp_path


# Compare baseline with a new run
def test_compare_baseline_with_new_run(report, fixtures, capsys):
    assert report.main(["--run", "baseline,v1"], fixtures=fixtures) == 0
    out = capsys.readouterr().out
    baseline, v1 = out.split("== v1 ==")
    assert "== baseline ==" in baseline
    assert "TOTAL  TP 1  FP 2  FN 1  dir 1  precision 0.333  recall 0.5" in baseline
    assert "TOTAL  TP 2  FP 0  FN 0  dir 0  precision 1.0  recall 1.0" in v1
    assert "1  TP 1  FP 1  FN 0  dir 0" in baseline


def test_unknown_run(report, fixtures, capsys):
    assert report.main(["--run", "nope"], fixtures=fixtures) == 2
    assert "nope" in capsys.readouterr().err


def test_missing_answer_listed(report, fixtures, capsys):
    (fixtures / "v1" / "2.json").unlink()
    report.main(["--run", "v1"], fixtures=fixtures)
    assert "missing answers: 2" in capsys.readouterr().out


# Offline by default
def test_offline_by_default(report, fixtures, monkeypatch, capsys):
    def refuse(*args, **kwargs):
        raise AssertionError("network call attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    assert report.main(["--run", "baseline"], fixtures=fixtures) == 0
    assert "TOTAL" in capsys.readouterr().out
