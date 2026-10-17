# Tasks

Branch: `feat/door-zones-defined` off `local`. Backend: `cd backend && uv run pytest`. PWA: `cd pwa && npm test`.

## 1. Door zones (backend)

- [x] 1.1 Write failing tests in `backend/tests/test_door_calibration.py` for "Zone added", "Invalid zone rejected", "Zone limit", "Zone redrawn" and "Zone deleted with its references" (moto table). Run them and confirm they fail because the zone functions are missing.
- [x] 1.2 Implement `DOORZONE#` items in `door_calibration.py`: `add_zone`, `update_zone`, `delete_zone` (which also deletes the zone's references), `list_zones`, name validation and `MAX_ZONES` reuse, with each one marking setup stale. Verify the 1.1 tests pass.

## 2. References belong to a zone (backend)

- [x] 2.1 Write failing tests for "Reference added" (zone box returned, counts), "Unknown zone", "Reference limit" (24) and "Old references without a zone" (stored with a `box` and no `zone_id`, not listed or counted). Confirm they fail because of the old body and limit.
- [x] 2.2 Change `add_reference` to take `zone_id` (validated against the device's zones), store no box, and set `MAX_REFERENCES = 24` counting only zoned references. Change `list_references` to skip references without a zone, or whose zone is gone, and to fill `box` from the zone. Verify the 2.1 tests pass, and update the existing reference tests to the new body without weakening what they assert.

## 3. Setup uses the defined zones (backend)

- [x] 3.1 Write failing tests for "One setup zone per defined zone", "References in one zone are not regrouped", "Overlapping boxes become one zone" (never merged), "Too many zones" (7 zones in the table), "No zones", "Missing a status" (named zone), "Open and closed overlap" (named), "Old references ignored", and "Setup from one open and one closed reference" with `id` and `name`. Rewrite the existing feature-choice tests (brightness, change, darker, blue tie, color) to create a zone first. Confirm the new tests fail.
- [x] 3.2 Rewrite `run()` to loop over `list_zones`, store each zone's `id` and `name` in the setup item, remove `group_boxes`, `_bounding` and `GROUP_IOU`, and rewrite the "Overlapping boxes become one zone" and "Too many zones" tests to their new scenarios (written failing first, in 3.1). Verify the 3.1 tests pass.
- [x] 3.3 Write failing tests for "Setup marked stale" (score from the zone's setup feature) and "Reference of a zone added after setup" (null). Then change `reference_scores` and `load_setup` to match by zone id, with no `id` in the setup meaning null. Verify the tests pass.
- [x] 3.4 Refactor with tests green. Check that `setup_check` and the debug-trace tests (`test_pipeline_debug_traces*.py`, door rule `references` with `box`) still pass unchanged.

## 4. API routes (backend)

- [x] 4.1 Write failing contract tests in `backend/tests/test_api_door_calibration.py` for `POST /api/door-calibration/zones`, `PATCH` and `DELETE /api/door-calibration/zones/{id}` (200 body, 400, 404, 409), the new reference body, the `GET` shape (`zones` with `open`/`closed`, reference `zone_id`, setup zone `id`/`name`), "Nothing set up yet", the viewer 403 on all three zone routes, and "Zones kept per device". Confirm they fail.
- [x] 4.2 Add the three zone routes and the new reference body and GET body to `handlers/api.py`. Verify the 4.1 tests and the existing door-calibration API tests pass.

## 5. Open/close detection tab (PWA)

- [x] 5.1 Write failing tests in `pwa/src/api/client.test.ts` for `addDoorZone`, `updateDoorZone` and `deleteDoorZone`, and the new `addDoorReference(image, zoneId, status)`, and update `api/types.ts`. Then implement them in `api/client.ts`. Verify with `npm test`.
- [x] 5.2 Write failing tests in `pwa/src/screens/DoorDetection.test.tsx` for "Not set up", "Add a door zone", "Zone needs a box and a name", "Redraw replaces the box", "Tiny drag ignored", "Edit a zone" and "Delete a zone". Then build the "Door zones" section. Verify the tests pass.
- [x] 5.3 Write failing tests for "References shown", "Add a door reference", "Box and status required", "Only one zone", "Snapshot fails while adding", "Delete a door reference" and "Zone checklist". Then group references by zone and change the add sheet to a zone picker with the zone's box shown read-only. Verify the tests pass.
- [x] 5.4 Write failing tests for "Run setup", "Setup fails", "Run setup needs both statuses", "Stale setup", "Blue light feature named" and "Viewer sees setup read-only". Then update the run gating, the state lines with zone names and the stale text. Verify the tests pass.
- [x] 5.5 Update `pwa/scripts/mock-api.ts` for zones and the new reference body and errors. Check it by running the PWA against the mock and adding 2 zones and 4 references in the browser preview.

## 6. Ship and clean up

- [x] 6.1 Run the full suite and linters green: `cd backend && uv run pytest && uv run ruff check .`, `cd pwa && npm test && npm run typecheck`. Report the commands and results, and add any friction-log entries.
- [ ] 6.2 With Jayson's OK, after deploying: list the `DOORREF#` items without `zone_id` (`aws dynamodb scan … --filter-expression "begins_with(sk, :p) AND attribute_not_exists(zone_id)"`), show the count, then delete them. Verify the second scan returns 0 items.
