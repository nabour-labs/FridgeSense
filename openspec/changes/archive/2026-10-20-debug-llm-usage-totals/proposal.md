# Proposal

## Why

Every LLM call's tokens and cost are already added to a daily total per account (`USAGE#<YYYY-MM-DD>`), but nothing shows those totals. The owner pays for Nova out of pocket and today has to read the logs or the table to see what a day cost. The Debug page already lists one day's motions, so it is the natural place to show that day's LLM spend.

## What Changes

- **New route.** `GET /api/debug/usage?day=YYYY-MM-DD` (owner only, like the other debug routes) returns that household day's totals: `{"day", "calls", "input_tokens", "output_tokens", "total_tokens", "usd"}`. `input_tokens` counts all input, cached or not (uncached + cache read + cache write); `total_tokens = input_tokens + output_tokens`. A day with no calls returns zeros. A missing or malformed `day` returns 400.
- **Debug page card.** Below the day picker, a "LLM usage" card shows the picked day's total tokens, input tokens, output tokens and cost in USD. It reloads when the day changes.

Out of scope:
- Totals over a range of days, per-source (analysis vs assistant) splits, or charts.
- Changing how usage is recorded.

Hackathon tracks: **AWS Builder** (visible Bedrock spend per day).

## Capabilities

### Modified Capabilities

- `llm-usage-tracking`: the daily totals can be read through the API and are shown on the Debug page.

## Impact

- Backend: `handlers/api.py` gets `GET /api/debug/usage`. No data changes: it reads the existing `USAGE#<date>` item.
- PWA: `api/types.ts` (`UsageTotals`), `api/client.ts` (`debugUsage`), `screens/Debug.tsx` (usage card).
- Infra: none; the route goes through the existing `/api/{proxy+}` integration.
- Cost: one DynamoDB read per Debug page day load.
