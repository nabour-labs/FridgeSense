# Results

Door check on the 12 local clips (Oct 15, 2026), default config: blue feature, default zones, threshold 0.01, frames every 500 ms from the clip.

```
uv run --group clips python scripts/door_clip_report.py
```

| | Stills (before) | Clip frames (now) |
|---|---|---|
| TP / FP / FN / TN | 9 / 0 / 0 / 3 (one opening missed, hidden as TN) | 10 / 0 / 0 / 2 |
| Mean / max open error | 1.09 s / 3.80 s | 0.31 s / 0.60 s |
| Mean / max close error | 0.82 s / 1.96 s | 0.32 s / 0.70 s |

Three labels were corrected after checking frames 0.25 s apart, because the draft labels came from stills 3–4 s apart:

- 2009: opened 5.0 → 6.0 s. The door is shut at 5.75 s and ajar at 6.0 s.
- 2017: 22.3–26.4 → 21.0–25.1 s. The drawer glow shows from 21.0 s to 25.0 s.
- 2023: none → 63.4–66.4 s. The left door is ajar at 63.25 s and shut by 66.5 s. Stills missed this opening.

All 12 `-m clips` tests pass at the new tolerance of 0.75 s (1.5 × 500 ms).

Not measured yet: decode time and memory on Lambda arm64, and how often Ring has a clip for a motion event. The one real probe got `416 MEDIA_NOT_FOUND` from the link. Both show up in the `clip_frames` and `clip_unavailable` logs after deploy.
