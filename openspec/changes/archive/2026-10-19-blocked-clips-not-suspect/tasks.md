# Tasks

## 1. Zone looks closed

- [x] 1.1 Write failing unit tests in `backend/tests/test_blocked_clips.py` for "Person in front of the zones at both bookends", "Wrong rules on a clear view", "One bookend clear is enough to count", "Two zones, only the open one is checked", "Shift applied to the zone box", "Suspect by share alone" and "Recorded clip with the owner in front", against a pure `is_blocked(anchor, check, first, last, first_open_zones, last_open_zones)`-style helper
- [x] 1.2 Implement the helper in `backend/src/fridgesense/door_events.py` (`ZONE_CLOSED_MAX_DIFF = 0.05`) to make them pass

## 2. Streak and log

- [x] 2.1 Write failing integration tests in `backend/tests/test_fetch_stills_clip.py`: a blocked suspect clip leaves `suspect_streak` at 2 and logs `door_check_blocked` while still re-scoring with the fridge light and returning `suspect = true`; a clear-view miscalibrated clip still adds 1; "No anchor stored" still adds 1
- [x] 2.2 Wire the helper into `fetch_stills` so `_count_suspect` is skipped for blocked clips, and log `door_check_blocked`

## 3. Finish

- [x] 3.1 Run `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` in `backend/`; all green
- [x] 3.2 Merge into `local` (test the merge first), and deploy with Jayson's OK
- [x] 3.3 With Jayson's OK, reset `suspect_streak` to 0 on the prod `ALIGN#` item and confirm the warnings list no `door_setup_mismatch`
