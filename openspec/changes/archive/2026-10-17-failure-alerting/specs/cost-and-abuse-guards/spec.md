# Spec Delta

## ADDED Requirements

### Requirement: Timed-out door-event alarm
The stack SHALL create a CloudWatch alarm that goes into alarm when the `fridgesense-door-events` state machine has at least one timed-out execution in a 5-minute period, and SHALL send it to the same SNS alert topic as the failed-run alarm.

#### Scenario: Alarm on timed-out executions
- **WHEN** the stack is synthesized with `alertEmail = "owner@example.test"`
- **THEN** an alarm named `fridgesense-door-events-timed-out` watches `AWS/States` `ExecutionsTimedOut` for the door-events state machine ARN with statistic `Sum`, period 300, threshold 1, `ComparisonOperator = "GreaterThanOrEqualToThreshold"`, 1 evaluation period and `TreatMissingData = "notBreaching"`, and its alarm action is the alert SNS topic

### Requirement: Rejected token refresh alarm
The stack SHALL count `token_refresh_rejected` log events from the token-refresh job as a CloudWatch metric, and SHALL create an alarm that goes into alarm when that metric is at least 1 in a 5-minute period, sending to the alert SNS topic.

#### Scenario: Metric filter on rejected refreshes
- **WHEN** the stack is synthesized
- **THEN** a metric filter on the `/fridgesense/token-refresh` log group with filter pattern `"token_refresh_rejected"` publishes metric `TokenRefreshRejected` in namespace `FridgeSense` with value `1`

#### Scenario: Alarm on rejected refreshes
- **WHEN** the stack is synthesized with `alertEmail = "owner@example.test"`
- **THEN** an alarm named `fridgesense-ring-relink-needed` watches `FridgeSense` `TokenRefreshRejected` with statistic `Sum`, period 300, threshold 1, `ComparisonOperator = "GreaterThanOrEqualToThreshold"`, 1 evaluation period and `TreatMissingData = "notBreaching"`, and its alarm action is the alert SNS topic
