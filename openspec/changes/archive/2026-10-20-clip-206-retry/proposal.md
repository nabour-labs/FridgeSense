# Proposal

## Why

On 2026-10-20 both door openings (09:33 and 09:42 UTC) logged `{"event": "clip_unavailable", "reason": "status_206"}`. The clip download only retries 416 and 425, so a 206 dropped straight to still sampling. Neither opening stored `clip.mp4` or `analysis.mp4`. Nova got 4 stills (3,671 input tokens, against 5–9k for the video), recorded a soda can from one blurry still and missed the second opening's item, and the app showed stills instead of a clip.

Since 2026-10-17, 5 of about 120 openings hit this (Oct 17 ×2, Oct 19 ×1, Oct 20 ×2), each logged 8–10 s after the motion ended. That points to footage that isn't fully ready yet. The log doesn't say whether the 206 came from the clip request or from the `Location` link, or which range it covered.

Track: **Ring** (clip download from the Ring Partner API).

## What Changes

- A 206 from the clip request or from the `Location` link is treated like 416/425: the whole request is repeated.
- Clip retry delays go from 3 s and 6 s to 3 s, 6 s and 12 s (up to 4 attempts, at most 21 s of waiting, well inside the 150 s pipeline timeout).
- `clip_unavailable` gains `stage` (`request` or `link`). For a link answer it also logs the `Content-Range` and `Content-Length` headers, when present.

## Out of scope

- Using a partial (206) body as the clip.
- Re-analyzing the two openings from 2026-10-20 (their footage is no longer worth fetching, and runs are not replayed).
- Still retries (`media/image/download`) keep their own delays and statuses.
