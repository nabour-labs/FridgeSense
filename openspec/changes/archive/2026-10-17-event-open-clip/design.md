# Design

## Context

`fetch_stills` already downloads the Ring event clip to a temp file through `clip_frames.download_clip`, scores frames every 500 ms, and finds the open span (`span`, with `opened_ms` and `closed_ms`). It then deletes the clip, as the current "Clips never stored" rule requires. Stills go to `stills_prefix(account_id, device_id, start_ms)`, a prefix keyed by account and device, in a bucket whose lifecycle deletes objects after 7 days. `GET /api/events` presigns still keys for 15 minutes. The PWA caches still links for 10 minutes so polls don't reload the images. Live video is already limited to `canEdit` roles because it isn't face-blurred.

## Goals / Non-Goals

**Goals:**
- Show only the time the door was open, cheaply, from the clip we already have.
- Never give an unblurred clip to a viewer token.
- A clip that can't be cut or stored never costs us the door event or its analysis.

**Non-Goals:**
- Exact frame cuts, transcoding or changing resolution.
- Fixing the stills-at-offset bug (see proposal).

## Decisions

1. **Remux with PyAV, no re-encode.** Seek to the last keyframe at or before `opened_ms − start_ms`, then copy packets until the first packet past `closed_ms − start_ms` (or the end of the clip) into a new MP4 (`movflags=faststart` so it streams). This is fast, about the cost of reading the file, and needs no encoder. PyAV's wheels may not ship libx264, and re-encoding a 2K clip in a 2048 MB Lambda would add seconds. *Alternative considered:* re-encode for an exact cut. That costs more CPU and depends on which encoder is available, for the sake of trimming up to one GOP. Rejected.

2. **The media fragment hides the lead-in.** A stream-copy cut starts at a keyframe, which can be a moment before the door opened. We store `clip_span = [start_s, end_s]`, the open span's position inside the stored file. The API appends `#t=start_s,end_s` to the presigned link. Browsers start playback at `start_s` and pause at `end_s`, so the user only sees the door open. The fragment is never sent to S3, so the presigned signature stays valid. *Alternative considered:* a separate `clip_start_s` field that the PWA seeks to. That's more client code for the same result.

3. **Cut inside `clip_frames_checked`'s lifetime.** The temp clip is deleted when that function returns, so the cut has to happen while the file still exists. `clip_frames_checked` will return the temp path through a context manager (or a `keep` callback), and `fetch_stills` will cut after the span is known and before the file is cleaned up. The cut goes to a second temp file in the same directory. Both files are deleted in a `finally`.

4. **Best effort.** The cut and the upload sit in `try/except`. On failure we log `clip_not_stored` with reason `cut_failed` or `upload_failed` and save the event without `clip_key`. Stills, analysis and the outcome stay the same.

5. **Viewer gating is server-side.** `get_events` sets `clip` to `null` for the viewer role. The PWA just renders whatever it gets, so a viewer token can't reach the clip even by calling the API directly.

6. **PWA.** `EventCard` renders `<video src={clip} poster={stills[0]} muted playsInline controls preload="metadata">`, with no autoplay. On an `onError` it switches to the existing `Stills` grid. The still-link cache in `EventPage` grows to `{stills, clip, at}`. A cached entry is reused only if the still count and whether there is a clip both match.

## Risks / Trade-offs

- [Ring keyframes are far apart, so the stored file has several seconds of lead-in] → `#t=` hides it. The cost is a little extra storage. The "under 9.0 s" spec bound assumes 2 s GOPs. The test fixture sets the GOP, and real clips are checked by hand.
- [Some browsers ignore the end time in `#t=start,end`] → It is part of the Media Fragments spec and Safari and Chrome support it. The worst case is that playback runs to the end of the stored cut, which is only one GOP past `closed_at` at most.
- [Unblurred faces in a stored clip] → Only owner and user tokens can get it (the same as Livestream), the link lasts 15 minutes, and the clip expires in 7 days. The "Blur faces" setting doesn't apply to clips. The card shows the clip only for roles that can already watch live video.
- [Extra S3 cost] → About 1–2 MB per opening for 7 days, which is negligible for a single fridge.

## Migration Plan

No migration. Old events have no `clip_key` and keep showing stills. Deploy the backend and the PWA together. Rolling back the PWA just ignores `clip`.

## Test strategy

- **Unit (pytest):**
  - `clip_frames.cut_clip` runs on a small synthetic MP4. A test helper builds it with PyAV at a known GOP (keyframes every 2.0 s) and frame rate, using the existing helpers in `tests/clip_video.py`. The tests assert the start keyframe, the duration bound and the `clip_span` math, plus the open-to-end-of-clip case and a corrupt file raising `ClipUnavailable("cut_failed")`.
  - `fetch_stills` uses moto S3 and a stubbed Ring client that serves the synthetic clip. The tests assert that `clip.mp4` is stored under the stills prefix, `clip_key` and `clip_span` are on the door event, and nothing is written for `not_door` or the fallback path. They also cover an upload failure (a stubbed `put_object` raising for the `.mp4` key) and confirm no temp files are left in `clip_dir`.
- **Contract (pytest, API):** `test_api_events_page` / `test_api_reads` cover owner, user and viewer tokens: the `clip` link with its `#t=` fragment, `null` for viewers, `null` with no `clip_key`, and `null` for events older than 7 days. Presigning runs against moto.
- **Component (Vitest):** `Activity.test.tsx` covers the video's attributes and poster, no still buttons when there is a clip, falling back to stills on `error`, the clip link staying stable across a poll, and a clip appearing on a later poll.
- **Stubbed:** Ring (canned redirect plus a local MP4), S3 (moto), and the face blurrer (the existing fake). Nothing calls live Ring, AWS or Bedrock.
- **Manual:** after deploy, open one real door opening on the hosted PWA as the owner and check that it plays only the open span.
