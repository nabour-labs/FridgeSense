# Spec Delta

## MODIFIED Requirements

### Requirement: Default API request limit
The HTTP API's default stage SHALL limit every route to a steady rate of 10 requests per second with a burst of 20, unless a route has its own limit.

#### Scenario: Default stage throttled
- **WHEN** the stack is synthesized
- **THEN** the HTTP API's `$default` stage has `DefaultRouteSettings` with `ThrottlingRateLimit = 10` and `ThrottlingBurstLimit = 20`

## ADDED Requirements

### Requirement: Webhook route limited separately
`POST /ring/webhook` SHALL have its own limit of 50 requests per second with a burst of 100, so unsigned traffic at the default limit can't starve Ring's deliveries into 429s. The stage SHALL depend on the webhook route so CloudFormation creates the route first.

#### Scenario: Webhook route throttled
- **WHEN** the stack is synthesized
- **THEN** the `$default` stage's `RouteSettings` has an entry for `POST /ring/webhook` with `ThrottlingRateLimit = 50` and `ThrottlingBurstLimit = 100`, and the `POST /api/session` and `POST /ring/link` entries are still 1 and 3

#### Scenario: Webhook route exists before its limit
- **WHEN** the stack is synthesized
- **THEN** the `$default` stage depends on the `POST /ring/webhook` route
