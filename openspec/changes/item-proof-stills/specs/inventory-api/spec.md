## ADDED Requirements

### Requirement: Proof still links per change
In `GET /api/events`, each item of an event's `changes` SHALL have `proof`: a list of 15-minute download links, one for each saved `proof` index that names one of the event's `still_keys`, in order. It SHALL be `[]` when the change has no `proof`, the event is older than 7 days, or no index names a stored still. Every role SHALL get it.

#### Scenario: Proof links listed
- **WHEN** a recent event has 4 `still_keys` and a change with `proof = [2, 3]`
- **THEN** that change's `proof` holds 2 links, which download `still_keys[2]` and `still_keys[3]` without any other credentials

#### Scenario: Viewer gets proof
- **WHEN** a viewer token lists the same event
- **THEN** that change's `proof` holds the same 2 stills

#### Scenario: Change without proof
- **WHEN** a recent event's change was saved without `proof`
- **THEN** its `proof` is `[]`

#### Scenario: Index past the stored stills
- **WHEN** a change has `proof = [1, 5]` and the event has 4 `still_keys`
- **THEN** its `proof` holds only the link to `still_keys[1]`

#### Scenario: Old event
- **WHEN** an event opened 8 days ago has a change with `proof = [0]`
- **THEN** its `proof` is `[]`
