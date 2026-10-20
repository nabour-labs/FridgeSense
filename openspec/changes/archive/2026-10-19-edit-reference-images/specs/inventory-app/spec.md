## ADDED Requirements

### Requirement: Edit reference images
Each reference card SHALL have an "Edit" button for the owner, next to "Delete". It SHALL open an "Edit reference" sheet showing the reference's current image, ready to draw on and crop, and its annotation in the annotation field. The sheet SHALL offer the same "Choose photo", "Camera snapshot" and "Recent clip" sources as adding, to replace the image. "Save" SHALL be disabled while the annotation is empty or nothing has changed. It SHALL send `PATCH /api/config/references/{id}` with the trimmed annotation if it changed, and the image, resized and with boxes drawn in, only if a new image was chosen, it was cropped or a box was drawn. The list SHALL then show the returned config. A 400 SHALL show the error in the sheet. Viewers get no "Edit" button.

#### Scenario: Edit an annotation
- **WHEN** the owner taps "Edit" on "chocomilk", changes the annotation to `chocolate milk carton` and taps "Save"
- **THEN** the sheet shows the current image, `PATCH` is sent with only `{"annotation": "chocolate milk carton"}`, and the card reads "chocolate milk carton"

#### Scenario: Replace the image
- **WHEN** the owner taps "Edit", chooses a new photo and taps "Save"
- **THEN** `PATCH` is sent with only the resized new image

#### Scenario: Draw on the current image
- **WHEN** the owner taps "Edit", draws a box on the current image and taps "Save"
- **THEN** `PATCH` is sent with only the image, resized with that box

#### Scenario: Nothing changed
- **WHEN** the owner opens "Edit" and changes nothing
- **THEN** "Save" is disabled

#### Scenario: Edit refused
- **WHEN** the API answers 400 to an edit
- **THEN** the error message is shown in the sheet and the list is unchanged

#### Scenario: Viewer has no edit
- **WHEN** a viewer opens the "Reference images" tab
- **THEN** no "Edit" button is shown
