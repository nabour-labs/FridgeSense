# Spec Delta

## REMOVED Requirements

### Requirement: Setup needs zones and references from clips
**Reason**: The owner can choose a live snapshot or a clip frame for door setup again; setup accepts both.
**Migration**: None. Zones and references keep their `source`; the app notes live ones instead of blocking setup.

## ADDED Requirements

### Requirement: Setup accepts live pictures
`POST /api/door-calibration/run` SHALL run with zones and references of either `source`, `"clip"` or `"live"`. The other setup failures stay as they are.

#### Scenario: Live zone and references set up
- **WHEN** zone "Doors" has `source = "live"`, it has an open and a closed reference with `source = "live"`, and they separate
- **THEN** the response is 200 with a setup zone for "Doors", and the stored setup is replaced

#### Scenario: Mixed sources
- **WHEN** zone "Doors" has `source = "clip"`, its open reference has `source = "live"`, its closed reference has `source = "clip"`, and they separate
- **THEN** the response is 200
