# Spec Delta

## MODIFIED Requirements

### Requirement: Ask a fridge question
`POST /api/ask` with `{"question": "<text>"}` SHALL return 200 `{"intent", "answer", "data", "source", "audio"}` for the linked account:
- `source` is `"agent"` when the fridge assistant answered, or `"keywords"` when the keyword rules answered.
- `intent` is `"agent"` for assistant answers, otherwise one of `find_item`, `get_inventory`, `fridge_activity`, `last_opened` or `unknown`.
- `answer` is the spoken sentence.
- `data` is `{"tools": [<tool names called>]}` for assistant answers. For keyword answers it is the structured result, the same shape as the matching MCP tool's output, or `null` for `unknown`.
- `audio` is the spoken answer as base64 MP3, or `null`.

The route is read-only, so owner and viewer tokens are both accepted. "Today" uses the household time zone.

#### Scenario: Do I have milk
- **WHEN** the assistant is off, a signed-in request posts `{"question": "Do I have milk?"}`, and milk has count 1, changed 2 minutes ago
- **THEN** the response is 200 with `source` `"keywords"`, `intent` `"find_item"`, `answer` `"Yes, you have 1 milk, changed 2 minutes ago."` and `data` `{"query": "milk", "in_fridge": true, "total_count": 1, "matches": [{"name": "Milk", "count": 1, "minutes_ago": 2, …}]}`

#### Scenario: Assistant answers
- **WHEN** the assistant is on and answers "Yes, you have 1 milk, added 2 minutes ago." after calling `find_item`
- **THEN** the response is 200 with `source` `"agent"`, `intent` `"agent"`, that `answer`, and `data` `{"tools": ["find_item"]}`

#### Scenario: Viewer can ask
- **WHEN** a viewer token posts `{"question": "What's in my fridge?"}`
- **THEN** the response is 200, not 403

#### Scenario: Unknown question
- **WHEN** the assistant is off and the body is `{"question": "Play some jazz"}`
- **THEN** the response is 200 with `intent` `"unknown"`, the hint as `answer` and `data` `null`

#### Scenario: Activity in the household time zone
- **WHEN** the assistant is off, the household time zone is America/Toronto, it is 01:00 local, there was a door event at 23:30 local the previous day, and the question is "How many times did we open the fridge today?"
- **THEN** `data.opens` is 0 and the answer is "The fridge hasn't been opened today."

## ADDED Requirements

### Requirement: Ask falls back to keywords
`POST /api/ask` SHALL use the fridge assistant only when `ASK_AGENT` is `"on"` and the app secret has a non-empty `mcp_key`. When the assistant is not used, or reports any failure, the route SHALL answer with the keyword rules and `source` `"keywords"`, and SHALL still return 200.

#### Scenario: Assistant off by setting
- **WHEN** `ASK_AGENT` is `"off"` (or unset) and the question is "Do I have milk?"
- **THEN** Converse is not called and the response has `source` `"keywords"` and `intent` `"find_item"`

#### Scenario: No MCP key
- **WHEN** `ASK_AGENT` is `"on"` but `mcp_key` is empty
- **THEN** Converse is not called and the response has `source` `"keywords"`

#### Scenario: Assistant fails
- **WHEN** the assistant reports `timeout`, `bedrock_error`, `mcp_error`, `too_many_rounds`, `empty_answer` or `over_budget` for "Do I have milk?"
- **THEN** the response is 200 with `source` `"keywords"`, `intent` `"find_item"` and the keyword answer

### Requirement: Ask returns spoken audio
`POST /api/ask` SHALL synthesize every answer, from either source, with Amazon Polly (neural engine, voice `ASK_VOICE`, default `Joanna`, MP3 output) and return it base64-encoded as `audio`. If Polly fails, `audio` SHALL be `null` and the response SHALL still be 200 with the answer.

#### Scenario: Audio returned
- **WHEN** the answer is "You're out of butter." and Polly returns MP3 bytes `b"ID3fake"`
- **THEN** Polly was asked for `Text` "You're out of butter.", `Engine` `"neural"`, `VoiceId` `"Joanna"`, `OutputFormat` `"mp3"`, and `audio` is `"SUQzZmFrZQ=="`

#### Scenario: Polly fails
- **WHEN** Polly raises `ServiceFailureException` (or access is denied)
- **THEN** the response is 200 with the answer and `audio` `null`
