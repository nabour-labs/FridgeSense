# Spec Delta

## ADDED Requirements

### Requirement: Failed hand-over is retried by Ring
If the motion handler fails for a first-time event, the system SHALL forget that event's `meta.request_id` and answer 500, so Ring's retry is handled as a first delivery.

#### Scenario: Motion handler fails
- **WHEN** a signed, first-time motion event arrives and the motion handler raises an error
- **THEN** the response is 500 and no record for that `request_id` remains in the store

#### Scenario: Ring retries after a failed hand-over
- **WHEN** the same signed payload arrives again after a 500 and the motion handler now succeeds
- **THEN** the response is 200 with `{"ok": true}` (not a duplicate) and the motion handler received the event
