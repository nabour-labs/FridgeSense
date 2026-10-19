## ADDED Requirements

### Requirement: Hosts the TV dashboard
The Fire TV app SHALL show one full-screen WebView that loads the FridgeSense site's TV dashboard: the site URL given at build time with the hash `#tv`. The WebView SHALL have DOM storage enabled (so the session survives restarts), system key events passed to the page, and initial focus. The site URL SHALL be an `https://` URL; a missing or non-HTTPS URL SHALL fail the build's config check.

#### Scenario: Loads #tv
- **WHEN** the app is built with site URL `https://d1example.cloudfront.net`
- **THEN** the WebView's source is `https://d1example.cloudfront.net/#tv`

#### Scenario: URL already ends with a slash or hash
- **WHEN** the site URL is `https://d1example.cloudfront.net/` or `https://d1example.cloudfront.net/#fridge`
- **THEN** the WebView's source is `https://d1example.cloudfront.net/#tv`

#### Scenario: Bad site URL
- **WHEN** the site URL is missing or starts with `http://`
- **THEN** the config check throws "FridgeSense site URL must be https"

#### Scenario: WebView settings
- **WHEN** the app renders
- **THEN** the WebView has `domStorageEnabled`, `allowSystemKeyEvents` and `hasTVPreferredFocus` set to true

### Requirement: Load failure screen
If the WebView reports a load error, the app SHALL replace it with a screen reading "Can't reach FridgeSense" and a focused "Try again" button; selecting it SHALL show the WebView again and reload the TV dashboard.

#### Scenario: Offline TV
- **WHEN** the WebView calls `onError`
- **THEN** "Can't reach FridgeSense" and a focused "Try again" button are shown and the WebView is not

#### Scenario: Try again
- **WHEN** "Try again" is selected
- **THEN** the WebView is shown again with the `#tv` source

### Requirement: No credentials in the app
The app's source and build output SHALL contain no passcode, session token or API key. The only credential SHALL be the session the TV dashboard stores in the WebView after someone signs in on the TV.

#### Scenario: Source has no secrets
- **WHEN** the `firetv/` package's tracked files are scanned
- **THEN** none matches a passcode assignment (`passcode` followed by `:` or `=` and a quoted value), a `Bearer <token>` string or an AWS access key ID (`AKIA` + 16 characters)

#### Scenario: First launch
- **WHEN** the app is launched on a TV for the first time
- **THEN** the TV dashboard's passcode screen is shown
