## MODIFIED Requirements

### Requirement: One Nova request per door opening
For a door opening, the system SHALL send one Bedrock Converse request to the configured model (default `us.amazon.nova-2-lite-v1:0`) with `temperature` 0 and the tool `record_fridge_changes` forced. The media SHALL be the analysis video when the door opening has one (see "Analysis video sent when available"), otherwise the stills in time order, each preceded by a text label `Image <n> of <total>`. A final text with the hand-evidence instructions and the inventory's item names in square brackets comes last. When the account has reference images or custom instructions, the request SHALL also carry them as set out in the requirement "Owner's config sent with each analysis".

#### Scenario: Request built from stills and inventory
- **WHEN** a door opening has no analysis video, has stills 1–4, and the inventory holds `milk` and `eggs`
- **THEN** the request's content is `Image 1 of 4`, still 1, `Image 2 of 4`, still 2, … still 4, then a text containing `[milk, eggs]`; `toolConfig.toolChoice` is `{"tool": {"name": "record_fridge_changes"}}`; `inferenceConfig.temperature` is 0

#### Scenario: Empty inventory
- **WHEN** the inventory is empty
- **THEN** the final text contains `[]`

#### Scenario: Stills sent as bytes
- **WHEN** the request is built from stills
- **THEN** each image block is `{"format": "jpeg", "source": {"bytes": <the stored still>}}` and at most 4 images are sent

#### Scenario: Hand-evidence instructions
- **WHEN** any analysis request is built
- **THEN** the final text says to report only items seen in a person's hand crossing the fridge opening, says that items resting on shelves or in the door are not changes, introduces the inventory as `Names already in the inventory (reuse them for the same kind of item; do not report them unless you see them carried): [...]`, and does not contain the word `Compare`

### Requirement: Answer validated before use
The system SHALL read the `toolUse.input` named `record_fridge_changes` from anywhere in the response content and accept it only if `items` is a list of objects with a non-empty `item`. `observations` SHALL default to `""` when missing or not a string. Each item SHALL be normalized: unknown `category` becomes `"other"`, missing or non-positive `quantity` becomes 1, `confidence` is clamped to 0–1 (missing: 0), and `going_in` and `coming_out` count as true only when they are JSON `true`.

#### Scenario: Valid answer
- **WHEN** Nova returns `stopReason = "tool_use"` with input `{"observations": "A hand puts milk on the top shelf, then takes eggs out.", "items": [{"item": "milk", "category": "dairy", "quantity": 1, "confidence": 0.92, "going_in": true, "coming_out": false, "moments": [2]}, {"item": "eggs", "category": "dairy", "quantity": 2, "confidence": 0.71, "going_in": false, "coming_out": true, "moments": [4]}]}`
- **THEN** the analysis has one added change (milk, dairy, 1, 0.92) and one removed change (eggs, dairy, 2, 0.71)

#### Scenario: Text before the tool call
- **WHEN** the response content is a text block followed by the `toolUse` block
- **THEN** the tool input is still found and used

#### Scenario: Values out of range
- **WHEN** an item has `category = "snacks & treats"`, `quantity = 0`, `confidence = 1.4`, `going_in = true` and `coming_out = false`
- **THEN** it becomes an added change with category `other`, quantity 1, confidence 1.0

#### Scenario: Evidence flags that are not booleans
- **WHEN** an item has `going_in = "yes"` and `coming_out = 1`
- **THEN** both count as false, the item is dropped as `no_hand_evidence`, and the answer is still valid

#### Scenario: Old answer shape
- **WHEN** the tool input is `{"added": [{"item": "milk"}], "removed": []}` with no `items`
- **THEN** the answer is invalid and handled as in "Invalid answer retried once"

#### Scenario: Invalid answer retried once
- **WHEN** the first response has no `record_fridge_changes` tool call (for example `stopReason = "end_turn"` or `"malformed_tool_use"`) or lacks `items`, and the second response is valid
- **THEN** exactly two requests are made and the second answer is used

#### Scenario: Invalid answer twice
- **WHEN** both responses are invalid
- **THEN** the door event's `status` becomes `"analysis_failed"` and the inventory is unchanged

### Requirement: Proof images per change
Each item in the `record_fridge_changes` tool schema SHALL have an optional `moments` array of numbers: image numbers when stills were sent, or seconds from the start of the video when the analysis video was sent. The final instruction text SHALL ask for it. Each change's saved `proof` SHALL hold at most 2 indexes into the door event's stored stills, without duplicates, in time order. With stills, `proof` is the whole numbers from 1 to the number of stills sent, minus 1. With video, each moment within the video maps to the stored still nearest in time. `proof` SHALL only point at the stored stills, which are blurred while face blurring is on, and never at the analysis video or any unblurred frame. A missing, non-list or invalid `moments` SHALL become `proof = []` and SHALL NOT make the answer invalid.

#### Scenario: Schema and prompt ask for images
- **WHEN** the request is built for 4 stills
- **THEN** the tool's item schema has `moments` of type array of number, it is not in `required`, and the final text contains "moments"

#### Scenario: Proof kept
- **WHEN** Nova returns an added `soda can` with `moments = [3, 4]` for 4 stills
- **THEN** the saved door event's change for `soda can` has `proof = [2, 3]`

