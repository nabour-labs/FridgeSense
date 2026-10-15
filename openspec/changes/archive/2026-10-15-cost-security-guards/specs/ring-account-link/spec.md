## MODIFIED Requirements

### Requirement: Token exchange stores tokens as unclaimed
When Ring POSTs an authorization `code` to `POST /ring/token`, the system SHALL exchange it at `https://oauth.ring.com/oauth/token` (`grant_type=authorization_code`, client ID and secret from config), read the account ID from `GET /v1/users/me` (`data.id`), store the tokens for that account with link status `unclaimed`, and reply 200. If the store already holds a `linked` or `needs_relink` account with a different account ID, the system SHALL NOT store the new tokens and SHALL reply 409 instead.

#### Scenario: Valid authorization code
- **WHEN** Ring POSTs `{"code": "abc123"}` to `/ring/token` and the OAuth endpoint returns `{"access_token": "at1", "refresh_token": "rt1", "expires_in": 14400, "token_type": "Bearer"}` and `/v1/users/me` returns `data.id = "ava1.ring.account.A1"`
- **THEN** the response is 200 and the token store holds `account_id = "ava1.ring.account.A1"`, `access_token = "at1"`, `refresh_token = "rt1"`, `expires_at` = now + 14400 s and `link_status = "unclaimed"`

#### Scenario: Code sent as a form field or query parameter
- **WHEN** Ring POSTs `code=abc123` as `application/x-www-form-urlencoded`, or calls `/ring/token?code=abc123`
- **THEN** the code is exchanged exactly as if it had been sent as JSON

#### Scenario: Missing code
- **WHEN** a request to `/ring/token` carries no `code` in JSON, form or query
- **THEN** the response is 400 and no call is made to the OAuth endpoint

#### Scenario: Ring rejects the code
- **WHEN** the OAuth endpoint answers 400 (for example an expired code)
- **THEN** the response is 502, the token store is unchanged, and the error is logged without the code or client secret

#### Scenario: Secrets never logged
- **WHEN** any token exchange runs, successful or not
- **THEN** no log line contains the authorization code, client secret, access token or refresh token

#### Scenario: Different account while one is linked
- **WHEN** the store holds `account_id = "ava1.ring.account.A1"` with `link_status = "linked"` and a code exchange returns `data.id = "ava1.ring.account.B2"`
- **THEN** the response is 409 with `{"error": "another account is linked"}`, the store still holds A1's tokens with `link_status = "linked"`, and a `token_exchange_refused` warning logs both account IDs

#### Scenario: Different account while relink is needed
- **WHEN** the store holds account A1 with `link_status = "needs_relink"` and a code exchange returns account B2
- **THEN** the response is 409 and the store is unchanged

#### Scenario: Same account links again
- **WHEN** the store holds account A1 with `link_status = "linked"` and a code exchange returns account A1 with `access_token = "at2"`
- **THEN** the response is 200 and the store holds A1 with `access_token = "at2"` and `link_status = "unclaimed"`, ready for the link page

#### Scenario: Different account before anything is linked
- **WHEN** the store holds account A1 with `link_status = "unclaimed"` and a code exchange returns account B2
- **THEN** the response is 200 and the store holds B2's tokens with `link_status = "unclaimed"`
