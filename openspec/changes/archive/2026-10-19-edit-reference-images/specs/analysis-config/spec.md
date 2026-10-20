## ADDED Requirements

### Requirement: Edit a reference image
`PATCH /api/config/references/{id}` with `{"annotation"?: "<text>", "image"?: "<base64 JPEG>"}` SHALL change the given fields of that reference for the linked account and return 200 with the full config. Each field SHALL follow the limits for adding a reference. The reference SHALL keep its `id`, `created_at` and place in the list. A body with neither field SHALL return 400 `{"error": "send an annotation or an image"}`. An unknown id SHALL return 404. A viewer token SHALL get 403 `{"error": "read-only"}`.

#### Scenario: Edit the annotation
- **WHEN** the owner has "milk bag" then "soda can" and sends `{"annotation": " chocolate milk "}` for "milk bag"
- **THEN** the response is 200, `references` is chocolate milk then soda can, and the first keeps its id, image and `created_at`

#### Scenario: Replace the image
- **WHEN** the owner sends only a new valid JPEG for "milk bag"
- **THEN** the response is 200 and that reference has the new image and still the annotation "milk bag"

#### Scenario: Edit both
- **WHEN** the owner sends a new annotation and a new image
- **THEN** both are changed

#### Scenario: Nothing to change
- **WHEN** the body is `{}` or not JSON
- **THEN** the response is 400 `{"error": "send an annotation or an image"}` and nothing changes

#### Scenario: Bad edit
- **WHEN** the annotation is only spaces, or the image decodes to a PNG
- **THEN** the response is 400 with the same error as for adding, and nothing changes

#### Scenario: Edit an unknown reference
- **WHEN** the id does not exist for this account
- **THEN** the response is 404 and nothing changes

#### Scenario: Viewer cannot edit
- **WHEN** a viewer token sends a valid edit
- **THEN** the response is 403 `{"error": "read-only"}` and the reference is unchanged
