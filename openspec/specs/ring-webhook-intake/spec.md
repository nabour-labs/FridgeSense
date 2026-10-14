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
