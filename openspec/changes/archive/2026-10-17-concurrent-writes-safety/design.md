# Design

## Context

See proposal.md - Why. `RingClient` is built once per Lambda invocation (`deps.ring_client`) and shared by up to 8 download threads (`door_events.download_all_stills`, `download_clip_frames`). Tokens live in one Secrets Manager secret, which has no conditional write. Inventory items are `ITEM#<key>` rows in the single DynamoDB table; every write path reads the row, computes the new row in Python (quantity, `stocked_at`, `peak_quantity`, `first_seen_at`) and writes it back, some inside a `TransactWriteItems` with the door event or pending change.

## Goals / Non-Goals

**Goals:**
- No duplicate OAuth refreshes within a process, and no stale token copy saved over newer tokens.
- No lost inventory updates and no resurrected deleted items, without changing the item schema.

**Non-Goals:**
- Cross-process mutual exclusion for token refresh (only a reload check).
- Changing item fields, API responses or the PWA.

## Decisions

### Tokens: reload under a module-level lock
`RingClient._refresh(stale)` takes a module-level `threading.Lock`, reloads the store, and returns the stored tokens without refreshing when their access token differs from `stale.access_token`; otherwise it refreshes from the stored copy and saves. A module-level lock (not per instance) also covers separate clients in the same process. Alternative considered: refresh-token rotation detection via OAuth error only — that still makes a wasted call and can mark the link broken.

### Scheduled job: re-check before `needs_relink`
On `OAuthRejected`, `run_refresh` reloads; if the stored refresh token differs from the rejected one, it logs `token_refresh_superseded` and returns `"already_refreshed"` without saving. Otherwise it marks the reloaded copy `needs_relink`.

### Inventory: optimistic condition on the read state, retry
Atomic `ADD quantity :d` was considered but rejected: `stocked_at` and `peak_quantity` depend on the old quantity (reset on restock, dropped at 0), the count is clamped at 0, and "remove an unknown item" must not create one — none of which `UpdateExpression` can express cleanly. Instead each item Put carries a condition built from the row that was read:
- row absent → `attribute_not_exists(sk)`
- row present → `quantity = :q AND last_changed_at = :t` (or `attribute_not_exists(last_changed_at)` for legacy rows)

No `version` attribute is added, so stored rows and API output keep their shape. If the write would remove an item that was read as absent, nothing is written (as today).

On a conflict the whole read-compute-write is redone, up to 5 attempts, then the conflict is raised. In transactions the item conditions sit next to the existing ones; cancellation reasons are per operation, so:
- `save_task`: door update first → its failure still means "already saved"; an item failure → retry.
- `confirm_pending`: pending delete first → still `PendingNotFound`; item failure → retry.
- `edit_item` rename: new-row Put `attribute_not_exists` → `ItemExists`; old-row Delete now uses the read-state condition; failure → retry, and the retry's read finds the item gone → `ItemNotFound`.
- `set_quantity`, `add_item`, same-key `edit_item`: plain `put_item` with a condition; `ConditionalCheckFailedException` → retry.

A small `FridgeTable.put(item, condition=...)` extension carries the condition; `FridgeTable.transact` already passes `ConditionExpression` through.

## Risks / Trade-offs

- [Two writes with the same quantity and the same `last_changed_at` (ABA)] → timestamps are door close times or ms clock time for one fridge; practically unique. Accepted.
- [Secrets Manager is still last-writer-wins across Lambdas] → the reload shrinks the window; the scheduled job no longer marks good tokens broken.
- [Retries exhausted under heavy contention] → raise; Step Functions retries the save task, the API returns 500. With one fridge this is not expected.

## Test strategy

- Unit tests with respx for the OAuth endpoint and Ring API, and the in-memory token store from `tests/conftest.py`. The concurrent-refresh test uses two real threads and a `threading.Barrier` in the store's first loads so both read stale tokens before either refreshes.
- Integration tests on moto DynamoDB (`aws` fixture) using a `FridgeTable` subclass whose `get` runs a hook (the competing write) once, right after the racing write reads its item. This interleaving is deterministic.
- Existing inventory, API and pipeline tests stay green unchanged.
