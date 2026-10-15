# Spec Delta

## ADDED Requirements

### Requirement: Bounded Bedrock call time
Each Bedrock request SHALL be sent once by the client (no client-side retries) with a read timeout of 30 s, so that the analysis step's two Nova attempts finish within the pipeline task's 90 s limit. A client-side read or connect timeout SHALL be treated like a retryable Bedrock error (`BedrockRetryable`), so the workflow's backoff retries apply to it.

#### Scenario: Client sends one attempt
- **WHEN** the pipeline builds its Bedrock client
- **THEN** the client's total attempts is 1 and its read timeout is 30 s

#### Scenario: Read timeout is retryable
- **WHEN** a Nova request times out on the client side (read or connect timeout)
- **THEN** the analysis raises `BedrockRetryable` and a `nova_error` warning is logged with `error_code` `ReadTimeout` or `ConnectTimeout`
