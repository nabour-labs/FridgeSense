# Spec Delta

## Purpose

Lists the setup problems that silently stop door openings being recorded or detected well, through `GET /api/warnings` and the app's warning banner, each with what fixes it.

## ADDED Requirements

### Requirement: Ring account needs re-linking warning
When the stored Ring account has `link_status = "needs_relink"`, `GET /api/warnings` SHALL list `{"code": "needs_relink", "message": "The Ring account link has expired, so door openings are not recorded. Re-link the Ring account in the Ring app."}` before every other warning, even when no camera has been discovered. The other warnings SHALL still be checked. In the app, the banner SHALL show the message with no fix link.

#### Scenario: Link expired
- **WHEN** the token store holds `link_status = "needs_relink"` and every other check passes
- **THEN** `warnings` is `[{"code": "needs_relink", "message": "The Ring account link has expired, so door openings are not recorded. Re-link the Ring account in the Ring app."}]`

#### Scenario: Link expired with other problems
- **WHEN** the link needs re-linking and door setup never ran
- **THEN** `warnings` lists `needs_relink` then `door_setup_missing`

#### Scenario: Link expired before any camera
- **WHEN** the link needs re-linking and no camera has been discovered
- **THEN** `warnings` is the `needs_relink` warning alone

#### Scenario: Linked
- **WHEN** the token store holds `link_status = "linked"`
- **THEN** no `needs_relink` warning is listed

#### Scenario: Re-link banner
- **WHEN** an owner opens the Fridge screen and `GET /api/warnings` lists `needs_relink`
- **THEN** the banner shows its message and no link
