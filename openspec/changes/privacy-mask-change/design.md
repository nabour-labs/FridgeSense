# Design

## Context

What happened in prod on 2026-10-18, measured against the stored setup (run 2026-10-17 21:08Z) and the 21:32Z clip:

| Measure | Value |
|---|---|
| `ALIGN#` item | `moved = true`, `failures = 3`, `dx = dy = 0`, `suspect_streak = 4` |
| Whole-frame edge error, 3 traced events | 0.068, 0.068, 0.072 (limit 0.05) |
| Share of that error outside the area visible in both frames (mask, mask border, overlay text) | 45% |
| Error with that area left out, scaled back to the whole frame | ~0.040 (would have passed) |
| Visible area: anchor vs new clip | 37% vs 30% of the frame; maps differ in 13% of pixels |
| Door zones visible in the new clip | Chiller, Freezer Drawer 1 and Freezer Drawer 2 all 100% |

So the mask change pushed alignment over its limit, and 3 failures in a row set `moved`. It is not a camera move: the best shift with masked pixels left out is exactly `(0, 0)`.

Both bookends of every traced clip also show the owner standing in front of the fridge. That is why the setup's `change` rules read open throughout (4 suspect clips → `door_setup_mismatch`). It also makes the whole-image error high in the visible area (0.15 per visible pixel against 0.02–0.03 for the closed references).

Ring's device API lists `privacy_zones` as a capability but returns no zone shapes, so the mask has to be read from the pixels.

## Goals / Non-Goals

**Goals:**
- A privacy mask change alone never shows "The camera has moved".
- A mask change that hides part of a door zone shows a warning that names the zone.
- A person in front of the fridge in both bookends does not count as an alignment failure.

**Non-Goals:**
- Fixing suspect clips (and `door_setup_mismatch`) caused by a person blocking the zones
- Reading mask shapes from Ring, or moving zones automatically

## Decisions

### D1. Read the mask from the pixels: mostly-black neighborhoods
Ring paints masked areas solid black and draws its overlay text (logo, "Device-ID / Partner / Generated-At") on top. A pixel is masked when ≥ 80% of its 9×9 neighborhood is below gray 16. Thin text doesn't lower that share enough to unmask it. The masked area is then grown by 2 px so the strong edge at the mask border is never compared. On the prod frames this gives visible areas of 37% (anchor) and 30% (new clip), which match what you can see by eye.

*Alternatives:* a fixed list of overlay boxes (breaks when Ring moves them); the Ring API (no shapes returned).

### D2. Block match share instead of mean edge error
The mean error over the visible area can't tell a person in front of the fridge from a small rotation:

| Case (vs the newest closed reference) | Mean error per visible pixel (exploration) | Match share, final implementation |
|---|---|---|
| Other closed references | 0.024–0.033 | 1.00 |
| Prod clip, person in both bookends (first / last) | 0.152 | 0.59 / 0.53 |
| Reference rotated 2° / 3° / 5° | – / – / 0.17 | 0.76 / 0.56 / 0.55 |
| Reference rotated 10° / 15° | 0.18 | 0.41 / 0.45 |

A person covers some blocks and leaves the rest lined up. A rotation moves every block a different amount, so few blocks match at any one shift. `ALIGN_MIN_MATCH = 0.5` passes the person case and rejects rotations of 10° or more. On this camera a rotation of 5° or less also passes, at shift `(0, 0)`. The fridge strip sits at the center of the frame, so such a tilt moves the zones by about 2 px at 128×72 (~1.5%), well under the 0.04 that counts as a move. Blocks with almost no anchor edges (mean < 8) are skipped because they match at any shift. `error` stays in the stored alignment as `1 − share`, so the item and API shape don't change.

*Alternative:* keep the mean error and raise the limit to ~0.16. Rejected: that is within 0.02 of a 5° rotation.

