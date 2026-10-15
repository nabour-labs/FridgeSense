# ring-account-link Specification

## Purpose
Links the single user's Ring account to FridgeSense through Ring's one-way account linking: Ring hands over an authorization code, and the user confirms the link on a passcode-protected page.

## Requirements

### Requirement: Token exchange stores tokens as unclaimed
When Ring POSTs an authorization `code` to `POST /ring/token`, the system SHALL exchange it at `https://oauth.ring.com/oauth/token` (`grant_type=authorization_code`, client ID and secret from config), read the account ID from `GET /v1/users/me` (`data.id`), store the tokens for that account with link status `unclaimed`, and reply 200.

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

### Requirement: Link page requires the passcode before matching the nonce
`GET /ring/link?nonce=<n>&time=<ms>` SHALL render a sign-in form that carries `nonce` and `time` forward and asks for the passcode. The nonce SHALL NOT be checked and Ring SHALL NOT be called until a correct passcode is submitted to `POST /ring/link`.

#### Scenario: Ring opens the link page
- **WHEN** the browser requests `GET /ring/link?nonce=N1&time=1771130906289`
- **THEN** the response is 200 HTML containing a passcode field and hidden fields with `nonce = N1` and `time = 1771130906289`, and no Ring API call is made

#### Scenario: Link page opened without Ring parameters
- **WHEN** the browser requests `GET /ring/link` without `nonce` or `time`
- **THEN** the response is 400 HTML saying the page must be opened from the Ring app

#### Scenario: Wrong passcode
- **WHEN** the form is posted with a passcode that does not match the configured passcode
- **THEN** the response is 401 HTML showing the form again with an error, and no nonce check or Ring API call happens

### Requirement: Nonce and freshness verification
After a correct passcode, the system SHALL reject a `time` older than 600 s or in the future, then SHALL accept the link only if `nonce` equals `base64url_nopad(HMAC_SHA256(hmac_key, "<time>:<account_id>"))` for the stored unclaimed account, compared in constant time.

#### Scenario: Stale link request
- **WHEN** the passcode is correct and `time` is 601 s before now
- **THEN** the response is 400 HTML saying the link expired and to start again from the Ring app, and no Ring API call is made

#### Scenario: Time in the future
- **WHEN** the passcode is correct and `time` is later than now
- **THEN** the response is 400 HTML and no Ring API call is made

#### Scenario: Nonce does not match
- **WHEN** the passcode is correct, `time` is fresh, and `nonce` does not match the HMAC for the unclaimed account
- **THEN** the response is 400 HTML, no Ring API call is made, and the stored tokens stay `unclaimed`

#### Scenario: No unclaimed account
- **WHEN** the passcode is correct and `time` is fresh but the token store has no account with `link_status = "unclaimed"`
- **THEN** the response is 400 HTML and no Ring API call is made

### Requirement: Complete the app integration with Ring
When the nonce matches, the system SHALL `POST /v1/accounts/me/app-integrations` with `{"account_identifier": <masked identity>, "nonce": <nonce>}`, then `PATCH` the same URL with `{"status": "completed"}`, using the matched account's access token, and SHALL mark the account `linked`.

#### Scenario: Successful link
- **WHEN** the nonce matches and Ring answers 2xx to both the POST and the PATCH
- **THEN** the token store shows `link_status = "linked"`, the response is 200 HTML confirming the link, and the PATCH body was exactly `{"status": "completed"}`

#### Scenario: Ring rejects the integration
- **WHEN** the nonce matches but Ring answers 400 or 404 to the POST or the PATCH
- **THEN** the response is 502 HTML explaining that linking failed, and the account stays `unclaimed`

### Requirement: Confirmation page links to the app
After a successful link, the confirmation page SHALL include a link labeled "Open FridgeSense" whose `href` is the app's site URL from `APP_URL`. When `APP_URL` is unset or empty, the page SHALL render without the link.

#### Scenario: App URL configured
- **WHEN** `APP_URL = "https://d111.cloudfront.net"` and a link completes successfully
- **THEN** the 200 HTML contains `<a` with `href="https://d111.cloudfront.net"` and the text "Open FridgeSense"

#### Scenario: App URL not configured
- **WHEN** `APP_URL` is unset and a link completes successfully
- **THEN** the 200 HTML confirms the link and contains no "Open FridgeSense" link

#### Scenario: Stack passes the site URL
- **WHEN** the CDK stack is synthesized
- **THEN** the HTTP function's environment has `APP_URL` set to the app's CloudFront site URL
