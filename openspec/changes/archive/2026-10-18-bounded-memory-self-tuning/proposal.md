# Proposal

## Why

On 17 Oct 2026 the `fridgesense-door-events-failed` alarm fired. Four door-event runs failed and nine more attempts had to be retried, all with `Runtime.OutOfMemory` in the `FetchStills` step (the 2048 MB pipeline Lambda peaked at 2045–2047 MB). The cause is `self_tuning.sample_event`. It decodes every frame of the event to RGB at once (`images = [_open_rgb(f) for f in frames]`). A long opening's clip gives 190–240 frames at 500 ms, and each 2K frame is about 11 MB decoded, so this step alone needs about 2.1–2.6 GB. Each failed run drops a real door opening from the inventory.

## What Changes

- `sample_event` decodes one frame at a time. It decodes the bookend once, makes one pass over the other frames that scores every zone rule on each frame and keeps only the index of each zone's best frame, then decodes those best frames again to build their `Look`s.
- Peak memory for event sampling no longer grows with clip length. The stored samples stay exactly the same, including ties, where the later frame still wins.
- No change to the Lambda's memory size, the state machine, or the stored sample format.

## Capabilities

### New Capabilities
- `door-self-calibration`: adds one requirement to this capability, which the unarchived `door-auto-calibration` change introduced: event sampling holds a bounded number of decoded frames.

### Modified Capabilities
<!-- none -->

## Impact

- Code: `backend/src/fridgesense/self_tuning.py` (`sample_event` only).
- Tests: `backend/tests/test_self_tuning.py` gets a test that counts live decoded frames. The existing sampling tests guard the unchanged results.
- Ops: once deployed (with Jayson's OK), long openings stop failing `FetchStills`. The alarm should stay OK.
- Hackathon track: AWS Builder (reliability of the Lambda / Step Functions pipeline).

## Out of scope

- Raising the pipeline Lambda's memory, or tuning other memory use in `fetch_stills`, such as the in-memory JPEG frame list.
- Replaying or recovering the door openings lost on 17 Oct.
- Changing what is sampled or how rules are re-tuned.
