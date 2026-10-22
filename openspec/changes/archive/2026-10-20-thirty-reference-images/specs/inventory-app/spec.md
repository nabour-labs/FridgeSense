## MODIFIED Requirements

### Requirement: Manage reference images
The "Reference images" sub-section SHALL list each reference as a thumbnail with its annotation (its description). It SHALL let the owner add one and delete one after confirming. Adding SHALL offer three sources: "Choose photo" (pick or take a photo on the device), "Camera snapshot" (`POST /api/camera/snapshot`) and "Recent clip". "Recent clip" SHALL open the "Snapshot from a recent clip" sheet: a dropdown of the door openings from the last 7 days that have a `clip`, newest first, each labelled with its day, local time and duration (e.g. "Today 18:02 · 25 s"); the selected clip plays with a scrubber; "Use this frame" sends the shown frame, as a JPEG at most 960 px wide, to `POST /api/camera/frame`, and only the image that route returns is shown for drawing; "Cancel" closes the sheet without a request. Once an image is chosen, the owner SHALL be able to drag boxes on it, undo the last box with "Undo", and type the annotation, up to 300 characters, in a multi-line field. There SHALL be no "Box" or "Line" tool buttons and no way to draw a line. Once at least one box is drawn, a "Crop" button SHALL crop the image to the last box, taken from the full-resolution image; the cropped image SHALL replace the one shown and its boxes SHALL be cleared. "Undo" with no boxes left after a crop SHALL restore the image from before that crop, with its boxes. The boxes SHALL be drawn in red into the uploaded image. Before upload, the image SHALL be re-encoded as JPEG with its longer side at most 768 px. The owner SHALL see how many of the 30 are used.

#### Scenario: Add a reference
- **WHEN** the owner taps "Add", taps "Choose photo", picks a 4032×3024 photo, types `soda can` and taps "Save"
- **THEN** `POST /api/config/references` is sent with annotation `soda can` and a JPEG of 768×576, and the list shows the new thumbnail labeled "soda can"

#### Scenario: Add a camera snapshot
- **WHEN** the owner taps "Add", then "Camera snapshot", and the API answers 200 with a 960×540 image
- **THEN** that image is shown for drawing, and after typing `milk bag` and tapping "Save", the uploaded JPEG is 768×432

#### Scenario: Snapshot with no recent footage
- **WHEN** the API answers 409 `{"error": "no recent footage"}` to a snapshot
- **THEN** "No recent footage. Walk past the camera, then try again." is shown and the owner can still choose a photo

#### Scenario: Draw on the image
- **WHEN** the owner drags from 10%, 10% to 40%, 50% of the image, then from 50%, 50% to 90%, 90%, and taps "Save"
- **THEN** there are no "Box" or "Line" buttons, and the shapes passed to the upload are a box from `(0.1, 0.1)` to `(0.4, 0.5)` and a box from `(0.5, 0.5)` to `(0.9, 0.9)`, in that order, drawn in red into the JPEG

#### Scenario: Crop to the box
- **WHEN** the owner draws a box from 10%, 10% to 40%, 50% on a 1000×800 image and taps "Crop"
- **THEN** the image is cropped to the 300×320 px region at (100, 80), the cropped image is shown for drawing with no boxes, and after typing `milk bag` and tapping "Save" the cropped image (not the original) is uploaded, with no shapes

#### Scenario: Crop needs a box
- **WHEN** an image is chosen and no box is drawn
- **THEN** "Crop" is disabled

#### Scenario: Undo a crop
- **WHEN** the owner draws a box, taps "Crop", then taps "Undo"
- **THEN** the original image is shown again with that box, and "Crop" is enabled

#### Scenario: Undo a shape
- **WHEN** the owner has drawn two shapes and taps "Undo"
- **THEN** only the first shape remains, and "Undo" is disabled when no shapes are left

#### Scenario: Annotation required
- **WHEN** the owner picks a photo but leaves the annotation empty
- **THEN** "Save" is disabled and no request is sent

#### Scenario: Long annotation
- **WHEN** the owner types a 300-character annotation and then one more character
- **THEN** the field holds the 300 characters and "Save" sends all of them

#### Scenario: Limit reached
- **WHEN** 30 references exist
- **THEN** the sub-section shows "30 of 30" and the "Add" button is disabled

#### Scenario: Delete a reference
- **WHEN** the owner taps "Delete" on "milk bag" and confirms
- **THEN** `DELETE /api/config/references/{id}` is sent and "milk bag" disappears from the list

#### Scenario: Upload refused
- **WHEN** the API answers 400 or 409 to an add
- **THEN** the error message from the response is shown and the list is unchanged

#### Scenario: Add a reference from a recent clip
- **WHEN** the owner taps "Add", then "Recent clip", picks the 18:02 opening, taps "Use this frame", and `POST /api/camera/frame` answers 200 with a 960×540 image
- **THEN** the grabbed frame was sent to `POST /api/camera/frame`, the returned image is shown for drawing, and after typing `milk bag` and tapping "Save", the uploaded JPEG is 768×432

#### Scenario: Recent clips listed
- **WHEN** the last 7 days hold openings today at 18:02 (25 s, with a clip), today at 09:15 (no clip) and yesterday at 20:40 (12 s, with a clip)
- **THEN** the dropdown lists "Today 18:02 · 25 s" then "Yesterday 20:40 · 12 s", the first is selected, and its video plays the clip link with `crossOrigin` set to `anonymous`

#### Scenario: No recent clips
- **WHEN** no door opening in the last 7 days has a clip
- **THEN** the sheet says "No door openings with a clip in the last 7 days." and "Use this frame" is disabled

#### Scenario: Recent clip won't load
- **WHEN** the selected clip fails to load
- **THEN** the sheet says "This clip can't be played" and "Use this frame" is disabled

#### Scenario: Frame can't be grabbed
- **WHEN** drawing the frame fails
- **THEN** the sheet says "This frame can't be used. Try another clip." and no request is sent

#### Scenario: Faces can't be blurred
- **WHEN** `POST /api/camera/frame` answers 502
- **THEN** the sheet says "Faces couldn't be blurred, so this frame can't be used." and no image is shown for drawing

#### Scenario: Cancel the recent clip picker
- **WHEN** the owner taps "Cancel" in the sheet
- **THEN** the sheet closes, no image is shown for drawing, and `POST /api/camera/frame` is not requested
