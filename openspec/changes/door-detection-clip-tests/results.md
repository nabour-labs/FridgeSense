# Results

Door check on the 12 local clips (Oct 15, 2026), default config: blue feature, default zones, threshold 0.01, still interval 1000 ms. Scored against the labels Jayson accepted as drafted on 2026-10-16 (task 5.2).

```
uv run --group clips python scripts/door_clip_report.py
```

| Clip | Verdict | Labelled | Detected | Open err | Close err |
|---|---|---|---|---|---|
| 1920 (3 openings merged) | TP | 5.0–23.6 s | 5.7–24.3 s | +0.7 | +0.7 |
| 1921 (2 openings merged) | TP | 3.4–12.2 s | 3.9–12.7 s | +0.5 | +0.5 |
| 1926 | TP | 1.8–27.1 s | 2.3–26.6 s | +0.5 | −0.5 |
| 1930 | TP | 16.9–26.9 s | 17.5–27.5 s | +0.6 | +0.6 |
| 1932 | TP | 7.8–19.1 s | 8.5–19.8 s | +0.7 | +0.7 |
| 1934 | TP | 5.3–7.3 s | 5.8–7.7 s | +0.5 | +0.4 |
| 1947 | TP | 5.4–15.3 s | 5.9–15.8 s | +0.5 | +0.5 |
| 2009 | TP | 5.0–10.3 s | 8.8–11.7 s | +3.8 | +1.4 |
| 2017 | TP | 22.3–26.4 s | 24.3–28.4 s | +2.0 | +2.0 |
| 2021 | TN | – | – | | |
| 2023 | TN | – | – | | |
| 2025 | TN | – | – | | |

**TP 9  FP 0  FN 0  TN 3.** Open error: mean 1.09 s, max 3.80 s. Close error: mean 0.82 s, max 1.96 s. All 12 `-m clips` tests pass. On the long clips (2009, 2017) the 30-still cap spaces stills about 3–4 s apart, so the tolerance widens to match.

Sweep (`--threshold 0.005,0.01,0.02 --interval 500,1000`): every combination gives TP 9, FP 0, FN 0, TN 3. Mean open/close error is about 1.07/0.84 s at thresholds 0.005 and 0.01, and 1.2/1.1 s at 0.02. The 500 ms interval barely helps, because most clips are long enough to hit the still cap.

Caveats: the labels for 2009, 2017, 2021, 2023 and 2025 came from stills 3–4 s apart. The default zones were measured on one of these clips. All clips are from one evening.
