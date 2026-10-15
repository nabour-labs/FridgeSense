# Spec Delta

## MODIFIED Requirements

### Requirement: One Nova request per door opening
For a door opening, the system SHALL send one Bedrock Converse request to the configured model (default `us.amazon.nova-2-lite-v1:0`) containing the stills in time order (each preceded by a text label `Image <n> of <total>`), then a final text with the instructions and the current inventory's item names in square brackets, with `temperature` 0 and the tool `record_fridge_changes` forced. When the account has reference images or custom instructions, the request SHALL also carry them as set out in the requirement "Owner's config sent with each analysis".

#### Scenario: Request built from stills and inventory
- **WHEN** a door opening has stills 1–4 and the inventory holds `milk` and `eggs`
- **THEN** the request's content is `Image 1 of 4`, still 1, `Image 2 of 4`, still 2, … still 4, then a text containing `[milk, eggs]`; `toolConfig.toolChoice` is `{"tool": {"name": "record_fridge_changes"}}`; `inferenceConfig.temperature` is 0

#### Scenario: Empty inventory
- **WHEN** the inventory is empty
- **THEN** the final text contains `[]`

#### Scenario: Stills sent as bytes
- **WHEN** the request is built
- **THEN** each image block is `{"format": "jpeg", "source": {"bytes": <the stored still>}}` and at most 4 images are sent

## ADDED Requirements

### Requirement: Owner's config sent with each analysis
When the account has reference images, the request SHALL begin with the text `Reference images: examples of items in this fridge. They are not part of this door opening.`, then, oldest first, `Reference <n>: <annotation>` followed by that image. The stills follow as before. Custom instructions SHALL be appended to the final text, after the inventory and before the tool instruction, as `Owner's instructions: <text>`.

#### Scenario: References before stills
- **WHEN** the account has references "milk bag" (added first) and "soda can", and the door opening has stills 1–4
- **THEN** the content starts with the reference header text, `Reference 1: milk bag`, its image, `Reference 2: soda can`, its image, and then `Image 1 of 4`, still 1, … still 4 and the final text

#### Scenario: Reference images as bytes
- **WHEN** references are sent
- **THEN** each reference image block is `{"format": "jpeg", "source": {"bytes": <the stored reference bytes>}}`, and the 4-still limit still applies to the stills alone

#### Scenario: Custom instructions in the final text
- **WHEN** the custom instructions are `Count yogurt cups individually.`
- **THEN** the final text contains `Owner's instructions: Count yogurt cups individually.` after the inventory list, and still ends by asking to call `record_fridge_changes`

#### Scenario: No config
- **WHEN** the account has no references and empty custom instructions
- **THEN** the request is identical to one built without config: no reference header and no `Owner's instructions` text

#### Scenario: Config changed between openings
- **WHEN** a reference is deleted after one door opening and before the next
- **THEN** the next opening's request no longer includes that reference
