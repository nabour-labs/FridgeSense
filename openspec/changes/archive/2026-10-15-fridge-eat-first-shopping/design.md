# Design

## Context

Inventory items are single-table rows `pk = ACCOUNT#<id>`, `sk = ITEM#<key>`, written as whole-item `Put`s by `quantity_put` (confident changes and confirmations, in `inventory.py`) and by `set_quantity` (hand edits). Each row already has `quantity`, `first_seen_at` and `last_changed_at`. Neither existing timestamp answers "how old is the stock in the fridge now": `first_seen_at` survives run-outs, and `last_changed_at` moves on every removal.

The MCP tools are thin wrappers over pure functions in `fridge_answers.py` that read one `ITEM#` query, and `ask.py` reuses the same functions for the keyword fallback. The Nova assistant (`assistant.py`) builds its Converse tool list from `tools/list`, so new tools reach it without code changes.

## Goals / Non-Goals

**Goals:**
- Two read-only MCP tools that answer within Alexa's 500 ms budget: one table query each, no Bedrock calls.
- Keep the change to item rows additive and safe for rows written before it.

**Non-Goals:**
- Shelf-life rules per item or category beyond leaving out three long-life categories.
- A migration or backfill job.
- Any change to the Nova analysis, the pipeline or the CDK stack.

## Decisions

**1. Track `stocked_at` and `peak_quantity` on the item row.**
Both are set inside the existing whole-item `Put`, so they stay consistent with `quantity` in the same transaction. `stocked_at` resets only on a 0 → above-0 transition, which matches first-in-first-out: the oldest unit in the fridge went in when it was last restocked from empty. `peak_quantity` resets on restock too, so one big party purchase doesn't make the item look "low" forever.
*Alternatives:* derive age from door-event history (needs a scan of `DOOR#` rows per question, too slow for Alexa, and 7-day history isn't enough); per-unit lots (accurate, but far more model and UI than a demo needs).

**2. When quantity hits 0, drop both fields rather than store nulls.**
`quantity_put` and `set_quantity` build the row from scratch, so leaving the keys out is simplest, and readers already treat a missing field as "use the fallback".

**3. Fallback for older rows happens at read time.**
`stocked_at` falls back to `first_seen_at`, `peak_quantity` to the current quantity. The fallback lives in one small helper in `fridge_answers.py`, used by both tools. The live table only holds a few days of demo data, so no backfill is worth writing.

**4. Leave out condiment, frozen and beverage by default in `oldest_items`.**
These keep for weeks or months and would always top an "oldest" list, crowding out what really needs eating. The tool reports `skipped_categories` so the assistant can say so, and an explicit `category` overrides the filter.
*Alternative:* a shelf-life table per category (days until "use soon"). Better answers, but it's a judgment call per category and adds spec surface; it can come later without changing the tool's shape.

**5. "Running low" = `count * 4 <= peak_quantity`; "ran out" = quantity 0 within 30 days.**
Integer arithmetic, no floats. Single-unit items (milk at 1 of 1) never count as low and show up in `ran_out` instead, which is the useful answer for them. The 30-day window and the cap of 10 keep a spoken answer short and drop things the household stopped buying.

**6. Validate `limit` in the tool signature.**
`limit: Annotated[int, Field(ge=1, le=20)] = 5` makes the MCP SDK reject bad values before the tool body runs, which is how `fridge_activity` already rejects an unknown `period`, so no table query runs.

**7. Ask fallback: substring cues checked before every existing intent.**
The new cues are multi-word phrases that don't overlap the existing ones, so checking them first changes no existing intent. Single-item questions ("Am I out of milk?") don't contain any full cue.

## Risks / Trade-offs

- [`stocked_at` is approximate: topping up eggs before running out keeps the old date] → This is the conservative reading (the oldest egg really is that old), and the description tells the assistant these are estimates from the camera.
- [A wrong Nova removal can zero an item and reset its age on the next add] → The same risk already exists for counts; the Review screen and hand edits fix it.
- [Excluding beverages hides milk-like drinks Nova files under "beverage"] → Milk is "dairy" in the Nova prompt's categories; the user can still ask "what beverages are oldest?".
- [Two more tools make the assistant's tool list longer] → Six tools are still small; descriptions say when to use each.

## Migration Plan

Deploy with the usual `cdk deploy` (Jayson's OK). Existing rows keep working through the read-time fallback and pick up the new fields on their next change. Rollback is a redeploy of the previous build; the extra attributes are ignored by old code.

## Test strategy

- **Unit (pytest + moto DynamoDB via the existing `aws` fixture):**
  - `test_inventory_rules.py` / `test_save_task.py` / `test_pending_review.py`: `stocked_at` and `peak_quantity` through `quantity_put`, `save_task`, `confirm_pending` and `set_quantity`, one test per fridge-inventory scenario.
  - New `test_fridge_oldest.py` and `test_fridge_low_stock.py`: the pure answer functions with items seeded by `tests/mcp_helpers.put_item` (extended to accept `stocked_at`, `peak_quantity`, `first_seen_at`) and the fixed `NOW`.
  - `test_ask_parse.py` and `test_ask_say.py`: new intents, cue boundaries and spoken sentences, built from result models directly.
- **Contract (in-memory MCP client, real handshake):** `test_mcp_server.py` for the six-tool list and annotations, a happy-path call of each new tool, `limit` validation errors, and the "No camera is linked" error via a context that raises `ToolError`.
- **Front end (Vitest + Testing Library):** `Ask.test.tsx` for the five example buttons and posting "What should I eat first?".
- **Stubbed:** DynamoDB (moto). No Ring, Bedrock or Polly calls are involved. No new fixtures beyond seeded items.
