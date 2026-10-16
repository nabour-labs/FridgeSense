## MODIFIED Requirements

### Requirement: Deciding rule in the door trace
`door.json` SHALL have `rule = {"source", "ran_at", "zones", "references"}`. Each zone is `{"zone", "box", "feature", "direction", "threshold", "margin", "baseline_key"}`. For `setup`, each zone's baseline is stored as `baseline-<zone>.png`. Each door reference the setup learned from is stored as `door-ref-<id>.jpg`, listed with its `status` and `box`. For `default`, `ran_at`, `margin` and `baseline_key` are null and `references` is empty.

#### Scenario: Setup rule
- **WHEN** the device has a setup run at `2026-10-15T20:00:00Z` with 2 zones and 3 door references (2 closed, 1 open)
- **THEN** `rule.source = "setup"`, `rule.ran_at = "2026-10-15T20:00:00Z"`, both zones list feature, direction, threshold, margin and a `baseline_key` whose PNG exists, and `rule.references` has 3 entries whose `key` objects exist

#### Scenario: Default rule
- **WHEN** the device has no setup
- **THEN** `rule.source = "default"`, the zones are the `DOOR_ZONES` boxes with `feature = "blue"`, `direction = "above"` and the `DOOR_THRESHOLD`, and `rule.references = []`

#### Scenario: Setup lookup failed
- **WHEN** loading the setup raises an error and the default rule is used
- **THEN** `rule.source = "default"`
