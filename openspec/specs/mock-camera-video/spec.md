# mock-camera-video Specification

## Purpose
Lets the developer take camera snapshots from local fridge recordings while running the app on the local dev server, so setup screens can be built and tested without standing at the fridge.

## Requirements

### Requirement: Debug mode only on the dev server
The PWA SHALL be in debug mode whenever it is served by the local dev server, and SHALL never be in debug mode in the production build. In debug mode a "Debug" bar under the header shows a "Mock video" switch (`role="switch"`). Outside debug mode neither the bar nor the switch exists.

#### Scenario: Dev server
- **WHEN** the signed-in owner opens the app from the dev server
- **THEN** the "Debug" bar and an unchecked "Mock video" switch are shown

#### Scenario: Production build
- **WHEN** the app runs from the production build
- **THEN** no "Debug" bar and no "Mock video" switch are rendered, and `/__dev/videos` is never requested

### Requirement: Mock video switch is remembered
The "Mock video" switch SHALL be off by default and SHALL keep its state in this browser across reloads. If browser storage is unavailable, the switch SHALL still work for the current page and start off.

#### Scenario: Turned on, then reload
- **WHEN** the developer turns "Mock video" on and reloads the page
- **THEN** the switch is still on

#### Scenario: Storage blocked
- **WHEN** reading or writing browser storage throws
- **THEN** the switch starts off, can be turned on, and no error is shown

### Requirement: Snapshots come from a clip while the switch is on
While "Mock video" is on, every camera snapshot request in the app SHALL open the clip picker instead of taking a live frame or calling `POST /api/camera/snapshot`. This covers "Camera snapshot" in Reference images, and in Open/close detection and Fridge area both the snapshot taken when the add or set-area sheet opens and "New snapshot". While it is off, snapshots are taken from a live frame, with `POST /api/camera/snapshot` as the fallback.

#### Scenario: Reference image from a clip
- **WHEN** the switch is on and the owner taps "Camera snapshot" in Reference images, picks a frame and taps "Use this frame"
- **THEN** `POST /api/camera/live`, `POST /api/camera/frame` and `POST /api/camera/snapshot` are not requested and the reference form shows that frame as its image

#### Scenario: Door reference from a clip
- **WHEN** the switch is on and the owner taps "Add" in Open/close detection
- **THEN** the clip picker opens, and after "Use this frame" the frame is shown for drawing the door box

#### Scenario: Switch off
- **WHEN** the switch is off and the owner taps "Camera snapshot"
- **THEN** `POST /api/camera/live` is requested once and no clip picker opens

#### Scenario: Cancel
- **WHEN** the clip picker is open and the owner taps "Cancel" or closes the sheet
- **THEN** the picker closes, the screen shows no new snapshot and no error message, and no request is made

### Requirement: Clip picker
The clip picker SHALL list the available clips newest first in a dropdown, play the selected clip with a scrubber, and offer "Use this frame" and "Cancel". "Use this frame" SHALL return the frame shown at the scrubber position as a JPEG at most 960 px wide (aspect kept), with `captured_at` set to the time it was taken. When the dev server proxies to a deployed backend, the picker SHALL show the notice "Frames are not face-blurred and will be uploaded if you save them."

#### Scenario: Clips listed
- **WHEN** the videos folder holds `Ring_Fridge_20261015_1920.mp4` and `Ring_Fridge_20261015_2025.mp4`
- **THEN** the dropdown lists `Ring_Fridge_20261015_2025.mp4` first, and it is selected

#### Scenario: Frame size
- **WHEN** the selected clip is 2560×1440 and the owner taps "Use this frame"
- **THEN** the returned snapshot is a base64 JPEG of 960×540

#### Scenario: No clips
- **WHEN** the videos folder holds no `.mp4` files or does not exist
- **THEN** the picker says "No clips in the videos folder" and "Use this frame" is disabled

