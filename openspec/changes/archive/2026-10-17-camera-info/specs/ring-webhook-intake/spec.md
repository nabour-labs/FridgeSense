# Spec Delta

## ADDED Requirements

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
