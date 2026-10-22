## MODIFIED Requirements

### Requirement: Nova call trace
When `DEBUG_TRACES` is not `false`, each Converse attempt of a door opening's analysis SHALL write `nova-<run_ms>-<attempt>.json` in the event's `debug/` folder. It holds `request.content` in request order: text blocks `{"type": "text", "text"}`, images `{"type": "image", "role": "reference" | "still", "n", "key"}`, the analysis video as `{"type": "video", "frames", "frame_ms", "bytes"}` with no `key`, and `{"type": "cache_point"}`. It also holds `model_id`, `inferenceConfig`, `toolConfig` and the raw `response` (`output`, `stopReason`, `usage`, `metrics`).

#### Scenario: Request with references
- **WHEN** an analysis sends 2 reference images (annotations "oat milk", "eggs") and 4 stills with the inventory `[milk]`
- **THEN** `request.content` lists, in order: the reference header, "Reference 1: oat milk", image reference 1, "Reference 2: eggs", image reference 2, then "Image 1 of 4", image still 1 … "Image 4 of 4", image still 4, then the instruction text containing `[milk]`

#### Scenario: Image keys are retrievable
- **WHEN** that request is traced
- **THEN** each still image's `key` is the stored `still-<n>.jpg` sent to Nova, and each reference image's `key` is a `nova-<run_ms>-ref-<n>.jpg` object holding the exact reference bytes sent

#### Scenario: Video traced without a key
- **WHEN** an analysis sends an 11-frame analysis video of 412 000 bytes with `frame_ms = 500`
- **THEN** `request.content` has `{"type": "video", "frames": 11, "frame_ms": 500, "bytes": 412000}` where the video was sent, no trace entry has a `key` or `url` for `analysis.mp4`, and no copy of the video is written to `debug/`

#### Scenario: Owner's instructions shown
- **WHEN** the owner's instructions are "Ignore condiments"
- **THEN** the final text block contains `Owner's instructions: Ignore condiments`

#### Scenario: Response kept
- **WHEN** Nova answers with tool input `{"observations": "Hand puts milk in.", "items": [{"item": "milk", ...}]}` and `stopReason = "tool_use"`
- **THEN** the trace's `response.output` holds that tool input, observations included, and `response.stopReason = "tool_use"`
