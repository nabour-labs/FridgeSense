## ADDED Requirements

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
