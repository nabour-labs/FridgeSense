# Spec Delta

## MODIFIED Requirements

### Requirement: Passcode sign-in returns a session token
`POST /api/session` with `{"passcode": "<passcode>"}` SHALL return 200 `{"token": "<token>", "expires_at": "<ISO 8601>", "role": "owner" | "viewer"}` when the passcode matches the configured owner passcode (role `owner`) or the optional configured demo passcode (role `viewer`), with a token valid for 24 hours. Changing either passcode SHALL invalidate the existing tokens of that role only. When no demo passcode is configured, only the owner passcode SHALL sign in. Tokens issued under the earlier 30-day scheme SHALL no longer be accepted.

#### Scenario: Correct passcode
- **WHEN** the configured passcode is `open-sesame` and the body is `{"passcode": "open-sesame"}`
- **THEN** the response is 200 with a non-empty `token`, an `expires_at` 24 hours from now and `role` `"owner"`

#### Scenario: Demo passcode
- **WHEN** the configured demo passcode is `look-only` and the body is `{"passcode": "look-only"}`
- **THEN** the response is 200 with a non-empty `token`, an `expires_at` 24 hours from now and `role` `"viewer"`

#### Scenario: No demo passcode configured
- **WHEN** no demo passcode is configured and the body is `{"passcode": ""}` or any value other than the owner passcode
- **THEN** the response is 401 `{"error": "wrong passcode"}`

#### Scenario: Demo passcode changed
- **WHEN** an owner token and a viewer token were issued and the demo passcode then changes
- **THEN** a request with the old viewer token gets 401 and a request with the owner token still succeeds

#### Scenario: Wrong passcode
- **WHEN** the body is `{"passcode": "guess"}` or has no `passcode`
- **THEN** the response is 401 `{"error": "wrong passcode"}`

#### Scenario: Passcode changed
- **WHEN** a token was issued and the configured passcode then changes
- **THEN** a request with the old token gets 401

#### Scenario: Token one day old
- **WHEN** an owner token was issued at time T and `GET /api/inventory` is called with it at T + 24 h, and again at T + 24 h + 1 s
- **THEN** the first request succeeds and the second gets 401 `{"error": "sign in"}`

#### Scenario: Token from before the change
- **WHEN** a request carries an owner token signed the old way (30-day lifetime, earlier signing key) whose `exp` is still in the future
- **THEN** the response is 401 `{"error": "sign in"}`
