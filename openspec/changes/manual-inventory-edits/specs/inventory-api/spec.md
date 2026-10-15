# Spec Delta

## ADDED Requirements

### Requirement: Add an item over HTTP
`POST /api/items` with `{"name": <string>, "category": <string>, "quantity": <whole number ≥ 1>}` SHALL add the item under the fridge-inventory rules and return 200 with the inventory, in the same shape as `GET /api/inventory`. It SHALL answer 400 and change nothing when the body is not a JSON object, or when a field is missing or breaks the rules. The error is `{"error": "name must be 1 to 60 characters"}`, `{"error": "unknown category"}` or `{"error": "quantity must be a whole number of 1 or more"}`.

#### Scenario: Add over HTTP
- **WHEN** an owner token posts `{"name": "Butter", "category": "dairy", "quantity": 1}` and there is no butter
- **THEN** the response is 200 and its `items` include `{"key": "butter", "name": "Butter", "category": "dairy", "quantity": 1, "last_changed_at": <now>}`

#### Scenario: Add to an existing item over HTTP
- **WHEN** `eggs` has quantity 4 and an owner token posts `{"name": "eggs", "category": "dairy", "quantity": 6}`
- **THEN** the response is 200 and `eggs` has quantity 10

#### Scenario: Bad add body
- **WHEN** the body is `not json`, `{}`, `{"name": "", "category": "dairy", "quantity": 1}`, `{"name": "Butter", "category": "sweets", "quantity": 1}`, `{"name": "Butter", "category": "dairy", "quantity": 0}` or `{"name": "Butter", "category": "dairy", "quantity": "2"}`
- **THEN** the response is 400 with the matching error and the inventory is unchanged

### Requirement: Edit an item over HTTP
`PUT /api/items/{key}` SHALL accept `{"quantity": n}` with optional `"name"` and `"category"`, and apply them under the fridge-inventory rules. On success it SHALL return 200 with the inventory. A body with only `quantity` SHALL behave as before. It SHALL answer:
- 400 for a bad field, with the same errors as `POST /api/items` except `quantity`, which may be 0
- 404 `{"error": "not found"}` when `name` is given for an item that doesn't exist
- 409 `{"error": "item exists"}` when the new name belongs to another item

#### Scenario: Rename over HTTP
- **WHEN** `bottle` has quantity 1 and an owner token calls `PUT /api/items/bottle` with `{"quantity": 1, "name": "Oat Milk", "category": "dairy"}`
- **THEN** the response is 200, its `items` include `{"key": "oat milk", "name": "Oat Milk", "category": "dairy", "quantity": 1, …}` and no item has key `bottle`

#### Scenario: Quantity only, as before
- **WHEN** `eggs` has quantity 18 and an owner token calls `PUT /api/items/eggs` with `{"quantity": 12}`
- **THEN** the response is 200 and `eggs` has quantity 12 with its name and category unchanged

#### Scenario: Key with spaces
- **WHEN** an owner token calls `PUT /api/items/oat%20milk` with `{"quantity": 2, "category": "beverage"}` and `oat milk` exists
- **THEN** the response is 200 and `oat milk` has quantity 2 and category `beverage`

#### Scenario: Rename clash over HTTP
- **WHEN** both `bottle` and `oat milk` exist and `PUT /api/items/bottle` has `{"quantity": 1, "name": "oat milk"}`
- **THEN** the response is 409 `{"error": "item exists"}` and both items are unchanged

#### Scenario: Rename unknown item over HTTP
- **WHEN** there is no `yogurt` and `PUT /api/items/yogurt` has `{"quantity": 1, "name": "Greek Yogurt"}`
- **THEN** the response is 404 `{"error": "not found"}` and no item is created

#### Scenario: Bad edit fields
- **WHEN** `PUT /api/items/eggs` has `{"quantity": 6, "name": "   "}` or `{"quantity": 6, "category": "sweets"}`
- **THEN** the response is 400 with the matching error and `eggs` is unchanged

### Requirement: Delete an item over HTTP
`DELETE /api/items/{key}` SHALL delete the item under the fridge-inventory rules and return 200 with the inventory. It SHALL answer 404 `{"error": "not found"}` when the item doesn't exist.

#### Scenario: Delete over HTTP
- **WHEN** `mystery jar` exists and an owner token calls `DELETE /api/items/mystery%20jar`
- **THEN** the response is 200 and no item in `items` has key `mystery jar`

#### Scenario: Delete unknown item over HTTP
- **WHEN** there is no `yogurt` and an owner token calls `DELETE /api/items/yogurt`
- **THEN** the response is 404 `{"error": "not found"}`

#### Scenario: Delete without a token
- **WHEN** `DELETE /api/items/eggs` is called without an `Authorization` header
- **THEN** the response is 401 `{"error": "sign in"}` and `eggs` still exists

## MODIFIED Requirements

### Requirement: Viewer tokens are read-only
A token with role `viewer` SHALL be accepted on every `GET` route and SHALL be refused on every write route (`POST /api/pending/{id}/confirm`, `POST /api/pending/{id}/reject`, `POST /api/items`, `PUT /api/items/{key}`, `DELETE /api/items/{key}`, `DELETE /api/events/{id}`) with 403 `{"error": "read-only"}`, changing nothing.

#### Scenario: Viewer write refused
- **WHEN** a viewer token calls `POST /api/pending/{id}/confirm` for an existing pending change, or `PUT /api/items/milk` with `{"quantity": 2}`
- **THEN** the response is 403 `{"error": "read-only"}`, the pending change still exists and the inventory is unchanged

#### Scenario: Viewer delete refused
- **WHEN** a viewer token calls `DELETE /api/events/{id}` for an existing door event
- **THEN** the response is 403 `{"error": "read-only"}` and the event is still listed

#### Scenario: Viewer cannot add or delete items
- **WHEN** a viewer token calls `POST /api/items` with `{"name": "Butter", "category": "dairy", "quantity": 1}`, or `DELETE /api/items/eggs` while `eggs` exists
- **THEN** each response is 403 `{"error": "read-only"}`, no butter is created and `eggs` still exists

#### Scenario: Viewer reads
- **WHEN** a viewer token calls `GET /api/inventory`, `GET /api/events` and `GET /api/pending`
- **THEN** each responds 200 with the same body an owner token gets
