# Spec Delta

## ADDED Requirements

### Requirement: Runs for a paused camera stop before any download
When a workflow run reaches the stills step and its account and device are paused (see the `fridge-monitoring` capability), the step SHALL return outcome `paused` without downloading stills or the clip from Ring, without face detection, and without claiming or recording a door event. The run SHALL then end without analysis, so no inventory change, open/close stat or Nova cost is recorded.

#### Scenario: Paused after the run started
- **WHEN** a run for device D1 started while it was active, and the owner paused D1 before the stills step
- **THEN** the step returns `outcome: "paused"`, no Ring media request is made, no face detection is called, no `DOOR#` item is written, and the run ends in `NoAnalysis`

#### Scenario: Resumed before the stills step
- **WHEN** D1 was paused and resumed before the stills step
- **THEN** the stills step runs the door check as usual
