## ADDED Requirements

### Requirement: Proof stills on Activity
When any change of an event has `proof` links, the event card SHALL show a "Proof" strip with each such change's thumbnails (up to 2), each captioned with the change's label ("+ soda", "− 2 eggs"). The strip SHALL sit beside the clip or stills on screens `sm` and up, and below them on phones. Tapping a thumbnail SHALL open the still viewer on that change's proof stills. Without proof links, no strip SHALL be shown.

#### Scenario: Proof beside the clip
- **WHEN** an event has a `clip` link and a change "+ soda" with 2 `proof` links
- **THEN** the card shows the video and a "Proof" strip with 2 images whose accessible names are "Proof for + soda, 1 of 2" and "Proof for + soda, 2 of 2"

#### Scenario: Several changes
- **WHEN** an event has "+ soda" with 1 proof link and "− 2 eggs" with 2
- **THEN** the strip shows 3 thumbnails, captioned "+ soda" and "− 2 eggs"

#### Scenario: Tap a proof still
- **WHEN** the user taps "Proof for − 2 eggs, 2 of 2"
- **THEN** the still viewer opens on that image, "Next still" is disabled and "Previous still" shows "Proof for − 2 eggs, 1 of 2"

#### Scenario: No proof
- **WHEN** no change of an event has `proof` links
- **THEN** no "Proof" strip is shown, and the clip or stills show as before

#### Scenario: Proof with stills
- **WHEN** an event has `clip: null`, 4 still links and a change with 1 proof link
- **THEN** the 4 still buttons and a "Proof" strip with 1 image are both shown

#### Scenario: Layout by width
- **WHEN** the card is rendered
- **THEN** the media area uses a one-column grid that becomes two columns at `sm` (`sm:grid-cols-[2fr_1fr]`), with the strip in the second column
