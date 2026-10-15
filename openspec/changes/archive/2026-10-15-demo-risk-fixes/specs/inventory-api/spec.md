# Spec Delta

## ADDED Requirements

### Requirement: API errors reach the app unchanged
When the app is served through the CDN, every `/api/*` response SHALL reach the app with the status code and JSON body the API sent. The CDN SHALL NOT replace an API error response with the app shell. Because the app uses hash routes, the CDN needs no path fallback: `/` serves the app shell.

#### Scenario: Viewer write refused through the CDN
- **WHEN** a viewer's `POST /api/pending/{id}/confirm` goes through the CDN and the API answers 403 `{"error": "read-only"}`
- **THEN** the app receives status 403 with that JSON body, not 200 with `index.html`

#### Scenario: Not found through the CDN
- **WHEN** the API answers 404 to an `/api/*` request made through the CDN
- **THEN** the app receives status 404 with the API's JSON body

#### Scenario: App shell at the root
- **WHEN** a browser requests `/` from the CDN
- **THEN** it receives `index.html`
