# Tasks

## 1. Stock age and peak on inventory items (fridge-inventory)

- [x] 1.1 Write failing tests for "New item", "Adding more keeps the stock age", "Peak rises above the old peak", "Running out clears both" and "Restock after running out" through `save_task`; run `uv run pytest tests/test_save_task.py` and see them fail on the missing `stocked_at` / `peak_quantity`
- [x] 1.2 Implement `stocked_at` and `peak_quantity` in `quantity_put`; the 1.1 tests pass
- [x] 1.3 Write failing tests for "Confirmed pending change" (`confirm_pending`) and "Count set by hand" (`set_quantity`, 12 → 0 → 6); run them and see them fail
- [x] 1.4 Implement the same rule in `set_quantity` (sharing one helper with `quantity_put`); the 1.3 tests and all existing inventory tests pass

## 2. oldest_items answer and tool (fridge-mcp)

- [x] 2.1 Extend `tests/mcp_helpers.put_item` to accept `stocked_at`, `peak_quantity` and `first_seen_at`; existing tests still pass
- [x] 2.2 Write failing tests in `tests/test_fridge_oldest.py` for "What should I eat first?", "Long-life items left out", "One category, even a long-life one", "Out-of-stock items are not listed", "Limit", "Item saved before stock tracking" (also covers the fridge-inventory "Item saved before this change" read fallback) and "Nothing perishable"; see them fail on the missing function
- [x] 2.3 Implement `oldest_items` and its result model in `fridge_answers.py`, with the read-time fallback helper; the 2.2 tests pass

## 3. low_stock answer and tool (fridge-mcp)

- [x] 3.1 Write failing tests in `tests/test_fridge_low_stock.py` for "What do I need to buy?", "Old run-outs are dropped", "At most ten run-outs", "Not low yet", "Single item never counts as low" and "Nothing to buy"; see them fail on the missing function
- [x] 3.2 Implement `low_stock` and its result model in `fridge_answers.py` (reusing the fallback helper); the 3.1 tests pass

## 4. MCP server exposes six tools (fridge-mcp)

- [x] 4.1 Update `test_mcp_server.py`: `TOOLS` lists six names ("Tool list"); add contract tests calling `oldest_items` and `low_stock` over the in-memory client, "Limit out of range" (0 and 21 give an error result naming the range), and "Not linked" for both new tools; run them and see them fail
- [x] 4.2 Register `oldest_items(category?, limit?)` with `Annotated[int, Field(ge=1, le=20)]` and `low_stock()` in `mcp_server.py` with `READ_ONLY` annotations and when-to-use descriptions, and mention the new questions in `INSTRUCTIONS`; the 4.1 tests pass
- [x] 4.4 Update `test_assistant_loop.py` and `test_assistant_clean.py` for "Six tools offered" (fridge-assistant); they pass against the six-tool server
- [x] 4.3 Update README "Voice and MCP (Alexa+)": six tools and the two example questions; check the text renders

## 5. Ask keyword fallback (fridge-ask)

- [x] 5.1 Write failing tests in `test_ask_parse.py` for "Eat first", "Shopping list", "One item is not a shopping question", and keep the existing "Questions map to one intent" scenarios green; see the new ones fail
- [x] 5.2 Implement the `oldest_items` and `low_stock` intents in `parse` (checked first) and dispatch them in `ask`; the 5.1 tests pass
- [x] 5.3 Write failing tests in `test_ask_say.py` for "Three oldest", "Yesterday", "Nothing to use up", "Out and low", "Only low" and "Nothing to buy"; see them fail
- [x] 5.4 Implement `say_oldest` and `say_low_stock`; the 5.3 tests pass, and an `/api/ask` test (`test_api_ask.py`) for "What should I eat first?" returns intent `oldest_items`

## 6. Ask screen examples (inventory-app)

- [x] 6.1 Write a failing Vitest test in `pwa/src/screens/Ask.test.tsx` for "Five examples" (five buttons in order; tapping "What should I eat first?" posts it); run `npm test` in `pwa/` and see it fail
- [x] 6.2 Add the two examples to `EXAMPLES` in `pwa/src/screens/Ask.tsx`; the Ask tests pass and the buttons wrap cleanly at 375 px wide

## 7. Finish

- [x] 7.1 Run the full suites and linters green: `uv run pytest` and `uv run ruff check . && uv run ruff format --check .` in `backend/`, `npm test` and `npm run lint` (if defined) in `pwa/`; report the commands and results
