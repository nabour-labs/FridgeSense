# Spec Delta

## ADDED Requirements

### Requirement: Door setup mismatch warning
When the device's `suspect_streak` is 3 or more, `GET /api/warnings` SHALL list `{"code": "door_setup_mismatch", "message": "Open/close detection doesn't match the camera's recordings, so the fridge light is used instead. Replace the door references with frames from recent clips and run setup again."}`. It SHALL come after every other warning. When the streak cannot be read, the warning SHALL be left out and the response SHALL still be 200.

#### Scenario: Three suspect events
- **WHEN** the device's `suspect_streak` is 3
- **THEN** `warnings` includes `door_setup_mismatch` with that message

#### Scenario: Two suspect events
- **WHEN** the device's `suspect_streak` is 2
- **THEN** `door_setup_mismatch` is not listed

#### Scenario: Listed last
- **WHEN** setup never ran and the `suspect_streak` is 4
- **THEN** `warnings` lists `door_setup_missing` before `door_setup_mismatch`

#### Scenario: Cleared by setup
- **WHEN** the streak was 3 and the owner runs setup successfully
- **THEN** `door_setup_mismatch` is no longer listed

#### Scenario: Streak unreadable
- **WHEN** reading the streak raises a table error
- **THEN** the response is 200 without `door_setup_mismatch`
