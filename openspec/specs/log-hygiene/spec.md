# log-hygiene Specification

## Purpose
TBD - created by archiving change security-quick-wins. Update Purpose after archive.

## Requirements

### Requirement: HTTP request URLs never logged
Every Lambda handler module SHALL set the `httpx` logger to WARNING or higher when imported, so request URLs (Ring's signed media URLs carry `security_token`, MCP URLs carry the MCP key) are never written to CloudWatch, even though the handlers log at INFO.

#### Scenario: Handler muted on import
- **WHEN** any of `fridgesense.handlers.api`, `http`, `mcp`, `pipeline` or `token_refresh` is imported in a fresh interpreter
- **THEN** `logging.getLogger("httpx").getEffectiveLevel()` is at least `logging.WARNING`

#### Scenario: Signed URL fetched during a pipeline run
- **WHEN** a handler has set the root logger to INFO and fetches `https://media.example/clip.mp4?security_token=abc` through `httpx`
- **THEN** no log record contains `security_token=abc`
