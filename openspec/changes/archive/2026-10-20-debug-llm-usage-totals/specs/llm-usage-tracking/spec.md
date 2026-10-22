## ADDED Requirements

### Requirement: Daily totals readable by the owner
`GET /api/debug/usage?day=<YYYY-MM-DD>` SHALL return 200 with the totals of the item `ACCOUNT#<account_id>` / `USAGE#<day>` as `{"day": "<day>", "calls": <int>, "input_tokens": <int>, "output_tokens": <int>, "total_tokens": <int>, "usd": <number>}`, where `input_tokens = input_tokens + cache_read_tokens + cache_write_tokens` of the item and `total_tokens = input_tokens + output_tokens`. A day with no item SHALL return the same shape with every count 0 and `usd = 0`. Only the owner role may read it.

#### Scenario: Day with calls
- **WHEN** item `USAGE#2026-10-20` for the linked account has `calls = 2`, `input_tokens = 2380`, `cache_read_tokens = 2000`, `cache_write_tokens = 0`, `output_tokens = 136`, `usd = 0.001324` and the owner requests `day=2026-10-20`
- **THEN** the response is 200 with `{"day": "2026-10-20", "calls": 2, "input_tokens": 4380, "output_tokens": 136, "total_tokens": 4516, "usd": 0.001324}`

#### Scenario: Day without calls
- **WHEN** the owner requests `day=2026-10-19` and no usage item exists for that day
- **THEN** the response is 200 with `{"day": "2026-10-19", "calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "usd": 0}`

#### Scenario: Another account's totals are not read
- **WHEN** only account `acc-2` has a usage item for 2026-10-20 and the linked account is a different one
- **THEN** the owner's request for `day=2026-10-20` returns zeros

#### Scenario: Bad day
- **WHEN** the owner requests with `day` missing, `day=yesterday` or `day=2026-13-01`
- **THEN** the response is 400

#### Scenario: Not the owner
- **WHEN** a viewer or user token requests the route
- **THEN** the response is 403 (`read-only` for a viewer, `admin only` for a user), and with no token 401

### Requirement: Debug page shows the day's LLM usage
Below the day picker, the Debug page SHALL show an "LLM usage" card for the picked day with "Total tokens", "Input tokens", "Output tokens" (whole numbers with thousands separators) and "Cost" (USD, `$` and 4 decimals). It SHALL load the picked day (as `YYYY-MM-DD`) and reload when the day changes. While loading it shows a placeholder; if the request fails it shows the no-data message and the rest of the page still works.

#### Scenario: Totals shown
- **WHEN** the API returns `input_tokens = 4380`, `output_tokens = 136`, `total_tokens = 4516`, `usd = 0.001324` for today
- **THEN** the card shows Total tokens `4,516`, Input tokens `4,380`, Output tokens `136` and Cost `$0.0013`, below the day picker

#### Scenario: Picking another day
- **WHEN** the owner picks 2026-10-19 in the day picker
- **THEN** the usage for `day=2026-10-19` is requested and shown

#### Scenario: Usage fails to load
- **WHEN** the usage request fails and the motions request succeeds
- **THEN** the card shows the no-data message and the motions list is still shown
