## MODIFIED Requirements

### Requirement: Add a reference image
`POST /api/config/references` with `{"annotation": "<text>", "image": "<base64 JPEG>"}` SHALL store the reference for the linked account and return 200 with the full config. The annotation SHALL be 1–300 characters after trimming. The image SHALL decode to JPEG bytes (starting `FF D8 FF`) of at most 200,000 bytes. An account SHALL hold at most 30 references.

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
- **WHEN** the account already has 30 references and another valid one is posted
- **THEN** the response is 409 `{"error": "at most 30 reference images"}` and the account still has the same 30
