"""door-clip-evaluation: the accuracy report and the threshold/interval sweep."""

import importlib.util
import json
from pathlib import Path

import pytest

from tests.clips.harness import ColourSource, Opening, score

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "door_clip_report.py"
GREY, LIT = (128, 128, 128), (40, 90, 200)


@pytest.fixture(scope="module")
def report():
    spec = importlib.util.spec_from_file_location("door_clip_report", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A stand-in repo root with an empty tmp/ clips folder."""
    (tmp_path / "tmp").mkdir()
    monkeypatch.setenv("FRIDGESENSE_CLIPS_DIR", str(tmp_path / "tmp"))
    for name in ("DOOR_ZONES", "DOOR_THRESHOLD", "STILL_INTERVAL_MS"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def write_labels(repo: Path, clips: dict[str, list[dict]]) -> Path:
    path = repo / "labels.json"
    path.write_text(json.dumps({"clips": {c: {"openings": o} for c, o in clips.items()}}))
    for clip in clips:
        (repo / "tmp" / clip).write_bytes(b"")
    return path


def lit_from(start_s: float, end_s: float):
    """open_clip stand-in: every clip is lit from start_s to end_s of 20 s."""
    return lambda path: ColourSource([(0.0, GREY), (start_s, LIT), (end_s, GREY)], 20.0)


# Report over all clips
def test_report_over_all_clips(report):
    results = [
        score("a.mp4", [Opening(5.0, 12.0)], 20.0, (4.6, 12.0), 1.5, 0.4, 0.01),
        score("b.mp4", [Opening(3.0, 9.0)], 20.0, None, 1.5, 0.004, 0.01),
        score("c.mp4", [], 20.0, None, 1.5, 0.0, 0.01),
    ]
    text = "\n".join(report.summary_lines(results))
    assert "TP 1  FP 0  FN 1  TN 1" in text
    assert "open error   mean 0.40 s  max 0.40 s" in text
    assert "close error  mean 0.00 s  max 0.00 s" in text


def test_report_rows_per_clip(report, repo, capsys):
    labels = write_labels(
        repo,
        {
            "Ring_Fridge_20261015_1920.mp4": [{"opened_s": 4.0, "closed_s": 12.5}],
            "Ring_Fridge_20261015_1934.mp4": [],
        },
    )
    code = report.main([], repo=repo, open_clip=lit_from(4.0, 12.5), labels=labels)
    out = capsys.readouterr().out
    assert code == 0
    assert "Ring_Fridge_20261015_1920.mp4" in out and "Ring_Fridge_20261015_1934.mp4" in out
    assert "TP 1  FP 1  FN 0  TN 0" in out  # the second clip is lit too: a false opening


def test_report_exits_zero_on_bad_accuracy(report, repo, capsys):
    labels = write_labels(repo, {"x.mp4": [{"opened_s": 4.0, "closed_s": 12.5}]})
    code = report.main([], repo=repo, open_clip=lit_from(30.0, 31.0), labels=labels)
    assert code == 0
    assert "TP 0  FP 0  FN 1  TN 0" in capsys.readouterr().out


def test_merged_openings_flagged(report, repo, capsys):
    labels = write_labels(
        repo, {"m.mp4": [{"opened_s": 2.0, "closed_s": 6.0}, {"opened_s": 9.0, "closed_s": 14.0}]}
    )
    report.main([], repo=repo, open_clip=lit_from(2.0, 14.0), labels=labels)
    assert "merged 2" in capsys.readouterr().out


# No clips present
def test_no_clips_present(report, repo, capsys):
    labels = repo / "labels.json"
    labels.write_text(json.dumps({"clips": {"gone.mp4": {"openings": []}}}))
    code = report.main([], repo=repo, open_clip=lit_from(4.0, 12.5), labels=labels)
    assert code == 0
    assert f"no labelled clips found in {repo / 'tmp'}" in capsys.readouterr().out


# Unlabelled clips listed
def test_unlabelled_clips_listed(report, repo, capsys):
    labels = write_labels(repo, {"a.mp4": []})
    (repo / "tmp" / "Ring_Fridge_20261016_0800.mp4").write_bytes(b"")
    opened = []

    def open_clip(path):
        opened.append(path.name)
        return ColourSource([(0.0, GREY)], 20.0)

    report.main([], repo=repo, open_clip=open_clip, labels=labels)
    out = capsys.readouterr().out
    assert "unlabelled" in out and "Ring_Fridge_20261016_0800.mp4" in out
    assert opened == ["a.mp4"]  # the unlabelled clip is not scored
    assert "TP 0  FP 0  FN 0  TN 1" in out


# Sweep two thresholds and two intervals
def test_sweep_two_thresholds_and_two_intervals(report, repo, capsys):
    labels = write_labels(repo, {"a.mp4": [{"opened_s": 4.0, "closed_s": 12.5}], "b.mp4": []})
    opened = []

    def open_clip(path):
        opened.append(path.name)
        return lit_from(4.0, 12.5)(path) if path.name == "a.mp4" else lit_from(30, 31)(path)

    code = report.main(
        ["--threshold", "0.01,0.03", "--interval", "500,1000"],
        repo=repo,
        open_clip=open_clip,
        labels=labels,
    )
    out = capsys.readouterr().out
    assert code == 0
    rows = [line for line in out.splitlines() if line.startswith("sweep ")]
    assert len(rows) == 4
    for threshold, interval in (("0.01", "500"), ("0.01", "1000"), ("0.03", "500")):
        assert any(f"threshold {threshold}" in r and f"interval {interval}" in r for r in rows)
    assert all("TP 1  FP 0  FN 0  TN 1" in r for r in rows)
    assert sorted(opened) == ["a.mp4", "b.mp4"]  # each clip decoded once


# Bad sweep value
@pytest.mark.parametrize(
    ("args", "option"),
    [
        (["--interval", "0"], "--interval"),
        (["--interval", "500,x"], "--interval"),
        (["--threshold", "abc"], "--threshold"),
        (["--threshold", "-0.1"], "--threshold"),
    ],
)
def test_bad_sweep_value(report, repo, capsys, args, option):
    labels = write_labels(repo, {"a.mp4": []})
    opened = []
    code = report.main(args, repo=repo, open_clip=lambda p: opened.append(p), labels=labels)
    assert code != 0
    assert option in capsys.readouterr().err
    assert opened == []
