# ring-token-lifecycle Specification

## Purpose
Keeps the linked Ring account's access token valid without user action, so the pipeline and front ends can call the Ring API at any time.

## Requirements

### Requirement: Scheduled token refresh
A scheduled job SHALL run every 3 hours and, for a stored account with link status `unclaimed` or `linked`, refresh the tokens at `https://oauth.ring.com/oauth/token` with `grant_type=refresh_token`, storing the new access token, the new refresh token and the new expiry.

#### Scenario: Refresh succeeds and rotates the refresh token
- **WHEN** the job runs with stored `refresh_token = "rt1"` and the OAuth endpoint returns `{"access_token": "at2", "refresh_token": "rt2", "expires_in": 14400}`
- **THEN** the store holds `access_token = "at2"`, `refresh_token = "rt2"` and `expires_at` = now + 14400 s, and the request body contained `grant_type=refresh_token&refresh_token=rt1` with the configured client ID and secret

#### Scenario: Refresh response without a new refresh token
- **WHEN** the OAuth endpoint returns an access token but no `refresh_token`
- **THEN** the store keeps the previous refresh token and saves the new access token and expiry

#### Scenario: Nothing to refresh
- **WHEN** the job runs and the token store is empty
- **THEN** the job ends successfully without calling the OAuth endpoint

#### Scenario: Refresh token rejected
- **WHEN** the OAuth endpoint answers 400 or 401 (for example `invalid_grant`)
- **THEN** the store marks the account `link_status = "needs_relink"`, keeps the old tokens, and logs an error naming the account ID but no token values

#### Scenario: OAuth endpoint unavailable
- **WHEN** the OAuth endpoint answers 5xx or times out
- **THEN** the store is unchanged, the link status is unchanged, and the job fails so the scheduler records the error

### Requirement: Valid token for every Ring API call
Before calling the Ring API, the system SHALL refresh the tokens first if the stored access token expires within 5 minutes. If a call still returns 401, it SHALL refresh once and retry that call once.

#### Scenario: Token about to expire
- **WHEN** a Ring API call is made and the stored `expires_at` is 4 minutes from now
- **THEN** the tokens are refreshed before the call, and the call uses the new access token

#### Scenario: Ring answers 401 once
- **WHEN** a Ring API call returns 401 and the refresh succeeds
- **THEN** the call is retried once with the new access token and its result is returned

#### Scenario: Ring answers 401 after refresh
- **WHEN** the retried call also returns 401
- **THEN** the call fails with an authorization error and no further retries are made

#### Scenario: Bearer header
- **WHEN** any Ring API call is made
- **THEN** it is sent to `https://api.amazonvision.com` with `Authorization: Bearer <access_token>`, and the token is never sent to any other host

### Requirement: Concurrent refreshes keep the newest tokens
When several Ring API calls in one process need a refresh at the same time, only one SHALL call the OAuth endpoint; the others SHALL use the tokens it stored. Before refreshing, a call SHALL read the stored tokens again and, if the stored access token differs from the one it was using, use the stored tokens instead of refreshing. When the scheduled job's refresh is rejected, it SHALL read the stored tokens again and mark the account `needs_relink` only if the stored refresh token is still the one that was rejected; otherwise it SHALL leave the stored tokens and link status as they are.

#### Scenario: Concurrent refresh
- **WHEN** two Ring API calls run at the same time, both read stored tokens `at1`/`rt1` expiring in 4 minutes, and the OAuth endpoint returns `{"access_token": "at2", "refresh_token": "rt2", "expires_in": 14400}`
- **THEN** the OAuth endpoint is called exactly once, both calls send `Authorization: Bearer at2`, and the store holds `at2`/`rt2`

#### Scenario: Another caller already refreshed
- **WHEN** a Ring API call read `at1` expiring in 4 minutes, and by the time it would refresh the store holds `at2`/`rt2` saved by another caller
- **THEN** the OAuth endpoint is not called, the call sends `Authorization: Bearer at2`, and the store still holds `at2`/`rt2`

#### Scenario: Refresh rejected after another caller already refreshed
- **WHEN** the scheduled job read `rt1`, the OAuth endpoint answers 400 `invalid_grant` for `rt1`, and meanwhile another caller stored `at2`/`rt2` with `link_status = "linked"`
- **THEN** the store still holds `at2`/`rt2` with `link_status = "linked"`, and the job reports that the tokens were already refreshed

#### Scenario: Refresh rejected and nobody else refreshed
- **WHEN** the scheduled job's refresh of `rt1` is rejected and the store still holds `rt1`
- **THEN** the store marks the account `link_status = "needs_relink"` as before
