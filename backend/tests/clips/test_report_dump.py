"""door-clip-evaluation: dumping sampled stills for labelling (`door_clip_report.py --dump`)."""

import csv
import importlib.util
from pathlib import Path

import pytest

from tests.clips.harness import ColourSource

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "door_clip_report.py"
CLIP = "Ring_Fridge_20261015_1920.mp4"
GREY, LIT = (128, 128, 128), (40, 90, 200)


@pytest.fixture(scope="module")
def report():
    spec = importlib.util.spec_from_file_location("door_clip_report", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A stand-in repo root with one clip in tmp/."""
    (tmp_path / "tmp").mkdir()
    (tmp_path / "tmp" / CLIP).write_bytes(b"")
    monkeypatch.setenv("FRIDGESENSE_CLIPS_DIR", str(tmp_path / "tmp"))
    for name in ("DOOR_ZONES", "DOOR_THRESHOLD", "STILL_INTERVAL_MS"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def source(path):
    return ColourSource([(0.0, GREY), (4.0, LIT), (12.5, GREY)], duration_s=20.0)


# Dump stills
def test_dump_stills(report, repo, capsys):
    code = report.main(["--dump"], repo=repo, open_clip=source, labels=repo / "none.json")
    assert code == 0, capsys.readouterr().err
    out = repo / "tmp" / "clip-stills" / "Ring_Fridge_20261015_1920"
    jpegs = sorted(out.glob("*.jpg"), key=lambda p: int(p.stem))
    assert len(jpegs) == 20  # one per sampled still: 20 s at 1000 ms
    assert int(jpegs[0].stem) == 952 and int(jpegs[-1].stem) == 19047
    with (out / "values.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 20
    assert [r["offset_ms"] for r in rows] == [p.stem for p in jpegs]
    assert {"zone_1", "zone_2", "verdict"} <= rows[0].keys()
    assert rows[0]["verdict"] == "closed"
    assert rows[4]["verdict"] == "open"  # 4.76 s
    assert float(rows[4]["zone_1"]) > 0.5


# Dump outside tmp refused
def test_dump_outside_tmp_refused(report, repo, capsys):
    calls = []
    code = report.main(
        ["--dump", "--dump-dir", "backend/tests/fixtures"],
        repo=repo,
        open_clip=lambda p: calls.append(p),
        labels=repo / "none.json",
    )
    assert code != 0
    assert "stills may only be written under tmp/" in capsys.readouterr().err
    assert calls == []
    assert not (repo / "backend").exists()
