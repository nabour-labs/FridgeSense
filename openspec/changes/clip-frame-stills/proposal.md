# Proposal

## Why

For a door opening found in the clip, the picked clip frames scored open, but the Ring stills fetched at the same timestamps can all show the door closed, so Nova gets four closed-door stills. On the 2026-10-17 21:13:37Z event (17:13 local) the clip check said `door_open` (`source: clip`, setup rules, `change` feature) and opened 21:13:49.9Z–21:14:01.9Z; all 4 stored stills show closed doors and people walking past, yet Nova listed "+ soda can". Ring's `at_timestamp` still is documented as "the nearest frame within ±10 s", so it is not the frame the check looked at. The clip frames are already 2560×1440 JPEGs, the same size as the Ring stills.

## What Changes

- For a door opening found in the clip, the stored stills SHALL be the picked clip frames themselves (JPEG), not Ring stills fetched at their times. No Ring still requests are made on the clip path.
- The "Still missing, frame used" behaviour goes away on the clip path, since no still is requested.
- The still-sampling fallback (no clip) is unchanged: it still downloads Ring stills.

Track: Ring (Ring Partner API media endpoints) and AWS Builder (Bedrock Nova input quality).

Out of scope:
- Showing the open-span clip on Activity cards (the separate `event-open-clip` change).
- Any change to how the open span, the picks, or the open/close times are computed.
- Re-analysing past events whose stored stills are wrong.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `door-event-detection`: "Stills for an opening found in the clip" stores the picked clip frames instead of requesting Ring stills at their times.

## Impact

- `backend/src/fridgesense/door_events.py`: `fetch_stills` stores the picked frames; `stills_at` is removed.
- `backend/tests/test_fetch_stills_clip.py`: the three scenario tests for the requirement.
- Fewer Ring API calls per opening (4 still requests and their downloads saved) and slightly faster steps.
- `docs/friction-log.md`: entry on Ring `at_timestamp` stills not matching the clip frame time.
