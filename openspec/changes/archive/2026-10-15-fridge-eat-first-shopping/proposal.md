# Proposal

## Why

FridgeSense today answers "what is in the fridge?", but not the two questions that make it worth having: "what should I eat before it goes bad?" and "what do I need to buy?". Answering them turns an inventory camera into a food-waste and shopping helper, which is a much stronger impact story for judges. The data is already there (every item records when it changed); we only need to keep two more facts per item and expose them as tools.

**Tracks:** Alexa+ (two new MCP tools a voice assistant can call: "Alexa, what should I eat first?", "Alexa, what do I need to buy?") and Ring (more value from each door opening the camera sees).

## What Changes

- Inventory items keep `stocked_at` (when the current stock went in, after being out) and `peak_quantity` (the most held since then). Confident changes, confirmed changes and hand-set counts all maintain them. Items saved before this change fall back to `first_seen_at` and the current quantity.
- New MCP tool `oldest_items(category?, limit?)`: items in stock, oldest first, with how many days they have been in the fridge. Long-life categories (condiment, frozen, beverage) are left out unless that category is asked for.
- New MCP tool `low_stock()`: items that ran out in the last 30 days, newest first, plus items down to a quarter or less of their peak count since restocking.
- The MCP server lists six read-only tools instead of four, and its instructions mention the new questions.
- The Ask screen's keyword fallback recognises "eat first / going bad / oldest" and "need to buy / shopping list / running low" questions and speaks short answers. The Nova assistant picks up the new tools automatically from `tools/list`.
- The Ask screen gets two more example questions: "What should I eat first?" and "What do I need to buy?".
- README "Voice and MCP" section lists the new tools and example questions.

**Out of scope:** expiry dates or shelf-life tables per item, a persisted or editable shopping list, notifications or a daily digest, a new PWA screen for these lists, changing the Nova prompt or analysis, and backfilling `stocked_at` / `peak_quantity` on existing items (the fallback covers them).

## Capabilities

### New Capabilities

None. Both tools belong to the existing `fridge-mcp` capability.

### Modified Capabilities

- `fridge-inventory`: items also track `stocked_at` and `peak_quantity`.
- `fridge-mcp`: the tool list grows to six; new requirements for `oldest_items` and `low_stock`.
- `fridge-ask`: two new intents in the matching order, with their spoken answers.
- `inventory-app`: the Ask screen shows five example questions.
- `fridge-assistant`: the assistant now offers six tools (the requirement already says "exactly the server's tools"; only the scenario's list changes).

## Impact

- `backend/src/fridgesense/inventory.py` (`quantity_put`, `set_quantity`): two more item attributes. No table or index changes; reads stay one `ITEM#` query.
- `backend/src/fridgesense/fridge_answers.py`: two new pure answer functions and result models.
- `backend/src/fridgesense/mcp_server.py`: two tools, updated instructions.
- `backend/src/fridgesense/ask.py`: two intents and spoken answers.
- `pwa/src/screens/Ask.tsx`: example list.
- Tests under `backend/tests/` and `pwa/src/screens/Ask.test.tsx`. No new dependencies, no infra changes, no added AWS cost (no extra Bedrock calls; the Ask assistant may make one more tool call on these questions).
