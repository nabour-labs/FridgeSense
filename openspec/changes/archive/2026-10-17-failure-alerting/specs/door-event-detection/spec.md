# Spec Delta

## MODIFIED Requirements

### Requirement: No door event left analyzing
Once a door event has been recorded with `status = "analyzing"`, the workflow run SHALL end with that event in a final status. If the analysis or the save of its changes fails for any reason, the event's `status` SHALL become `"analysis_failed"`, the failure SHALL be logged as `analysis_failed` with the error name, and the inventory SHALL be unchanged by that run. After marking the event failed, the run SHALL end as a failed execution so the failed-run alarm counts it.

#### Scenario: Save fails
- **WHEN** the save step of a run fails with any error (for example a DynamoDB error or a task timeout)
- **THEN** the run goes to the mark-failed step and the door event's `status` is `"analysis_failed"`

#### Scenario: Analysis fails
- **WHEN** the analyze step fails with any error after its retries
- **THEN** the run goes to the mark-failed step and the door event's `status` is `"analysis_failed"`

#### Scenario: Failed run ends as a failed execution
- **WHEN** the mark-failed step finishes
- **THEN** the run moves to a `Fail` state named `AnalysisFailed` with error `AnalysisFailed`, so the execution's status is `FAILED`

## ADDED Requirements

### Requirement: Window and stills steps retried and caught
The find-window and fetch-stills steps SHALL retry a task failure (`States.TaskFailed`) twice, 10 s apart then 20 s. Any error left after the retries SHALL send the run to the mark-failed step with the error at `$.error`. The mark-failed step SHALL set the door event's `status` to `"analysis_failed"` only when the run already has a `door_sk`; without one it SHALL only log `analysis_failed` with the error name and account ID.

#### Scenario: Window step retries and is caught
- **WHEN** the state machine is synthesized
- **THEN** `FindWindow` has a retry on `["States.TaskFailed"]` with `IntervalSeconds = 10`, `MaxAttempts = 2`, `BackoffRate = 2`, and a catch on `["States.ALL"]` with `ResultPath = "$.error"` to `MarkFailed`

#### Scenario: Stills step retries and is caught
- **WHEN** the state machine is synthesized
- **THEN** `FetchStills` has the same retry and the same catch to `MarkFailed`

#### Scenario: Failure before the door event exists
- **WHEN** the mark-failed step runs with `{"account_id": "acc-1", "error": {"Error": "RingTimeout"}}` and no `door_sk`
- **THEN** it logs `analysis_failed` with `reason = "RingTimeout"`, writes no door event, and returns the state with `outcome = "analysis_failed"`
