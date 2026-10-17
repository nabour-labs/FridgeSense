# Proposal

## Why

Setup works out the door zones by grouping the reference boxes: a box joins the first group it overlaps by IoU ≥ 0.3. The owner has to draw the same box again on every snapshot, and a drawer looks different open and closed, so boxes for one door often fail to group. On 2026-10-17 the owner added 10 references for a door and a drawer, and setup answered "zone 3 needs an open and a closed reference". One thin "closed" drawer box (y 0.647, height 0.09) had started its own zone, and the open drawer box that matched it best had already joined another group. The owner had no way to see or fix this.

The owner knows where the doors are. Setup should ask for that first, then ask for open and closed snapshots of each zone.

## What Changes

- **Zones come first.** The owner defines 1 to 6 door zones. Each zone has a name (such as "Fridge doors" or "Freezer drawer") and one box drawn on a camera snapshot. Zones can be added, renamed or redrawn, and deleted. New routes: `POST /api/door-calibration/zones`, `PATCH /api/door-calibration/zones/{id}` and `DELETE /api/door-calibration/zones/{id}`.
- **References belong to a zone.** **BREAKING:** `POST /api/door-calibration/references` takes `{"image", "zone_id", "status"}` and no longer takes a box. Every reference is measured with its zone's box. Deleting a zone deletes its references. The limit goes from 12 references per device to 24, so 6 zones can each have several references.
- **Setup uses the defined zones.** `POST /api/door-calibration/run` makes one rule per defined zone, in the order the zones were added. The IoU grouping is removed. Each zone needs at least one open and one closed reference, and the error names the zone: `"Freezer drawer needs an open and a closed reference"`. With no zones, it answers `"add a door zone first"`.
- **`GET /api/door-calibration`** gains `zones: [{"id", "name", "box", "open", "closed"}]` (with reference counts per status). Each reference gains `zone_id`, and its `box` is now its zone's box. Setup zones gain `id` and `name`.
- **The Open/close detection tab is a two-step setup.** Step 1, "Door zones": draw and name each zone. Step 2, "References": the list is grouped by zone. Each zone shows how many open and closed references it has, with a "needs open" or "needs closed" hint. "Add" asks for the zone and the status, and shows the zone's box on the snapshot instead of asking the owner to draw one. "Run setup" is enabled only when every zone has at least one of each.
- **Old references are not used.** References saved before this change have no zone. They are not listed, not counted toward the limit and not used by setup. After deploying, they are deleted from the table (with the owner's OK). The stored setup result keeps working until setup runs again.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `door-calibration`: a new requirement for defining door zones. Reading the setup, adding and deleting references, running setup and the owner-only rule change to use the defined zones instead of grouping boxes.
- `inventory-app`: the Open/close detection tab becomes a zones step and a per-zone references step.

## Impact

- **Backend:** `backend/src/fridgesense/door_calibration.py`: zone items and their validation; references keyed to a zone; `run` and `reference_scores` use zones by id; `group_boxes` and `GROUP_IOU` are removed. `handlers/api.py`: three zone routes and the new reference body. The door check (`setup_check`) and the stored setup shape stay the same, plus `id` and `name` per zone.
- **Data:** new DynamoDB items `DOORZONE#{device}#{created_ms}-{rand}` with `name` and `box`. `DOORREF#` items gain `zone_id` and lose `box`. All are keyed by Ring `account_id` and device ID.
- **PWA:** `screens/DoorDetection.tsx` (zones section, grouped references, the add sheet picks a zone), `api/client.ts` and `api/types.ts`, and `scripts/mock-api.ts`.
- **Other changes in progress:** `door-auto-calibration` shifts and retunes the setup zones. It reads the stored setup, which keeps its shape, so it is unaffected. Its samples are per setup zone, which is now per defined zone.
- **Infra, Ring and cost:** none. No new Ring or Bedrock calls.

**Hackathon tracks:** Ring (a camera-based door setup that the owner can get right on the first try) and AWS Builder.

**Out of scope:**
- Drawing a zone as anything other than one rectangle (no polygons).
- Different zone boxes for open and closed. A zone's box should cover the door or drawer in both positions.
- Suggesting zones automatically from the snapshot.
- Moving old references into zones. They are dropped and the owner adds new ones.
- Changing which feature setup picks, or the door check itself.