#### Scenario: Clip won't load
- **WHEN** the selected clip fails to load in the browser
- **THEN** the picker says "This clip can't be played" and "Use this frame" is disabled

#### Scenario: Deployed backend notice
- **WHEN** the dev server proxies `/api` to a deployed backend
- **THEN** the picker shows "Frames are not face-blurred and will be uploaded if you save them."

#### Scenario: Mock API has no notice
- **WHEN** the dev server uses the mock API
- **THEN** the picker shows no upload notice

### Requirement: Livestream plays a clip while the switch is on
While "Mock video" is on, the "Livestream" dialog SHALL play a clip from the videos folder instead of opening a live view. It shows a clip dropdown (newest first, newest selected), a "Mock video" label, and the selected clip playing muted on a loop. It SHALL NOT request `POST /api/camera/live` or `DELETE /api/camera/live/{id}`. While the switch is off, the dialog behaves as before.

#### Scenario: Livestream from a clip
- **WHEN** the switch is on, the folder holds `Ring_Fridge_20261015_1920.mp4` and `Ring_Fridge_20261015_2025.mp4`, and the owner taps "Livestream"
- **THEN** the dialog shows "Mock video", a `<video>` with `src = "/__dev/videos/Ring_Fridge_20261015_2025.mp4"` that is muted and loops, and `POST /api/camera/live` is not requested

#### Scenario: Change clip
- **WHEN** the owner picks `Ring_Fridge_20261015_1920.mp4` in the dialog's dropdown
- **THEN** the video's `src` becomes `/__dev/videos/Ring_Fridge_20261015_1920.mp4`

#### Scenario: Livestream with no clips
- **WHEN** the switch is on and the folder holds no `.mp4` files
- **THEN** the dialog says "No clips in the videos folder" and makes no request to `/api/camera/live`

#### Scenario: Livestream switch off
- **WHEN** the switch is off and the owner taps "Livestream"
- **THEN** `POST /api/camera/live` is requested as before and no clip dropdown is shown

### Requirement: Dev-server clip routes
The dev server SHALL serve `GET /__dev/videos`, returning `{"clips": [{"name", "size", "url"}], "upload": bool}` for each `.mp4` in the videos folder (`FRIDGESENSE_VIDEOS`, default `<repo>/tmp`), newest name first. `upload` is true when `/api` is proxied to a deployed backend. `GET /__dev/videos/<name>` SHALL stream that file as `video/mp4`, honouring `Range` with 206. Names with a path separator, `..`, or not ending in `.mp4`, or files that do not exist, SHALL get 404. These routes SHALL not exist in the production build.

#### Scenario: Listing
- **WHEN** the folder holds `a.mp4` (10 bytes), `b.mp4` (20 bytes) and `notes.txt`
- **THEN** `GET /__dev/videos` answers 200 with clips `b.mp4` then `a.mp4`, their sizes and `url = "/__dev/videos/b.mp4"` etc., and no `notes.txt`

#### Scenario: Missing folder
- **WHEN** the videos folder does not exist
- **THEN** `GET /__dev/videos` answers 200 with `clips = []`

#### Scenario: Range request
- **WHEN** `GET /__dev/videos/a.mp4` is sent with `Range: bytes=2-5`
- **THEN** the answer is 206 with `Content-Range: bytes 2-5/10`, `Content-Type: video/mp4` and the 4 bytes at offsets 2–5

#### Scenario: Whole file
- **WHEN** `GET /__dev/videos/a.mp4` is sent without `Range`
- **THEN** the answer is 200 with `Accept-Ranges: bytes` and all 10 bytes

#### Scenario: Path escape refused
- **WHEN** `GET /__dev/videos/..%2F.env` or `GET /__dev/videos/notes.txt` is requested
- **THEN** the answer is 404 and no file outside the folder is read

#### Scenario: Unknown clip
- **WHEN** `GET /__dev/videos/missing.mp4` is requested
- **THEN** the answer is 404
