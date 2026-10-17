# Tasks

## 1. Ring token refresh race

- [x] 1.1 Write failing tests in `backend/tests/test_ring_client.py` for "Concurrent refresh" (two threads, one OAuth call) and "Another caller already refreshed" (no OAuth call, uses `at2`); run them and see them fail
- [x] 1.2 Implement reload-before-refresh under a module-level lock in `RingClient._refresh`; verify with `uv run pytest tests/test_ring_client.py`
- [x] 1.3 Write failing tests in `backend/tests/test_token_refresh.py` for "Refresh rejected after another caller already refreshed" and "Refresh rejected and nobody else refreshed"; run them and see the first fail
- [x] 1.4 Implement the reload check in `run_refresh`; verify with `uv run pytest tests/test_token_refresh.py`

## 2. Inventory lost updates

- [x] 2.1 Write failing tests in `backend/tests/test_inventory_races.py` for "Two concurrent deltas both applied", "Door event saved while a pending change is confirmed", "Adding by hand while a door event is saved", "An edit racing a delete", "A rename racing a delete" and "Setting a count racing a door event"; run them and see them fail
- [x] 2.2 Add a conditional `FridgeTable.put` and the read-state condition helper with retry, and use them in `save_task`, `confirm_pending`, `set_quantity`, `add_item` and `edit_item`; verify with `uv run pytest tests/test_inventory_races.py tests/test_save_task.py tests/test_manual_items.py tests/test_pending_review.py`

## 3. Wrap up

- [x] 3.1 Run the full backend suite and ruff: `uv run pytest` and `uv run ruff check . && uv run ruff format --check .` in `backend/`, all green
