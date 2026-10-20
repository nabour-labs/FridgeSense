# Tasks

## 1. Retry 206 and longer delays

- [x] 1.1 Write failing tests in `backend/tests/test_clip_download.py` for "Clip not ready yet" with 206 on the request and on the link, and for "Clip never ready" (206 every time, 4 attempts, sleeps 3, 6, 12); update the 416/425 never-ready tests to 4 attempts
- [x] 1.2 Add 206 to the clip's not-ready set and set `CLIP_RETRY_DELAYS_S = (3, 6, 12)` to make them pass

## 2. Say where the clip failed

- [x] 2.1 Write failing tests for "Failure stage logged" (request: `stage = "request"`; link: `stage = "link"` with `content_range` and `content_length`)
- [x] 2.2 Carry `stage`, `content_range` and `content_length` on `ClipUnavailable` and log them with `clip_unavailable`

## 3. Wrap up

- [x] 3.1 Add the 206 entry to `docs/friction-log.md`
- [x] 3.2 Run `uv run pytest` and `uv run ruff check` in `backend/`, all green
