# Spec Delta

## Purpose

Gives the signed-in user's app HTTP access to the fridge inventory, door events, pending changes and corrections, for the linked Ring account only.

## ADDED Requirements

### Requirement: Passcode sign-in returns a session token
`POST /api/session` with `{"passcode": "<passcode>"}` SHALL return 200 `{"token": "<token>", "expires_at": "<ISO 8601>"}` when the passcode matches the configured one, with a token valid for 30 days. Changing the passcode SHALL invalidate existing tokens.

#### Scenario: Correct passcode
- **WHEN** the configured passcode is `open-sesame` and the body is `{"passcode": "open-sesame"}`
- **THEN** the response is 200 with a non-empty `token` and an `expires_at` 30 days from now

#### Scenario: Wrong passcode
- **WHEN** the body is `{"passcode": "guess"}` or has no `passcode`
- **THEN** the response is 401 `{"error": "wrong passcode"}`

#### Scenario: Passcode changed
- **WHEN** a token was issued and the configured passcode then changes
- **THEN** a request with the old token gets 401

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

### Requirement: Inventory listing
`GET /api/inventory` SHALL return `{"items": [...], "pending_count": n}`, where each item is `{"key", "name", "category", "quantity", "last_changed_at"}`, sorted by category then name, including items with quantity 0.

#### Scenario: Inventory with items
- **WHEN** the inventory has `eggs` (6, dairy), `apple` (3, produce) and `soda can` (0, beverage), and one change is pending
- **THEN** the response lists beverage/soda can, dairy/eggs, produce/apple in that order with their quantities, and `pending_count` is 1

#### Scenario: Empty inventory
- **WHEN** there are no items
- **THEN** the response is `{"items": [], "pending_count": 0}`

### Requirement: Door event listing
`GET /api/events?days=<n>` (default 7, max 30) SHALL return `{"events": [...]}`, newest first. Each event has `id`, `opened_at`, `closed_at`, `duration_s`, `status`, `changes`, `pending_count`, and `stills`: 15-minute download links for its stored stills, or `[]` for events older than 7 days.

#### Scenario: Recent event with stills
- **WHEN** a `done` door event opened 1 hour ago has 4 stored stills
- **THEN** it is listed with 4 `stills` links that download the images without any other credentials, and with its `changes`

#### Scenario: Old event
- **WHEN** a door event opened 8 days ago and `days=30`
- **THEN** it is listed with `stills: []`

#### Scenario: Range limit
- **WHEN** events exist 2 and 10 days ago and the request has no `days`
- **THEN** only the event from 2 days ago is listed

#### Scenario: Days out of range
- **WHEN** `days=0`, `days=31` or `days=abc`
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
