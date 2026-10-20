# Design

## Context

`door_calibration.py` stores each reference as `DOORREF#{device}#{ms}-{rand}` with `image`, `box` and `status`. `run()` groups the boxes with `group_boxes()` (first group with IoU ≥ `GROUP_IOU = 0.3`), measures each reference in its group's bounding box, and stores `SETUP#{device}` with one entry per zone (box, feature, direction, threshold, margin, baseline). `reference_scores()` matches a reference to a setup zone by IoU. A `DOORCHANGED#{device}` marker (`_mark_changed`) makes `setup.stale` true. The door check (`setup_check`) reads only the setup item. The PWA tab is `pwa/src/screens/DoorDetection.tsx`, and the add sheet draws one box with `ImageMarkup`.

The live table holds 10 old references for device `…TNUH`, which are the ones in the bug report (see proposal.md).

## Goals / Non-Goals

**Goals:**
- Zones are records the owner creates. The zone a reference belongs to is stored, never guessed.
- The door check and the stored setup shape stay the same, so `door-event-detection`, debug traces and `door-auto-calibration` need no change.

**Non-Goals:**
- A migration that keeps the old references.
- Any change to how features, thresholds or baselines are worked out.

## Decisions

1. **Zone items: `DOORZONE#{device}#{ms:013d}-{rand}` with `name` and `box`.** This uses the same sort-key pattern as references, so a prefix query lists them oldest first, which is the order setup uses. *Alternative:* a single `DOORZONES#{device}` item holding a list. Rejected because each edit would rewrite the whole list, and adding or deleting would not match how references already work.

2. **A reference stores `zone_id` (the zone's sort key) and no box.** Reads join each reference to its zone's current box, so redrawing a zone moves all its references with it. *Alternative:* copy the zone box into each reference when it is saved. Rejected because the copies would drift after a redraw, which is the same kind of mismatch this change removes.

3. **Delete `group_boxes`, `_bounding` and `GROUP_IOU`.** `run()` loops over the zones. For each zone it takes `[r for r in refs if r.zone_id == zone.sk]` and then picks a feature exactly as it does now. `reference_scores()` matches a reference to a setup zone by `id`. To do that, the setup item stores each zone's `id` and `name` next to its box. A setup stored before this change has no `id`, so its references score null until setup runs again. That is acceptable.

4. **Old references (no `zone_id`) are skipped when read.** `list_references` drops them, so they are not listed, not counted and not used. A one-off clean-up deletes them from the live table, run with Jayson's OK: an `aws dynamodb` query of `DOORREF#` items without `zone_id`, then deleting each. *Alternative:* a lazy migration that puts each old reference into a zone by IoU. Rejected because it rebuilds the grouping this change removes, and re-adding about 10 snapshots takes a few minutes.

5. **Deleting a zone deletes its references in the same request.** These are plain per-item deletes, at most 24, which is well within Lambda time. There is no transaction: if a delete fails partway through, any references left behind belong to a missing zone. Reads treat them the same as old references and skip them.

6. **Zone edits mark setup stale** through the existing `_mark_changed`. The stale text becomes "Zones or references changed."

7. **Limits:** 6 zones (`MAX_ZONES`, unchanged) and 24 references (up from 12). At ≤300 KB each, 24 references is at most about 7 MB in the table, and the GET body is about 7 MB of base64 at worst. That is under the 10 MB API Gateway limit, but large. Typical use is 2 zones × 3 references.

8. **PWA flow:** the tab gets two `<section>`s. "Door zones" reuses the snapshot-and-draw sheet with a name field. The reference sheet loses drawing (`ImageMarkup` `readOnly`, with the picked zone's box as its shape) and gains a zone `Select` (the existing `components/Select.tsx`), which is preselected when there is only one zone. The `Run setup` check becomes `zones.length > 0 && zones.every(z => z.open > 0 && z.closed > 0)`.

## Risks / Trade-offs

- [The owner draws a zone box that covers only the closed door, so the open door falls outside it] → The add-zone sheet's hint says "Draw around the door or drawer, open and closed". Setup's overlap error names the zone, so the owner knows which zone to redraw.
- [**BREAKING** API body change for references] → The PWA and the API ship together in one deploy, and no other client calls this route.
- [Old references keep taking table space until the clean-up runs] → They are a few MB at most. The clean-up is task 6.2.

## Migration Plan

1. Deploy (with Jayson's OK). The existing setup result keeps driving the door check.
2. The owner adds zones and references, then runs setup.
3. Delete the old `DOORREF#` items that have no `zone_id` (with Jayson's OK).

Rollback: redeploy the previous version. New zone items are ignored by it, and new references (no `box`) would break it, so delete them before rolling back.

## Test strategy

- **Unit (pytest, moto DynamoDB as the existing `test_door_calibration.py` does):** zone add, patch, delete and limits; references tied to a zone; `run` with defined zones; ignoring old references; scores matched by zone id; stale marking. Images are built with Pillow as the current tests do (plain grey, coloured blocks).
- **Contract (pytest, `test_api_door_calibration.py`):** every route's status codes and JSON bodies, viewer 403s, and per-device isolation, through the API handler with the existing stubbed Ring device lookup.
- **PWA (Vitest + Testing Library, `DoorDetection.test.tsx`, `client.test.ts`):** each `inventory-app` scenario, with `fetch` stubbed. `mock-api.ts` is updated so the dev mock follows the new body.
- Nothing calls live Ring, AWS or Bedrock.
