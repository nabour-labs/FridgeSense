# analysis-config Specification

## Purpose
The owner's reference images (each with an annotation) and custom instructions that guide the fridge-change analysis. Covers how they are stored per Ring account, their limits, and the HTTP routes that read and change them.

## Requirements

### Requirement: Read the config
`GET /api/config` SHALL return 200 `{"instructions": "<text>", "references": [{"id", "annotation", "image", "created_at"}]}` for the linked account, where `image` is the base64 JPEG and references are listed oldest first. Owner and viewer tokens SHALL both be accepted.

#### Scenario: Config with references
- **WHEN** the owner added "milk bag" and then "soda can", and saved instructions `Count yogurt cups individually.`
- **THEN** a viewer's `GET /api/config` returns those instructions and two references in the order milk bag, soda can, each with a non-empty `id`, its `image` and an ISO 8601 `created_at`

#### Scenario: Nothing configured
- **WHEN** no references or instructions were ever saved
- **THEN** the response is `{"instructions": "", "references": []}`

### Requirement: Save custom instructions
`PUT /api/config/instructions` with `{"instructions": "<text>"}` SHALL store the trimmed text for the linked account and return 200 with the full config in the `GET /api/config` shape. The text SHALL be at most 1,000 characters after trimming. An empty string SHALL clear it.

#### Scenario: Save instructions
- **WHEN** the owner sends `{"instructions": "  Count yogurt cups individually.  "}`
- **THEN** the response is 200 and its `instructions` is `Count yogurt cups individually.`

#### Scenario: Clear instructions
- **WHEN** the owner sends `{"instructions": ""}`
- **THEN** the response's `instructions` is `""` and the next analysis has no owner's instructions

#### Scenario: Instructions too long or wrong type
- **WHEN** the body is `{"instructions": <1,001 characters>}`, `{"instructions": 5}` or not JSON
- **THEN** the response is 400 `{"error": "instructions must be text of at most 1000 characters"}` and the stored instructions are unchanged

### Requirement: Add a reference image
`POST /api/config/references` with `{"annotation": "<text>", "image": "<base64 JPEG>"}` SHALL store the reference for the linked account and return 200 with the full config. The annotation SHALL be 1–300 characters after trimming. The image SHALL decode to JPEG bytes (starting `FF D8 FF`) of at most 200,000 bytes. An account SHALL hold at most 6 references.

#### Scenario: Add a reference
- **WHEN** the owner sends annotation `milk bag (2 L, white with blue print)` and a valid 60 KB JPEG
- **THEN** the response is 200 and the last entry of `references` has that annotation and the same image

#### Scenario: Bad annotation
- **WHEN** the annotation is missing, only spaces, or 301 characters
- **THEN** the response is 400 `{"error": "annotation must be 1 to 300 characters"}` and nothing is stored

#### Scenario: Not a JPEG or too large
- **WHEN** `image` is not valid base64, decodes to a PNG, or decodes to 200,001 bytes
- **THEN** the response is 400 `{"error": "image must be a JPEG of at most 200 KB"}` and nothing is stored

#### Scenario: Seventh reference
- **WHEN** the account already has 6 references and another valid one is posted
- **THEN** the response is 409 `{"error": "at most 6 reference images"}` and the account still has the same 6

### Requirement: Delete a reference image
`DELETE /api/config/references/{id}` SHALL remove that reference from the linked account and return 200 with the full config. An unknown id SHALL return 404.

#### Scenario: Delete a reference
- **WHEN** the owner deletes the "milk bag" reference's id
- **THEN** the response is 200 and `references` no longer contains it

#### Scenario: Unknown reference
- **WHEN** the id does not exist for this account
- **THEN** the response is 404 and nothing changes

### Requirement: Config writes are owner-only and per account
The three config write routes SHALL follow the existing auth rules: they need a valid token, a viewer token SHALL get 403 `{"error": "read-only"}`, and they need a linked account (otherwise 409). All config SHALL be stored and read under the linked Ring `account_id`.

#### Scenario: Viewer cannot change config
- **WHEN** a viewer token calls `PUT /api/config/instructions`, `POST /api/config/references` or `DELETE /api/config/references/{id}`
- **THEN** each response is 403 `{"error": "read-only"}` and the config is unchanged

#### Scenario: No token
- **WHEN** `GET /api/config` is called without a token
- **THEN** the response is 401 `{"error": "sign in"}`

#### Scenario: Config kept per account
- **WHEN** account A has a reference and account B has none
- **THEN** B's config and B's analysis requests contain no references

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
