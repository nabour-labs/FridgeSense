# Design

## Context

`clip_frames.download_clip` posts `media/video/download`, follows the 303 `Location` and streams it. `NOT_READY = {416, 425}` from either step repeats the whole request after each of `CLIP_RETRY_DELAYS_S = (3, 6)`. Any other status raises `ClipUnavailable("status_<code>")`, and `door_events` logs `clip_unavailable` and falls back to stills.

Prod logs since 2026-10-17: 5 `status_206`, no other `clip_unavailable` reason. They came 8–10 s after the motion's end, so a third, longer wait gives Ring more time.

## Decisions

- **206 is "not ready".** The body of a 206 is only part of the file and would decode as a cut clip at best. Retrying keeps the existing all-or-nothing behavior.
- **Delays (3, 6, 12).** 21 s of waiting at most. The pipeline Lambda has a 150 s timeout, and a normal run takes about 12 s.
- **Where it failed.** `ClipUnavailable` carries `stage` and, for link answers, `content_range` and `content_length`. `door_events` logs those fields. This is enough to tell Ring which call answers 206 and with what range. Headers are not secrets: the pre-signed link itself is never logged.
- The still `NOT_READY` set in `door_events` stays as it is.

## Test strategy

- Unit (`backend/tests/test_clip_download.py`, respx): 206 on the request then the clip; 206 on the link then the clip; 206 every time gives `status_206` after 4 attempts with sleeps `[3, 6, 12]`; the reason carries `stage` and the link's headers. Existing never-ready tests updated to 4 attempts.
- Unit (`backend/tests/test_fetch_stills_clip.py`): the `clip_unavailable` log line includes `stage` (and the headers when given).
- No live Ring calls; all responses canned.

## Risks

- If Ring keeps answering 206 for a whole clip, each such event waits 21 s before stills. Acceptable.
