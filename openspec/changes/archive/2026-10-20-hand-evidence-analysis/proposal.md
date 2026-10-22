# Proposal

## Why

On the 12 latest openings (2026-10-18), Nova mostly repeated the current inventory list instead of reporting what moved. A 2 s opening came back with 5 items added and 1 removed. A drawer opening where nothing moved came back with 5 items removed. Every change had confidence 0.8–0.9, so the 0.7 cutoff never sent any of them to review, and most changes pointed at the same proof images `[1, 2]`.

The inputs are part of the problem. Nova gets 4 evenly spaced stills, which is one every ~38 s in a 115 s opening, so the moment a hand carries something in or out is usually missed. The stills are 870×1440 crops in which the fridge interior takes up about 15% of the frame. The prompt also says "compare them" when no still shows the fridge before the opening.

## What Changes

- **BREAKING (tool schema):** `record_fridge_changes` no longer returns `added`/`removed` lists. It returns `observations`: a short, time-ordered account of what the hands did. Then it returns `items`, where each item says whether it was seen in a hand going into the fridge, in a hand coming out, and at which moments.
- The code decides the direction from that evidence instead of Nova's own label. Seen going in only → added. Seen coming out only → removed. Both or neither → dropped and logged. Items on the shelves never count.
- The prompt is rewritten around hands crossing the fridge opening. The inventory list becomes a list of names to reuse and is no longer presented as things to compare against.
- When the event clip is available, Nova gets a short **analysis video** of the open span instead of 4 stills. It is built from the frames the door check already decodes, cropped tighter and slowed down so Nova's frame sampling sees every frame. When there is no clip, the analysis falls back to stills as it does today.
- **Tighter crop:** when the device has a fridge area, the analysis video and the stored stills are cropped to that area plus a margin for hands, instead of the wide `STILL_CROP` strip.
- **Face blurring scope changes** (the owner decided this on 2026-10-18): Nova may receive unblurred frames, but every image or clip the front end can show stays blurred. The analysis video is transient. It is never linked or served, and it is deleted after the analysis.
- Proof images still point at the stored, blurred stills. Moments in the video are mapped to the nearest stored still.
- **New labelled eval** of the 12 openings: hand-confirmed ground truth, the recorded "before" answers, and a scorer that reports item precision, recall and direction errors. Tests use only recorded answers. A separate opt-in script runs the new analysis against the downloaded clips.

Out of scope: a different Nova model, prompt caching changes, blurred proof frames taken from the video, picking frames by motion, changes to the PWA, Fire TV.

Track: AWS Builder (Bedrock Nova video understanding, Step Functions), Ring (event clips).

## Capabilities

### New Capabilities
- `analysis-evaluation`: a labelled set of real openings and an offline scorer that measures how well the analysis tells added from removed items.

### Modified Capabilities
- `fridge-change-analysis`: new request shape (video or stills, hand-evidence prompt), a new tool schema, direction derived from evidence, and proof moments.
- `door-event-detection`: builds and stores the transient analysis video. Also adds the fridge-area analysis crop, and changes "Only blurred stills are analyzed" so that only displayed media must be blurred.
- `pipeline-debug-traces`: the Nova call trace records the analysis video block and the observations.

## Impact

- Code: `backend/src/fridgesense/analysis.py` (request, schema, parsing), `door_events.py` (crop box, analysis video, state), `clip_frames.py` (encoding), `inventory.py` (video bytes, proof mapping, deleting the analysis video), `traces.py`, `handlers/pipeline.py`.
- Infra: the analyze Lambda needs `s3:GetObject`/`s3:DeleteObject` on `*/analysis.mp4`. The existing transient-tag lifecycle rule covers runs that die. No new services.
- Cost: there are more image tokens per opening (up to 40 frames instead of 4 stills). The cost per opening is measured once and logged per clip as today.
- Data: the analysis video holds unblurred frames for at most the analyze step. This is allowed by the owner's decision above.
- Ordering: the in-progress `face-blur-setting` change also modifies "Only blurred stills are analyzed". Archive it first, then sync this change's delta onto its wording.
