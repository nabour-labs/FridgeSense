# ring-device-discovery Specification

## Purpose
Finds the linked account's Ring cameras so FridgeSense knows which device watches the fridge and can show it to the user.

## Requirements

### Requirement: Devices saved after linking
After a successful link, the system SHALL call `GET /v1/devices` and store each returned device's ID and `attributes.name` under the linked account ID, replacing the account's previous device list.

#### Scenario: One camera returned
- **WHEN** linking completes and `/v1/devices` returns one device with `id = "ava1.ring.device.D1"` and `attributes.name = "Fridge Cam"`
- **THEN** the store holds that device under account `ava1.ring.account.A1`, and the success page lists "Fridge Cam"

#### Scenario: Device removed since last link
- **WHEN** the account previously had devices D1 and D2 and `/v1/devices` now returns only D1
- **THEN** only D1 is stored for the account

#### Scenario: Device list unavailable
- **WHEN** linking completes but `/v1/devices` answers 5xx
- **THEN** linking still counts as successful, the stored device list is unchanged, and the success page says devices could not be loaded yet

### Requirement: Device list on demand
The system SHALL provide a command that refreshes and prints the linked account's devices (ID and name), for setup and debugging.

#### Scenario: Listing devices from the command line
- **WHEN** the device command runs with a linked account and `/v1/devices` returns devices D1 "Fridge Cam" and D2 "Front Door"
- **THEN** it prints one line per device with its ID and name, stores both, and exits 0

#### Scenario: No linked account
- **WHEN** the device command runs and the token store is empty
- **THEN** it prints that no Ring account is linked and exits 1
