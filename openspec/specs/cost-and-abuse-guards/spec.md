# cost-and-abuse-guards Specification

## Purpose
Deploy-time guards that cap abuse of the public API and warn the owner early about AWS spend and pipeline failures, since the demo's AWS bill is paid out of pocket.

## Requirements

### Requirement: Default API request limit
The HTTP API's default stage SHALL limit every route to a steady rate of 10 requests per second with a burst of 20, unless a route has its own limit.

#### Scenario: Default stage throttled
- **WHEN** the stack is synthesized
- **THEN** the HTTP API's `$default` stage has `DefaultRouteSettings` with `ThrottlingRateLimit = 10` and `ThrottlingBurstLimit = 20`

### Requirement: Passcode routes limited further
`POST /api/session` and `POST /ring/link`, the two routes that check a passcode, SHALL each be limited to 1 request per second with a burst of 3. `POST /api/session` SHALL be its own route, served by the same app API function as `/api/{proxy+}`.

#### Scenario: Passcode routes throttled
- **WHEN** the stack is synthesized
- **THEN** the `$default` stage's `RouteSettings` has entries for `POST /api/session` and `POST /ring/link`, each with `ThrottlingRateLimit = 1` and `ThrottlingBurstLimit = 3`

#### Scenario: Session route reaches the app API
- **WHEN** the stack is synthesized
- **THEN** a route with `RouteKey = "POST /api/session"` exists and targets the same integration as `ANY /api/{proxy+}`

#### Scenario: Routes exist before their limits
- **WHEN** the stack is synthesized
- **THEN** the `$default` stage depends on the `POST /api/session` and `POST /ring/link` routes, so CloudFormation creates them first

### Requirement: Monthly cost budget alert
The stack SHALL create a monthly cost budget of 20 USD that emails the alert address when actual spend passes 80% of it.

#### Scenario: Budget at 80 percent
- **WHEN** the stack is synthesized with `alertEmail = "owner@example.test"`
- **THEN** an `AWS::Budgets::Budget` has `BudgetType = "COST"`, `TimeUnit = "MONTHLY"`, `BudgetLimit = {"Amount": 20, "Unit": "USD"}`, and one notification `{"NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN", "Threshold": 80, "ThresholdType": "PERCENTAGE"}` with an `EMAIL` subscriber `owner@example.test`

### Requirement: Failed door-event alarm
The stack SHALL create a CloudWatch alarm that goes into alarm when the `fridgesense-door-events` state machine has at least one failed execution in a 5-minute period, and SHALL email the alert address through an SNS topic when it does.

#### Scenario: Alarm on failed executions
- **WHEN** the stack is synthesized with `alertEmail = "owner@example.test"`
- **THEN** an alarm watches `AWS/States` `ExecutionsFailed` for the door-events state machine ARN with statistic `Sum`, period 300, threshold 1, `ComparisonOperator = "GreaterThanOrEqualToThreshold"`, 1 evaluation period and `TreatMissingData = "notBreaching"`, and its alarm action is an SNS topic with an email subscription to `owner@example.test`

### Requirement: Alert address supplied at deploy time
The alert email address SHALL come from the CDK context value `alertEmail`. No email address SHALL be written into the source. Synthesis SHALL fail with an error naming `alertEmail` when it is missing or empty.

#### Scenario: Address missing
- **WHEN** the stack is synthesized without an `alertEmail` context value
- **THEN** synthesis throws an error whose message contains `alertEmail`

### Requirement: Webhook route limited separately
`POST /ring/webhook` SHALL have its own limit of 50 requests per second with a burst of 100, so unsigned traffic at the default limit can't starve Ring's deliveries into 429s. The stage SHALL depend on the webhook route so CloudFormation creates the route first.

#### Scenario: Webhook route throttled
- **WHEN** the stack is synthesized
- **THEN** the `$default` stage's `RouteSettings` has an entry for `POST /ring/webhook` with `ThrottlingRateLimit = 50` and `ThrottlingBurstLimit = 100`, and the `POST /api/session` and `POST /ring/link` entries are still 1 and 3

#### Scenario: Webhook route exists before its limit
- **WHEN** the stack is synthesized
- **THEN** the `$default` stage depends on the `POST /ring/webhook` route

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
