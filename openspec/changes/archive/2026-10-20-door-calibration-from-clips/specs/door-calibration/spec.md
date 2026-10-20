# Spec Delta

## ADDED Requirements

### Requirement: Door zones and references record their picture's source
`POST /api/door-calibration/zones`, `PATCH /api/door-calibration/zones/{id}` (when it changes the box) and `POST /api/door-calibration/references` SHALL accept an optional `source`, either `"clip"` (a frame of a recorded event clip) or `"live"` (a live-view frame or Ring still). It defaults to `"live"`. `GET /api/door-calibration` SHALL list each zone's and reference's `source`. Zones and references stored before this change SHALL read as `"live"`.

#### Scenario: Reference from a clip
- **WHEN** the owner posts a reference with zone Z, status `closed` and `source = "clip"`
- **THEN** the response lists that reference with `source = "clip"`

#### Scenario: Source left out
- **WHEN** a zone is posted without `source`
- **THEN** it is stored and listed with `source = "live"`

#### Scenario: Unknown source
- **WHEN** `source` is `"upload"` or `3`
- **THEN** the response is 400 `{"error": "source must be clip or live"}` and nothing is stored

#### Scenario: Stored before this change
- **WHEN** the table holds a zone and a reference with no `source` field
- **THEN** `GET /api/door-calibration` lists both with `source = "live"`

#### Scenario: Rename keeps the source
- **WHEN** zone Z has `source = "clip"` and the owner sends `PATCH` with only a new name
- **THEN** Z keeps `source = "clip"`

#### Scenario: Redraw on a live picture
- **WHEN** zone Z has `source = "clip"` and the owner sends `PATCH` with a new box and no `source`
- **THEN** Z's `source` becomes `"live"`

### Requirement: Setup needs zones and references from clips
`POST /api/door-calibration/run` SHALL fail when any zone or any reference has `source = "live"`. It answers 422 with the `references` as in other setup failures, and the stored setup result stays unchanged. For a zone the error is `"zone <name> was drawn on a live picture. Redraw it on a frame from a recent clip."`. For a reference it is `"reference <n> is not from a recorded clip. Replace it with a frame from a recent clip."`, with `n` its 1-based position in `references`. Zones are checked first.

#### Scenario: Live reference refused
- **WHEN** zone "Doors" has `source = "clip"`, and its references are an open one from a clip and, listed second, a closed one with `source = "live"`
- **THEN** the response is 422 `{"error": "reference 2 is not from a recorded clip. Replace it with a frame from a recent clip.", "references": [...]}` and the stored setup is unchanged

#### Scenario: Live zone refused
- **WHEN** zone "Doors" has `source = "live"` and all its references are from clips
- **THEN** the response is 422 with `error = "zone Doors was drawn on a live picture. Redraw it on a frame from a recent clip."`

#### Scenario: Everything from clips
- **WHEN** every zone and reference has `source = "clip"` and each zone has an open and a closed reference that separate
- **THEN** setup runs as before and answers 200

### Requirement: Fridge light measured strictly in setup
Wherever setup, reference scores and self-tuning measure the `blue` feature, a pixel SHALL count as blue-lit only when `max(R,G,B) − min(R,G,B) > 100`, `max(R,G,B) > 120` and `B − max(R,G) > 60`, the same rule the door check uses. This replaces the `blue` thresholds given in "Run setup". The `color`, `brightness` and `change` features are unchanged.

#### Scenario: Daylit steel is not fridge light
- **WHEN** a zone of a closed reference is grey except a `(110,150,200)` area covering 30% of it
- **THEN** that reference's `blue` value is 0.0

#### Scenario: Fridge interior is fridge light
- **WHEN** a zone of an open reference is grey except a `(40,90,200)` block covering 10% of it
- **THEN** that reference's `blue` value is about 0.1

### Requirement: Fridge light preferred in setup
When choosing a zone's feature, setup SHALL use `blue` whenever `blue` separates the zone's open and closed references by at least the minimum margin of 0.01, even if another feature has a larger margin. Only when `blue` does not separate does the zone use the feature with the largest margin, with ties in the order color, change, brightness. Re-tuning from event samples SHALL choose the same way.

#### Scenario: Blue wins over a larger change margin
- **WHEN** in a zone `blue` separates with margin 0.04 and `change` separates with margin 0.09
- **THEN** that zone's feature is `blue`, with the threshold at the midpoint of `blue`'s two values

#### Scenario: Blue too close to call
- **WHEN** in a zone `blue` separates with margin 0.005 and `change` with margin 0.09
- **THEN** that zone's feature is `change`

#### Scenario: Drawer without fridge light
- **WHEN** a drawer zone's open and closed references both have a `blue` value of 0.0, and `change` separates with margin 0.2
- **THEN** that zone's feature is `change`

#### Scenario: Re-tune keeps blue
- **WHEN** the owner's references plus the event samples separate a zone on `blue` by 0.03 and on `brightness` by 0.2
- **THEN** the tuned rule for that zone uses `blue`
