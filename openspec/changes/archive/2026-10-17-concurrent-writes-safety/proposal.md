# Proposal

## Why

A code review found two read-modify-write races in the backend. Still downloads run up to 8 threads that share one Ring client, so several threads can refresh the same expiring token at once and save over each other; the scheduled refresh job can even mark a freshly refreshed account `needs_relink` because its own copy of the refresh token was stale. Separately, every inventory write reads `ITEM#<name>` and then puts the whole row back unconditionally, so a door event saved while the PWA edits the same item loses one of the changes, and an edit racing a delete brings the deleted item back.

Tracks: Ring (reliable token handling against the Ring Partner API) and AWS Builder (correct DynamoDB writes).

## What Changes

- Ring API calls reload the stored tokens before refreshing and use them if another caller already refreshed; refreshes inside one process run one at a time.
- The scheduled refresh job reloads the tokens when Ring rejects a refresh, and marks the account `needs_relink` only if the stored refresh token is still the one Ring rejected.
- Every inventory write (door-event save, confirming a pending change, set count, add by hand, edit, rename) only succeeds if the item is still as it was read; otherwise it reads again and retries, so concurrent changes are all kept and a deleted item stays deleted.

Out of scope: cross-process locking for Ring tokens (Secrets Manager has no compare-and-set; the reload covers the common case), a `version` attribute on items, PWA changes, retry limits exposed in the API.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `ring-token-lifecycle`: adds a "Concurrent refreshes keep the newest tokens" requirement.
- `fridge-inventory`: adds a "Concurrent inventory writes keep every change" requirement.

## Impact

- `backend/src/fridgesense/ring.py` (`RingClient._refresh`), `backend/src/fridgesense/handlers/token_refresh.py` (`run_refresh`)
- `backend/src/fridgesense/inventory.py` (`save_task`, `confirm_pending`, `set_quantity`, `add_item`, `edit_item`)
- No API, schema, infra or PWA changes. A few more DynamoDB reads only when a write loses a race.
