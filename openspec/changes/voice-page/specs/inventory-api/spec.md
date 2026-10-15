# Spec Delta

## ADDED Requirements

### Requirement: Ask a fridge question
`POST /api/ask` with `{"question": "<text>"}` SHALL return 200 `{"intent", "answer", "data"}` for the linked account:
- `intent` is one of `find_item`, `get_inventory`, `fridge_activity`, `last_opened` or `unknown`.
- `answer` is the spoken sentence.
- `data` is that answer's structured result, the same shape as the matching MCP tool's output, or `null` for `unknown`.

The route is read-only, so owner and viewer tokens are both accepted. "Today" uses the household time zone.

#### Scenario: Do I have milk
- **WHEN** a signed-in request posts `{"question": "Do I have milk?"}` and milk has count 1, changed 2 minutes ago
- **THEN** the response is 200 with `intent` `"find_item"`, `answer` `"Yes, you have 1 milk, changed 2 minutes ago."` and `data` `{"query": "milk", "in_fridge": true, "total_count": 1, "matches": [{"name": "Milk", "count": 1, "minutes_ago": 2, …}]}`

#### Scenario: Viewer can ask
- **WHEN** a viewer token posts `{"question": "What's in my fridge?"}`
- **THEN** the response is 200 with `intent` `"get_inventory"`, not 403

#### Scenario: Unknown question
- **WHEN** the body is `{"question": "Play some jazz"}`
- **THEN** the response is 200 with `intent` `"unknown"`, the hint as `answer` and `data` `null`

#### Scenario: Activity in the household time zone
- **WHEN** the household time zone is America/Toronto, it is 01:00 local, there was a door event at 23:30 local the previous day, and the question is "How many times did we open the fridge today?"
- **THEN** `data.opens` is 0 and the answer is "The fridge hasn't been opened today."

### Requirement: Ask rejects bad bodies
`POST /api/ask` SHALL answer 400 `{"error": "question required"}` and read nothing from the table in these cases:
- the body is not JSON
- `question` is missing or not a string
- `question` is blank after trimming
- `question` is longer than 200 characters

#### Scenario: Missing question
- **WHEN** the body is `{}`, `{"question": 5}`, `{"question": "   "}` or `not json`
- **THEN** the response is 400 `{"error": "question required"}`

#### Scenario: Too long
- **WHEN** `question` is 201 characters long
- **THEN** the response is 400 `{"error": "question required"}`

#### Scenario: No token
- **WHEN** `POST /api/ask` is called without an `Authorization` header
- **THEN** the response is 401 `{"error": "sign in"}`
