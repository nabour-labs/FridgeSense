# Spec Delta

## Purpose
Door rules learn from recent door events: closed and open samples per zone, and rules re-tuned from those samples.

## ADDED Requirements

### Requirement: Event sampling memory stays bounded
Sampling an event SHALL hold at most 2 decoded frames at any time, however many frames the event has: the closed bookend and the frame being scored. A long door opening, such as a 240-frame clip at 2K, SHALL NOT need more memory to sample than a short one. The stored samples SHALL be the same as when every frame is decoded together.

#### Scenario: Long event sampled with two frames decoded
- **WHEN** an aligned event with 240 frames is sampled for a one-zone setup
- **THEN** a sample is stored, and no more than 2 decoded frames were alive at any moment while it was taken

#### Scenario: Several zones share one pass
- **WHEN** an aligned event with 40 frames is sampled for a two-zone setup, where the left zone opens at frame 10 and the right zone at frame 30
- **THEN** each zone's open sample comes from its own frame, and no more than 2 decoded frames were alive at any moment