### D3. Mask change = visible maps differ > 3% on 2 events in a row
One frame can be odd (dark kitchen at night, a hand over the lens), so a change needs 2 events in a row, the same idea as the 3-failure rule for moves. 3% is well above the frame-to-frame noise between the closed references (0%) and well below the real change (13%).

### D4. No zone hit → adopt the new map silently; zone hit → warn and keep the old map
If every zone is still fully visible, the door rules still read the same pixels, so there is nothing for the owner to do. Adopting the new map stops the 2-in-a-row check from firing again. If a zone is hit, its rule now reads mask pixels. Keeping the old map keeps the warning up until the owner re-runs setup, and setup builds a new map from the new references.

### D5. Backfill the map for the existing setup lazily
The prod setup predates this change. The first aligned event builds the map from the newest closed reference (the same image the anchor came from) and stores it on the `DOORSETUP#` item. No migration script is needed.

### D6. Prod cleanup of the false move
The prod `ALIGN#` item already reads `moved = true`, and `moved` only clears on a setup run. After deploy, with Jayson's OK, set `moved = false`, `moved_at = null`, `failures = 0` and `last_moved_at = null` on that one item. It had no earlier move, so `null` is its old value, and clearing it also keeps a stale fridge-area link from appearing. Re-running setup would also clear `moved`, but `last_moved_at` would stay. That `UpdateItem` changes prod data, so it is listed as its own task that needs approval.

## Risks / Trade-offs

- [Occlusion and a small rotation overlap (0.53–0.59 vs 0.55–0.56 on the prod frames)] → tilts of 5° or less are no longer caught. They move the centered zones by ~1.5%, which the door rules tolerate. A person covering more than half the visible blocks in both bookends still fails, and 3 such events in a row still read as a move. The constants are set in one place, and the recorded-clip test pins the prod case.
- [A dark kitchen reads as masked] → a night clip with the lights off could look like a mask change. The 2-in-a-row rule and "no zone hit → adopt" keep this quiet. Worst case, a zone-hit warning that a setup run clears.
- [A lights-off night frame adopted as the map] → the anchor's map would shrink, and the next daytime event reads as a change back and adopts again. That costs nothing visible.
- [Per-block loop cost] → 17×17 shifts × ~40 blocks on 128×72 images, twice per event. That is milliseconds in Pillow; if not, crop all blocks once with numpy.

## Test strategy

- **Unit (pytest)**: `alignment.visible_map`, `match_share`, `best_shift` with maps, `align_bookends`, `record` (mask streak, adopt vs warn) and the setup-run reset, all on synthetic Pillow images: test patterns, painted black bands, white text in the mask, a gray "person" rectangle, and rotations.
- **Recorded fixture**: `tests/fixtures/alignment/mask_change/` holds the newest closed reference and the 21:32Z clip's first and last frames, **saved at 128×72 grayscale**, the size alignment uses. At that size the person is an unrecognizable blob. Getting these files from prod S3/DynamoDB is a read. Committing them needs Jayson's OK (see Open Questions).
- **Contract**: `GET /api/warnings` with moto DynamoDB items for `privacy_mask_changed`, the zone-name joining, the empty case, and an unreadable alignment (patched `get` raising).
- **Integration**: `door_events` on a stubbed event with a stored setup missing `anchor_visible` → the backfill is stored. Setup run → map stored and mask fields cleared.
- **PWA (Vitest)**: `Warnings.test.tsx` for the banner, the link, the viewer case and no camera-moved text. The mock API gets a `privacy_mask_changed` toggle.
- No live Ring, AWS or Bedrock calls in tests.

## Open Questions

- Is it OK to commit 128×72 grayscale frames from the 2026-10-18 clip (the owner is in them) as the recorded fixture? If not, the "Recorded clip after a mask change" scenario uses a synthetic stand-in, and the prod check is done by hand.
- `door_setup_mismatch` from a person standing in front of the zones for a whole clip is still open. It should be its own change, for example to count a clip as suspect only if the zones also read open in frames where nothing covers them.
