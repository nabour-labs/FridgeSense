"""door-clip-evaluation: clip videos are read from the local clips folder and stay out of git."""

import subprocess

from tests.clips.harness import REPO, clips_dir

CLIP = "Ring_Fridge_20261015_1920.mp4"


# Clips folder from the environment
def test_clips_folder_from_the_environment(monkeypatch, tmp_path):
    (tmp_path / CLIP).write_bytes(b"")
    monkeypatch.setenv("FRIDGESENSE_CLIPS_DIR", str(tmp_path))
    assert clips_dir() == tmp_path
    assert (clips_dir() / CLIP).exists()


def test_clips_folder_defaults_to_repo_tmp(monkeypatch):
    monkeypatch.delenv("FRIDGESENSE_CLIPS_DIR", raising=False)
    assert clips_dir() == REPO / "tmp"


# Videos ignored by git
def test_videos_ignored_by_git():
    out = subprocess.run(
        ["git", "check-ignore", "--no-index", f"tmp/{CLIP}"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == f"tmp/{CLIP}"
