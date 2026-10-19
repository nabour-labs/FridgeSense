## Purpose

Measures how well the item analysis tells items put into the fridge apart from items taken out, by scoring recorded Nova answers for real openings against hand-confirmed labels.

## ADDED Requirements

### Requirement: Opening labels fixture
The repository SHALL hold `backend/tests/fixtures/analysis_eval/labels.json`, shaped `{"openings": {"<window start_ms>": {"added": [{"item", "quantity", "also"?}], "removed": [...], "note"?, "skip"?}}}`. `also` lists other names that count as the same item. `skip` gives the reason an opening could not be judged; a skipped opening needs no `added`/`removed`. Loading SHALL reject a malformed file with an error naming the opening and the problem. The file SHALL hold no images, video or personal data.

#### Scenario: Valid labels load
- **WHEN** opening `1790000000000` is labelled `{"added": [], "removed": [{"item": "chocolate milk", "quantity": 1, "also": ["chocomilk"]}]}`
- **THEN** loading returns one removed item `chocolate milk` (quantity 1, alias `chocomilk`) and no added items for it

#### Scenario: Nothing moved
- **WHEN** an opening is labelled `{"added": [], "removed": []}`
- **THEN** it loads as an opening where nothing moved

#### Scenario: Bad quantity
- **WHEN** a labelled item has `quantity = 0` or no `item`
- **THEN** loading fails with an error naming that opening and the field

#### Scenario: Opening that could not be judged
- **WHEN** an opening is labelled `{"skip": "item not visible in the clip"}`
- **THEN** it loads as skipped with that reason

### Requirement: Recorded answers as fixtures
Recorded answers SHALL be stored per run under `backend/tests/fixtures/analysis_eval/<run name>/<window start_ms>.json`, each holding the `record_fridge_changes` tool input. `baseline/` SHALL hold the answers the pipeline gave the 12 labelled openings on 2026-10-18, from their Nova call traces. A run SHALL be scored with the analysis's own parsing and direction rules for its answer shape.

#### Scenario: Baseline answers in the old shape
- **WHEN** `baseline/1792368091888.json` holds `{"added": [{"item": "milk", ...}], "removed": [{"item": "soda can", ...}]}`
- **THEN** scoring reads it as added `milk` and removed `soda can`

#### Scenario: New answers in the evidence shape
- **WHEN** a run's answer holds `items` with `going_in`/`coming_out` flags
- **THEN** scoring uses the directions and drops that the analysis would apply

#### Scenario: Missing answer
- **WHEN** a run has no answer file for a labelled opening
- **THEN** that opening is scored as if the answer were empty, and the report lists it as missing

### Requirement: Direction-aware score
For each opening, a predicted change SHALL match a labelled one when the direction is the same and the normalized names are equal, either directly or through `also`. The report SHALL give, per opening and in total, true positives, false positives and false negatives (counting items, not quantities), plus direction errors: a name that matches but has the opposite direction. It SHALL also give precision and recall rounded to 3 places.

#### Scenario: Perfect opening
- **WHEN** an opening is labelled added `soda can` and the answer is added `Soda  Can`
- **THEN** that opening has 1 true positive, 0 false positives, 0 false negatives

#### Scenario: Inventory echo
- **WHEN** an opening is labelled added `soda can`, and the answer is added `soda can`, `milk`, `eggs` and removed `bread`
- **THEN** that opening has 1 true positive, 3 false positives and 0 false negatives

#### Scenario: Direction flipped
- **WHEN** an opening is labelled removed `soda can` and the answer is added `soda can`
- **THEN** that opening has 0 true positives, 1 false positive, 1 false negative and 1 direction error

#### Scenario: Alias matches
- **WHEN** a label has `item = "chocolate milk"`, `also = ["chocomilk"]`, and the answer removes `chocomilk`
- **THEN** it is a true positive

#### Scenario: Totals
- **WHEN** a run over 2 openings has 3 true positives, 1 false positive and 2 false negatives in total
- **THEN** the report's totals are precision `0.75` and recall `0.6`

#### Scenario: Skipped openings left out of the totals
- **WHEN** a run covers 3 labelled openings and 1 skipped opening that its answer gets wrong
- **THEN** the totals count only the 3 labelled openings, and the report lists the skipped opening with its reason

#### Scenario: Nothing predicted and nothing labelled
- **WHEN** every opening is labelled empty and every answer is empty
- **THEN** precision and recall are reported as `null`, not as an error

### Requirement: Eval report command
`uv run python scripts/analysis_eval.py --run <name>[,<name>…]` SHALL print, for each run, a table of the labelled openings with the per-opening counts, then totals. It SHALL read only fixtures and SHALL make no network call. Only with `--live <run name>` SHALL it call Bedrock. In that mode it analyzes each labelled opening's clip from the local clips folder and writes the answers under that run name, then prints the total cost.

#### Scenario: Compare baseline with a new run
- **WHEN** the developer runs `--run baseline,video-v1` and both runs have answers for all 12 openings
- **THEN** two tables are printed, each ending with total TP, FP, FN, direction errors, precision and recall

#### Scenario: Offline by default
- **WHEN** the report runs without `--live` while every outbound request is set to fail
- **THEN** it completes without any request reaching the network

#### Scenario: Live run needs clips
- **WHEN** `--live video-v1` is given and a labelled opening's clip is not in the clips folder
- **THEN** that opening is skipped with a message naming the missing file, no Bedrock call is made for it, and the others run

### Requirement: Eval clips stay local
Clips and stills of labelled openings SHALL be read only from the local clips folder (`FRIDGESENSE_CLIPS_DIR`, default the repository's `tmp/`). They SHALL NOT be committed or uploaded anywhere other than the live run's Bedrock request.

#### Scenario: Eval clips ignored by git
- **WHEN** `tmp/analysis-eval/1792368091888.mp4` exists
- **THEN** `git check-ignore` reports it as ignored
