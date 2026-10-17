# Tasks

## 1. Clip frames as the stored stills

- [x] 1.1 Write failing tests for "Four stills from the open span", "Short open span" and "No Ring still requested" and "Still missing, frame used" in `backend/tests/test_fetch_stills_clip.py` (Ring still endpoint answers a distinct image; stored stills must be the clip frames and the endpoint is never called); verify they fail because Ring stills are requested
- [x] 1.2 Implement: `fetch_stills` stores the picked frames' JPEGs on the clip path and `stills_at` is removed; verify `uv run pytest tests/test_fetch_stills_clip.py` passes
- [x] 1.3 Add a friction-log entry for Ring `at_timestamp` stills not matching the clip frame time; verify the entry follows the template at the top of `docs/friction-log.md`

## 2. Integration

- [x] 2.1 Run the full backend suite and linters green: `uv run pytest` and `uv run ruff check . && uv run ruff format --check .` in `backend/`
