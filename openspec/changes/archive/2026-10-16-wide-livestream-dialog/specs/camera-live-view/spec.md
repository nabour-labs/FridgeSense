## ADDED Requirements

### Requirement: Wide Livestream dialog
The "Livestream" dialog SHALL be wider than the app's other dialogs on screens `sm` and up: up to 768 px (`sm:max-w-3xl`) instead of 448 px (`max-w-md`), with the video filling its width at 16:9. This applies both to the live camera view and to the Mock video clip player. Other dialogs SHALL keep the 448 px width. On phones every dialog stays a full-width bottom sheet.

#### Scenario: Livestream dialog is wide
- **WHEN** the user opens the "Livestream" dialog
- **THEN** the dialog has the `sm:max-w-3xl` width and not `max-w-md`

#### Scenario: Mock video Livestream is wide
- **WHEN** Mock video is on and the user opens the "Livestream" dialog
- **THEN** the dialog has the `sm:max-w-3xl` width and not `max-w-md`

#### Scenario: Other dialogs keep their width
- **WHEN** any other sheet dialog opens
- **THEN** it has the `max-w-md` width
