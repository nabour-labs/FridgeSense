"""door-clip-evaluation: the door check on each labelled local recording.

Local only: `uv sync --group clips`, clips in tmp/ (or FRIDGESENSE_CLIPS_DIR), then
`uv run pytest -m clips`. Without the clips or the decoder these tests skip.
"""

import pytest

from tests.clips.harness import AvSource, clip_cases, clips_dir, evaluate_clip


@pytest.mark.clips
@pytest.mark.parametrize(("clip", "openings"), clip_cases())
def test_door_check_on_clip(clip, openings):
    result = evaluate_clip(clip, AvSource(clips_dir() / clip), openings)
    assert result.passed, "\n".join(result.failures)