#### Scenario: Out-of-range, duplicate and extra numbers
- **WHEN** an item has `moments = [0, 2, 2, 5, 3, 4]` and 4 stills were sent
- **THEN** its `proof` is `[1, 2]`

#### Scenario: Non-integer numbers
- **WHEN** an item has `moments = [1.0, "2", true, 2.5]` and stills were sent
- **THEN** its `proof` is `[0]`

#### Scenario: Proof mapped from video seconds
- **WHEN** the analysis video starts at real time `T`, has 20 frames 500 ms apart played at 1 frame per second, the stored stills were taken at `T + 0`, `T + 3000`, `T + 6000` and `T + 9500` ms, and an item has `moments = [7, 12]`
- **THEN** the moments map to `T + 3500` and `T + 6000` ms, and the change's `proof` is `[1, 2]`

#### Scenario: Video moments past the end
- **WHEN** the video has 20 frames and an item has `moments = [-1, 25, "3"]`
- **THEN** its `proof` is `[]` and the answer is still valid

#### Scenario: Images missing or malformed
- **WHEN** one item has no `moments` and another has `moments = "2"`
- **THEN** both are accepted with `proof = []`, and the analysis is not retried

#### Scenario: Proof shown blurred
- **WHEN** face blurring is on, a door opening was analyzed from its analysis video, still 2 had a face blurred, and a change's `proof` is `[1]`
- **THEN** the proof image the front end gets for that change (`GET /api/events`) is a link to the stored, blurred `still-2.jpg`, and no proof link points at `analysis.mp4` or `debug/`

## ADDED Requirements

### Requirement: Direction decided from hand evidence
The system SHALL decide each item's direction from its evidence flags, not from any label Nova gives. Seen going in only means added. Seen coming out only means removed. When both or neither flag is true, the item SHALL be dropped: it is not saved as an applied or pending change, and a `change_dropped` line is logged with the door event, `item` and `reason` (`no_hand_evidence` or `in_and_out`). Confidence only decides applied versus pending for the items that are kept.

#### Scenario: Seen going in
- **WHEN** an item has `going_in = true` and `coming_out = false`
- **THEN** it is an added change

#### Scenario: Seen coming out
- **WHEN** an item has `going_in = false` and `coming_out = true`
- **THEN** it is a removed change

#### Scenario: Item only seen on a shelf
- **WHEN** an item has `going_in = false` and `coming_out = false`
- **THEN** it is dropped, `change_dropped` is logged with `reason = "no_hand_evidence"`, and the inventory is unchanged by it

#### Scenario: Taken out and put back
- **WHEN** an item has `going_in = true` and `coming_out = true`
- **THEN** it is dropped with `reason = "in_and_out"`

#### Scenario: Every item dropped
- **WHEN** all items of a valid answer are dropped
- **THEN** the door event is saved with `status = "done"` and no changes, and the analysis is not retried

#### Scenario: Low confidence with evidence
- **WHEN** an item has `going_in = true`, `coming_out = false` and `confidence = 0.5`
- **THEN** it is saved as a pending added change, as before

### Requirement: Observations come before items
The tool's input schema SHALL list `observations` (a string, described as what the hands did, in time order) before `items`. Both SHALL be in `required`. Each item SHALL require `item`, `category`, `quantity`, `going_in` and `coming_out`. `observations` SHALL be kept in the Nova call trace's response and SHALL NOT be saved on the door event.

#### Scenario: Schema order and required fields
- **WHEN** the tool spec is built
- **THEN** the input schema's property keys are `observations`, `items` in that order, `required` is `["observations", "items"]`, and the item schema's `required` is `["item", "category", "quantity", "going_in", "coming_out"]`

#### Scenario: Observations not stored on the event
- **WHEN** a valid answer has `observations = "Hand takes a soda can from the door shelf."`
- **THEN** the saved door event has no `observations` field

### Requirement: Analysis video sent when available
When the door opening has an analysis video, the request SHALL send it as one block, `{"video": {"format": "mp4", "source": {"bytes": <the stored analysis video>}}}`, preceded by the text `Video of the door opening, slowed down, in time order.`, and SHALL send no stills. Reference images, owner's instructions and cache points stay in place: references before the video, a cache point (when on) right after it. If the analysis video cannot be read, the request SHALL use the stored stills instead.

#### Scenario: Video instead of stills
- **WHEN** the door opening has an analysis video and stills 1–4
- **THEN** the request content has the video text, one video block whose bytes equal the stored `analysis.mp4`, no image block for any still, then the final text

#### Scenario: References before the video
- **WHEN** the account has references "milk bag" and "soda can" and the door opening has an analysis video
- **THEN** the content starts with the reference header, `Reference 1: milk bag`, its image, `Reference 2: soda can`, its image, then the video text and the video block

#### Scenario: Cache point after the video
- **WHEN** `NOVA_CACHE_ANALYSIS` is `true`, there are no references, and the door opening has an analysis video
- **THEN** the content has exactly one `cachePoint` block, placed between the video block and the final text

#### Scenario: Video object missing
- **WHEN** the step input names an analysis video but reading it from S3 fails with `NoSuchKey`
- **THEN** an `analysis_video_missing` warning is logged and the request is built from the stored stills
