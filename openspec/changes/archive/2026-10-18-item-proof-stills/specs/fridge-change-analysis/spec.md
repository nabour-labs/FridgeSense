## ADDED Requirements

### Requirement: Proof images per change
Each change in the `record_fridge_changes` tool schema SHALL have an optional `images` array of integers, described as the 1 or 2 image numbers where that item is most clearly visible. The final instruction text SHALL ask for it. On parsing, `images` SHALL keep only whole numbers from 1 to the number of stills sent, in order, without duplicates and at most 2. A missing, non-list or invalid `images` SHALL become `[]` and SHALL NOT make the answer invalid. The door event's saved change SHALL keep `proof`, the kept numbers minus 1.

#### Scenario: Schema and prompt ask for images
- **WHEN** the request is built for 4 stills
- **THEN** the tool's change schema has `images` of type array of integer, it is not in `required`, and the final text contains "images"

#### Scenario: Proof kept
- **WHEN** Nova returns `{"added": [{"item": "soda can", "category": "beverage", "quantity": 1, "confidence": 0.9, "images": [3, 4]}], "removed": []}` for 4 stills
- **THEN** the saved door event's change for `soda can` has `proof = [2, 3]`

#### Scenario: Out-of-range, duplicate and extra numbers
- **WHEN** a change has `images = [0, 2, 2, 5, 3, 4]` and 4 stills were sent
- **THEN** its `proof` is `[1, 2]`

#### Scenario: Images missing or malformed
- **WHEN** one change has no `images` and another has `images = "2"`
- **THEN** both are accepted with `proof = []`, and the analysis is not retried

#### Scenario: Non-integer numbers
- **WHEN** a change has `images = [1.0, "2", true, 2.5]`
- **THEN** its `proof` is `[0]`
