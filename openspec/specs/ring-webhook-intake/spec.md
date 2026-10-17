# ring-webhook-intake Specification

## Purpose
Receives Ring webhook calls safely: only signed calls are accepted, each event is handled at most once, and Ring always gets a fast answer that never disables the webhook.

## Requirements

### Requirement: Signature verified before anything else
`POST /ring/webhook` SHALL compute `"sha256=" + hex(HMAC_SHA256(hmac_key, raw_body))` over the exact bytes received and compare it in constant time with the `X-Signature` header before parsing the body.

#### Scenario: Valid signature
- **WHEN** a recorded `motion_detected` payload arrives with a correct `X-Signature`
- **THEN** the response is 200 with body `{"ok": true}`

#### Scenario: Invalid signature
- **WHEN** the payload arrives with `X-Signature: sha256=` followed by a wrong hex digest
- **THEN** the response is 401, the body is not parsed, and nothing is stored

#### Scenario: Missing signature header
- **WHEN** the payload arrives without an `X-Signature` header
- **THEN** the response is 401 and nothing is stored

#### Scenario: Base64-encoded body from the gateway
- **WHEN** the gateway delivers the body base64-encoded (`isBase64Encoded: true`)
- **THEN** the signature is checked against the decoded bytes, and a correct signature is accepted

#### Scenario: Signing key not configured
- **WHEN** the HMAC key is missing from config
- **THEN** the response is 503 (so Ring retries later) and nothing is stored

### Requirement: Duplicate deliveries handled once
The system SHALL record each accepted `meta.request_id` under its `meta.account_id`, and a later call with the same `request_id` SHALL be acknowledged without being handled again. Records SHALL expire after 7 days.

#### Scenario: First delivery
- **WHEN** a signed payload with `meta.request_id = "R1"` arrives for the first time
- **THEN** a record for account `meta.account_id` and request `R1` is stored with an expiry 7 days ahead, and the event is handled

#### Scenario: Repeated delivery
- **WHEN** a signed payload with `meta.request_id = "R1"` arrives again
- **THEN** the response is 200 with `{"ok": true, "duplicate": true}` and the event is not handled a second time

### Requirement: Never a 4xx for a signed call
Once the signature is valid, the system SHALL answer 200 for unknown event types and for bodies it cannot parse, logging them instead of rejecting them.

#### Scenario: Unknown event type
- **WHEN** a signed payload has `data.type = "button_press"`
- **THEN** the response is 200 and the event is logged as ignored

#### Scenario: Malformed JSON with a valid signature
- **WHEN** the signed body is not valid JSON or lacks `meta.request_id`
- **THEN** the response is 200 and the problem is logged

### Requirement: Motion events recorded for the pipeline
For a signed, first-time `motion_detected` event, the system SHALL log and hand over the account ID (`meta.account_id`), device ID (`data.attributes.source`), event time (`data.attributes.timestamp`, epoch ms) and sub type (`data.attributes.sub_type`) to the motion handler.

#### Scenario: Motion event handed over
- **WHEN** the recorded motion fixture arrives signed for the first time
- **THEN** the motion handler receives `account_id = "ava1.ring.account.XXXYYY"`, `device_id = "ava1.ring.device.XXXYYY"`, `timestamp_ms = 1786715596787` and `sub_type = "motion"`

#### Scenario: App integration added
- **WHEN** a signed `app_integration_added` event arrives
- **THEN** the response is 200 and the event is logged with its account ID

### Requirement: Failed hand-over is retried by Ring
If the motion handler fails for a first-time event, the system SHALL forget that event's `meta.request_id` and answer 500, so Ring's retry is handled as a first delivery.

#### Scenario: Motion handler fails
- **WHEN** a signed, first-time motion event arrives and the motion handler raises an error
- **THEN** the response is 500 and no record for that `request_id` remains in the store

#### Scenario: Ring retries after a failed hand-over
- **WHEN** the same signed payload arrives again after a 500 and the motion handler now succeeds
- **THEN** the response is 200 with `{"ok": true}` (not a duplicate) and the motion handler received the event

### Requirement: Device online and offline events recorded
For a signed, first-time `device_online` or `device_offline` event, the system SHALL store a status change for `meta.account_id` and device `data.attributes.source`: `online` true or false and the event time `data.attributes.timestamp` (epoch ms), with source `webhook`. The response SHALL be 200 `{"ok": true}`, including when the payload lacks those fields.

#### Scenario: Device goes offline
- **WHEN** the recorded `device_offline` fixture (device `ava1.ring.device.XXXYYY`, timestamp `1771025206000`) arrives signed for the first time
- **THEN** the response is 200 `{"ok": true}` and a status change `{online: false, at_ms: 1771025206000, source: "webhook"}` is stored for account `ava1.ring.account.XXXYYY` and device `ava1.ring.device.XXXYYY`

#### Scenario: Device comes online
- **WHEN** the recorded `device_online` fixture arrives signed for the first time
- **THEN** the response is 200 and a status change with `online: true` and the fixture's timestamp is stored for that account and device

#### Scenario: Repeated status delivery
- **WHEN** the same `device_offline` payload (same `meta.request_id`) arrives a second time
- **THEN** the response is 200 `{"ok": true, "duplicate": true}` and only one status change is stored

#### Scenario: Status event without a timestamp
- **WHEN** a signed `device_online` payload has no `data.attributes.timestamp`
- **THEN** the response is 200, nothing is stored, and the payload is logged as malformed

#### Scenario: Bad signature on a status event
- **WHEN** a `device_offline` payload arrives with a wrong `X-Signature`
- **THEN** the response is 401 and no status change is stored
