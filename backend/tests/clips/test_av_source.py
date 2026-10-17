"""door-clip-evaluation: decoding clips with PyAV (skipped without `uv sync --group clips`)."""

import pytest

from tests.clips.harness import AvSource, ClipUnreadable

pytest.importorskip("av", reason="run `uv sync --group clips` to install the video decoder")


# Unreadable clip
def test_unreadable_clip(tmp_path):
    clip = tmp_path / "Ring_Fridge_20261015_1920.mp4"
    clip.write_text("not a video")
    with pytest.raises(ClipUnreadable, match="Ring_Fridge_20261015_1920.mp4"):
        AvSource(clip)
