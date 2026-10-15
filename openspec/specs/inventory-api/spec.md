# inventory-api Specification

## Purpose
Gives the signed-in user's app HTTP access to the fridge inventory, door events, pending changes and corrections, for the linked Ring account only.

## Requirements

### Requirement: Passcode sign-in returns a session token
`POST /api/session` with `{"passcode": "<passcode>"}` SHALL return 200 `{"token": "<token>", "expires_at": "<ISO 8601>", "role": "owner" | "viewer"}` when the passcode matches the configured owner passcode (role `owner`) or the optional configured demo passcode (role `viewer`), with a token valid for 24 hours. Changing either passcode SHALL invalidate the existing tokens of that role only. When no demo passcode is configured, only the owner passcode SHALL sign in. Tokens issued under the earlier 30-day scheme SHALL no longer be accepted.

#### Scenario: Correct passcode
- **WHEN** the configured passcode is `open-sesame` and the body is `{"passcode": "open-sesame"}`
- **THEN** the response is 200 with a non-empty `token`, an `expires_at` 24 hours from now and `role` `"owner"`

#### Scenario: Demo passcode
- **WHEN** the configured demo passcode is `look-only` and the body is `{"passcode": "look-only"}`
- **THEN** the response is 200 with a non-empty `token`, an `expires_at` 24 hours from now and `role` `"viewer"`

#### Scenario: No demo passcode configured
- **WHEN** no demo passcode is configured and the body is `{"passcode": ""}` or any value other than the owner passcode
- **THEN** the response is 401 `{"error": "wrong passcode"}`

#### Scenario: Demo passcode changed
- **WHEN** an owner token and a viewer token were issued and the demo passcode then changes
- **THEN** a request with the old viewer token gets 401 and a request with the owner token still succeeds

#### Scenario: Wrong passcode
- **WHEN** the body is `{"passcode": "guess"}` or has no `passcode`
- **THEN** the response is 401 `{"error": "wrong passcode"}`

#### Scenario: Passcode changed
- **WHEN** a token was issued and the configured passcode then changes
- **THEN** a request with the old token gets 401

#### Scenario: Token one day old
- **WHEN** an owner token was issued at time T and `GET /api/inventory` is called with it at T + 24 h, and again at T + 24 h + 1 s
- **THEN** the first request succeeds and the second gets 401 `{"error": "sign in"}`

#### Scenario: Token from before the change
- **WHEN** a request carries an owner token signed the old way (30-day lifetime, earlier signing key) whose `exp` is still in the future
- **THEN** the response is 401 `{"error": "sign in"}`

### Requirement: Every other API call needs a valid token
Every `/api` route except `POST /api/session` SHALL require `Authorization: Bearer <token>` with a valid, unexpired token, and SHALL answer 401 `{"error": "sign in"}` otherwise. Unknown `/api` routes SHALL answer 404.

#### Scenario: No token
- **WHEN** `GET /api/inventory` is called without an `Authorization` header
- **THEN** the response is 401 `{"error": "sign in"}`

#### Scenario: Tampered or expired token
- **WHEN** the token's signature was altered, or its expiry is in the past
- **THEN** the response is 401

#### Scenario: Unknown route
- **WHEN** a signed-in request calls `GET /api/nope`
- **THEN** the response is 404

#### Scenario: No linked Ring account
- **WHEN** a signed-in request arrives but no Ring account is linked
- **THEN** the response is 409 `{"error": "no camera linked"}`

### Requirement: Viewer tokens are read-only
A token with role `viewer` SHALL be accepted on every `GET` route and SHALL be refused on every write route (`POST /api/pending/{id}/confirm`, `POST /api/pending/{id}/reject`, `PUT /api/items/{key}`, `DELETE /api/events/{id}`) with 403 `{"error": "read-only"}`, changing nothing.

#### Scenario: Viewer write refused
- **WHEN** a viewer token calls `POST /api/pending/{id}/confirm` for an existing pending change, or `PUT /api/items/milk` with `{"quantity": 2}`
- **THEN** the response is 403 `{"error": "read-only"}`, the pending change still exists and the inventory is unchanged

#### Scenario: Viewer delete refused
- **WHEN** a viewer token calls `DELETE /api/events/{id}` for an existing door event
- **THEN** the response is 403 `{"error": "read-only"}` and the event is still listed

#### Scenario: Viewer reads
- **WHEN** a viewer token calls `GET /api/inventory`, `GET /api/events` and `GET /api/pending`
- **THEN** each responds 200 with the same body an owner token gets

### Requirement: Inventory listing
`GET /api/inventory` SHALL return `{"items": [...], "pending_count": n}`, where each item is `{"key", "name", "category", "quantity", "last_changed_at"}`, sorted by category then name, including items with quantity 0.

#### Scenario: Inventory with items
- **WHEN** the inventory has `eggs` (6, dairy), `apple` (3, produce) and `soda can` (0, beverage), and one change is pending
- **THEN** the response lists beverage/soda can, dairy/eggs, produce/apple in that order with their quantities, and `pending_count` is 1

