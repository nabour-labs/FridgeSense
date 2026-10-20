# Spec Delta

## ADDED Requirements

### Requirement: Proof photos in Recent changes
A Recent changes row whose opening has changes SHALL show, under its labels, one photo per change that has a `proof` link (its first link), in the order of the labels, at most 3. Rejected changes SHALL add no photo. A row showing "Checking…" or "No changes" SHALL show no photos. A photo SHALL have an empty `alt`, since the labels already name the change.

#### Scenario: Proof under the labels
- **WHEN** an opening added 2 milk with `proof` ["https://s3/a.jpg", "https://s3/b.jpg"] and removed eggs with `proof` ["https://s3/c.jpg"]
- **THEN** its row shows two `img` elements, with `src` "https://s3/a.jpg" then "https://s3/c.jpg"

#### Scenario: At most three photos
- **WHEN** an opening has 5 changes, each with a `proof` link
- **THEN** its row shows the photos of the first 3 changes only

#### Scenario: Change without proof
- **WHEN** an opening added milk with no `proof` and removed eggs with `proof` ["https://s3/c.jpg"]
- **THEN** its row shows one `img`, "https://s3/c.jpg"

#### Scenario: Rejected change has no photo
- **WHEN** an opening's only change with a `proof` link is rejected
- **THEN** its row shows no `img`

#### Scenario: No photos without changes
- **WHEN** a row shows "Checking…" or "No changes", and its opening has `stills`
- **THEN** that row shows no `img`

### Requirement: Latest still in the header
The header SHALL show the last link in `stills` of the newest loaded opening that has any stills, with the caption "Latest still · <local clock time the opening opened>" (e.g. "Latest still · 8:42 pm"). The picture SHALL have the `alt` text "Latest still from the fridge camera". With no opening that has stills, the header SHALL show no picture and no caption. It SHALL change only when the events refresh brings a newer still.

#### Scenario: Newest opening's last still
- **WHEN** the newest opening, at 8:42 pm local time, has `stills` ["https://s3/1.jpg", "https://s3/2.jpg", "https://s3/3.jpg"]
- **THEN** the header shows an `img` with `src` "https://s3/3.jpg" and the caption "Latest still · 8:42 pm"

#### Scenario: Newest opening has no stills
- **WHEN** the newest opening has empty `stills` and the one before it, at 7:10 pm, has `stills` ["https://s3/x.jpg"]
- **THEN** the header shows "https://s3/x.jpg" and "Latest still · 7:10 pm"

#### Scenario: No stills at all
- **WHEN** no loaded opening has stills
- **THEN** the header has no "Latest still from the fridge camera" image and no "Latest still" caption

#### Scenario: Events fail
- **WHEN** `GET /api/events` fails before any openings have loaded
- **THEN** the header shows no latest still, and the camera line still shows

### Requirement: Photos load quietly
A photo on the TV dashboard (proof or latest still) that fails to load SHALL be removed instead of showing a broken image, without affecting the rest of its row or header. When an events refresh returns a new link for the same picture (same address without its query string) that is already shown, the TV dashboard SHALL keep showing it with its current link, so it is not downloaded again.

#### Scenario: Broken link hidden
- **WHEN** a proof photo's `img` fires an `error` event
- **THEN** that `img` is removed, and the row's labels and its other photos stay

#### Scenario: Header still fails
- **WHEN** the latest still's `img` fires an `error` event
- **THEN** the picture and its caption are removed, and the title, "Updated" time and camera line stay

#### Scenario: Re-signed link kept
- **WHEN** a proof photo is shown with `src` "https://s3/a.jpg?X-Amz-Signature=1" and the next events refresh returns "https://s3/a.jpg?X-Amz-Signature=2" for it
- **THEN** its `img` `src` is still "https://s3/a.jpg?X-Amz-Signature=1"

#### Scenario: New picture replaces the old
- **WHEN** the latest still is "https://s3/3.jpg?sig=1" and a refresh brings a newer opening whose last still is "https://s3/9.jpg?sig=2"
- **THEN** the header `img` `src` is "https://s3/9.jpg?sig=2"

## MODIFIED Requirements

### Requirement: Nothing private or interactive on the TV dashboard
The TV dashboard SHALL show no clips, video, live view, reference images, camera snapshots or the camera's product image; the only pictures it SHALL show are door-opening stills and proof photos from `GET /api/events`. It SHALL have no buttons, links or inputs. It SHALL request only `GET /api/inventory`, `GET /api/events` and `GET /api/camera`, and SHALL NOT handle the Back (Escape) key, so the Fire TV app can close on Back.

#### Scenario: No clips or video
- **WHEN** an opening in the list has a `clip` link
- **THEN** the TV dashboard contains no `video` element and nothing pointing at the clip

#### Scenario: Only opening pictures shown
- **WHEN** the TV dashboard is shown with openings that have `stills` and change `proof` links
- **THEN** every `img` `src` on the dashboard is one of those links

#### Scenario: Camera image not shown
- **WHEN** `GET /api/camera` returns an `image_url`
- **THEN** the TV dashboard contains no `img` element pointing at it

#### Scenario: No controls
- **WHEN** the TV dashboard is shown with items, openings with photos and camera details
- **THEN** it contains no button, link or input

#### Scenario: Only three endpoints
- **WHEN** the TV dashboard has loaded and refreshed once
- **THEN** the only API calls made are `inventory`, `events` and `camera`, and `POST /api/camera/snapshot` is never requested

#### Scenario: Back is left to the TV app
- **WHEN** the Escape key is pressed on the TV dashboard
- **THEN** the event is not default-prevented and the hash stays `#tv`
