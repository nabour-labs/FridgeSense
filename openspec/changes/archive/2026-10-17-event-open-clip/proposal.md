# Proposal

## Why

An Activity card can list a change that its stills don't show. On 2026-10-17 the 17:13 opening listed "+ soda can", but all 4 stills showed the door closed, so there was no way to check the claim. The door check already downloads the Ring event clip and finds when the door was open. A short clip of just that span shows what actually went in or out.

Hackathon tracks: **Ring** (makes more use of the Ring video download API) and **AWS Builder** (S3, Lambda, PyAV).

## What Changes

- When the door check finds an opening in the event clip, the pipeline cuts that clip down to the open span (`opened_at` → `closed_at`) and stores it next to the stills as `clip.mp4`. The bucket's 7-day lifecycle still deletes it.
- The door event record gets the clip's key.
- `GET /api/events` adds a `clip` field to each event: a 15-minute link to the open-span clip, or `null`. Only owner and user tokens get it. Viewer tokens always get `null`, because the clip is not face-blurred.
- On the Activity card, the clip replaces the stills when the event has one: an inline, muted video with controls and the first still as its poster. Events without a clip (viewers, the still-sampling fallback, a failed cut, or events older than 7 days) show the stills as they do today.
- The clip link stays the same across polls, as still links do, so a poll doesn't restart a clip that is playing.
- **BREAKING (spec):** "Clips never stored" is relaxed. The open-span cut is the one clip object allowed in S3. The full event clip is still only kept in `/tmp`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `door-event-detection`: store the open-span clip, record its key on the door event, and relax "Clips never stored" to allow only that object.
- `inventory-api`: "Door event listing" gains a `clip` link, which viewers never get.
- `inventory-app`: "Activity screen" plays the clip instead of the stills when there is one, and the clip link stays stable across polls.

## Out of scope

- **Why the stills showed a closed door.** The likely cause is that `stills_at()` replaces each open-span clip frame with a Ring still requested at the same timestamp, and Ring's still clock seems offset from the clip's. Nova analyzes those stills, so it reported a soda can from closed-door images. That bug needs its own change. This change only makes the opening watchable.
- Face-blurring video. Viewers keep the blurred stills instead.
- Clips for the still-sampling fallback path, where no clip was downloaded.
- Sending the clip to Nova, or changing what Nova analyzes.
- Deleting the clip when an event is deleted. Stills aren't deleted then either; the 7-day lifecycle removes both.
- Fire TV and MCP.

## Impact

- Backend: `door_events.fetch_stills`, `clip_frames` (new trim helper on PyAV), door event record (`clip_key`), `handlers/api.get_events`.
- PWA: `screens/Activity.tsx` (`EventCard`, link caching), `api/types.ts` (`DoorEvent.clip`).
- S3: one extra object per door opening, typically under 2 MB for a 10–20 s span. It expires after 7 days.
- Pipeline Lambda: a short remux of the clip it already downloaded. Its memory and timeout stay the same.
- No new dependencies (`av` is already a runtime dependency). No infra changes.