#### Scenario: Empty inventory
- **WHEN** there are no items
- **THEN** the response is `{"items": [], "pending_count": 0}`

### Requirement: Door event listing
`GET /api/events` SHALL return `{"events": [...], "next": <id or null>}`, newest first. Each event has `id`, `opened_at`, `closed_at`, `duration_s`, `status`, `changes`, `pending_count`, and `stills`: 15-minute download links for its stored stills, or `[]` for events older than 7 days.

The range is either `days=<n>` (default 7, max 30, ending now) or `from` and `to`, ISO 8601 instants with `from` inclusive, `to` exclusive, `from` before `to` and at most 31 days apart. When `from` is given, `days` is ignored. With `limit=<n>` (1 to 50) at most `n` events are returned and `next` is the id of the last one when older events remain in the range, else null; `cursor=<id>` returns only events older than that event. Without `limit`, every event in range is returned and `next` is null.

#### Scenario: Recent event with stills
- **WHEN** a `done` door event opened 1 hour ago has 4 stored stills
- **THEN** it is listed with 4 `stills` links that download the images without any other credentials, and with its `changes`

#### Scenario: Old event
- **WHEN** a door event opened 8 days ago and `days=30`
- **THEN** it is listed with `stills: []`

#### Scenario: Range limit
- **WHEN** events exist 2 and 10 days ago and the request has no `days`
- **THEN** only the event from 2 days ago is listed and `next` is null

#### Scenario: Days out of range
- **WHEN** `days=0`, `days=31` or `days=abc`
- **THEN** the response is 400

#### Scenario: One day
- **WHEN** events opened at 03:59, 04:00, 12:00 and 03:59 the next day (UTC), and the request has `from=…T04:00:00.000Z` and `to=` 24 hours later
- **THEN** only the 12:00 and 04:00 events are listed, in that order

#### Scenario: Pages
- **WHEN** 3 events are in range and the request has `limit=2`
- **THEN** the 2 newest are listed and `next` is the id of the second; the same request with `cursor=<next>` lists only the oldest and `next` is null

#### Scenario: Last page exactly full
- **WHEN** 2 events are in range and the request has `limit=2`
- **THEN** both are listed and `next` is null

#### Scenario: Bad range or page
- **WHEN** `from=yesterday`, `from` without `to`, `to` before `from`, a range over 31 days, `limit=0`, `limit=51` or `cursor=nope`
- **THEN** the response is 400

### Requirement: Pending changes and corrections over HTTP
The API SHALL expose `GET /api/pending` (`{"pending": [{"id", "door_event_id", "item", "category", "direction", "quantity", "confidence", "opened_at"}]}`), `POST /api/pending/{id}/confirm` (optional body `{"item", "quantity"}`), `POST /api/pending/{id}/reject`, and `PUT /api/items/{key}` with `{"quantity": n}`. Each write returns the updated item list in the same shape as `GET /api/inventory`.

#### Scenario: Confirm over HTTP
- **WHEN** `POST /api/pending/{id}/confirm` is called for an existing pending change
- **THEN** the response is 200 with the inventory after the change, and the pending change is gone from `GET /api/pending`

#### Scenario: Pending change not found
- **WHEN** confirm or reject is called with an unknown `id`
- **THEN** the response is 404

#### Scenario: Invalid quantity
- **WHEN** `PUT /api/items/milk` has `{"quantity": -1}` or `{"quantity": "two"}`, or confirm has `{"quantity": 0}`
- **THEN** the response is 400 and nothing changes

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

### Requirement: API errors reach the app unchanged
When the app is served through the CDN, every `/api/*` response SHALL reach the app with the status code and JSON body the API sent. The CDN SHALL NOT replace an API error response with the app shell. Because the app uses hash routes, the CDN needs no path fallback: `/` serves the app shell.

#### Scenario: Viewer write refused through the CDN
- **WHEN** a viewer's `POST /api/pending/{id}/confirm` goes through the CDN and the API answers 403 `{"error": "read-only"}`
- **THEN** the app receives status 403 with that JSON body, not 200 with `index.html`

#### Scenario: Not found through the CDN
- **WHEN** the API answers 404 to an `/api/*` request made through the CDN
- **THEN** the app receives status 404 with the API's JSON body

#### Scenario: App shell at the root
- **WHEN** a browser requests `/` from the CDN
- **THEN** it receives `index.html`

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

### Requirement: Delete a door event
`DELETE /api/events/{id}` SHALL delete the door event and every pending change that came from it, and respond 200 `{"id": "<id>"}`. It SHALL NOT change the inventory.

#### Scenario: Delete
- **WHEN** an owner deletes an event that applied "+ milk" and has one pending change
- **THEN** the response is 200, the event is gone from `GET /api/events`, its pending change is gone from `GET /api/pending`, other pending changes remain, and milk's quantity is unchanged

#### Scenario: Unknown event
- **WHEN** the id is unknown, already deleted, or not a door event id
- **THEN** the response is 404 `{"error": "not found"}`
