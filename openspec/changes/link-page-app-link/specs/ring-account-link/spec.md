## ADDED Requirements

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
