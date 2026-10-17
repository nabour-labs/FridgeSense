"""door-clip-evaluation: which clip tests run, and why the others skip."""

import json
import subprocess
import sys
from pathlib import Path

from tests.clips.harness import clip_cases

BACKEND = Path(__file__).resolve().parents[2]
A = "Ring_Fridge_20261015_1920.mp4"
B = "Ring_Fridge_20261015_2025.mp4"


def labels(tmp_path, *clips) -> Path:
    path = tmp_path / "door_labels.json"
    path.write_text(json.dumps({"clips": {c: {"openings": []} for c in clips}}))
    return path


def skip_reason(case) -> str | None:
    reasons = [m.kwargs["reason"] for m in case.marks if m.name == "skip"]
    return reasons[0] if reasons else None


def clips_folder(tmp_path, *clips) -> Path:
    folder = tmp_path / "clips"
    folder.mkdir()
    for c in clips:
        (folder / c).write_bytes(b"")
    return folder


# One labelled clip missing
def test_one_labelled_clip_missing(tmp_path):
    cases = clip_cases(labels(tmp_path, A, B), clips_folder(tmp_path, A), have_decoder=True)
    reasons = {c.id: skip_reason(c) for c in cases}
    assert reasons[A] is None
    assert B in reasons[B] and "not in" in reasons[B]


# Decoder not installed
def test_decoder_not_installed(tmp_path):
    cases = clip_cases(labels(tmp_path, A, B), clips_folder(tmp_path, A, B), have_decoder=False)
    assert all("uv sync --group clips" in skip_reason(c) for c in cases)


def test_clips_folder_missing(tmp_path):
    [case] = clip_cases(labels(tmp_path, A), tmp_path / "nowhere", have_decoder=True)
    assert "clips folder" in skip_reason(case) and "not found" in skip_reason(case)


def test_unlabelled_clip_is_not_tested(tmp_path):
    cases = clip_cases(labels(tmp_path, A), clips_folder(tmp_path, A, B), have_decoder=True)
    assert [c.id for c in cases] == [A]


def test_no_labels_file(tmp_path):
    [case] = clip_cases(tmp_path / "missing.json", tmp_path, have_decoder=True)
    assert "no labels file" in skip_reason(case)


def pytest_run(*args, env_dir: Path) -> subprocess.CompletedProcess:
    import os

    env = {**os.environ, "FRIDGESENSE_CLIPS_DIR": str(env_dir)}
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
    )


# Fresh checkout or CI
def test_fresh_checkout_or_ci(tmp_path):
    out = pytest_run("tests/clips/test_door_clips.py", "-rs", env_dir=tmp_path / "no-clips")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "skipped" in out.stdout
    assert "passed" not in out.stdout and "failed" not in out.stdout


# Run only the clip tests
def test_run_only_the_clip_tests(tmp_path):
    out = pytest_run("-o", "addopts=", "-m", "clips", "--collect-only", "-q", env_dir=tmp_path)
    collected = [line for line in out.stdout.splitlines() if "::" in line]
    assert collected, out.stdout + out.stderr
    assert all(line.startswith("tests/clips/test_door_clips.py::") for line in collected)
