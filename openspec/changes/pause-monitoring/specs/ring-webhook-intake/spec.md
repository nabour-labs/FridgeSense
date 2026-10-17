# Spec Delta

## ADDED Requirements

### Requirement: Motion for a paused camera is not handed over
For a signed, first-time `motion_detected` event whose account and device are paused (see the `fridge-monitoring` capability), the system SHALL answer 200 `{"ok": true, "paused": true}`, keep the `meta.request_id` as seen, log `motion_paused` with the account ID, device ID and event time, and SHALL NOT call the motion handler. If the paused state cannot be read, the event SHALL be handed over as if active.

#### Scenario: Paused camera
- **WHEN** the recorded motion fixture arrives signed for the first time and `ava1.ring.device.XXXYYY` of `ava1.ring.account.XXXYYY` is paused
- **THEN** the response is 200 `{"ok": true, "paused": true}`, the motion handler is not called, and a `motion_paused` log line has that account ID, device ID and `timestamp_ms = 1786715596787`

#### Scenario: Paused and delivered again
- **WHEN** the same signed payload arrives a second time while paused
- **THEN** the response is 200 with `"duplicate": true` and the motion handler is not called

#### Scenario: Active camera
- **WHEN** the same fixture arrives and the device was resumed or never paused
- **THEN** the motion handler receives the event as before

#### Scenario: Paused state unreadable
- **WHEN** reading the paused state raises an error
- **THEN** the motion handler receives the event and the response is 200 `{"ok": true}`

#### Scenario: Status events while paused
- **WHEN** a signed `device_offline` event arrives for a paused device
- **THEN** the status change is still recorded and the response is 200
