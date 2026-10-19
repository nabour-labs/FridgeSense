"""Item analysis accuracy on labelled real openings. Offline unless --live is given.

    uv run python scripts/analysis_eval.py --run baseline
    uv run python scripts/analysis_eval.py --run baseline,video-v1
    uv run python scripts/analysis_eval.py --live video-v1   # calls Bedrock: costs money

Each run is a folder of recorded `record_fridge_changes` tool inputs under
tests/fixtures/analysis_eval/<run>/<window start ms>.json, scored against labels.json:
true and false positives and negatives count items (not quantities) with their direction,
and `dir` counts names that matched a label with the opposite direction.

`--live <run>` builds the analysis video from each labelled opening's local clip
(<clips folder>/analysis-eval/<window start ms>.mp4) with the production crop and encoder,
asks Nova, and writes each tool input to the run's folder. It is the only mode that calls AWS.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/, for tests.analysis_eval

from tests.analysis_eval.harness import (  # noqa: E402
    FIXTURES,
    RunReport,
    eval_clips_dir,
    load_labels,
    load_run,
    score_run,
)

FRIDGE_AREA = (0.362, 0.329, 0.233, 0.611)  # the demo camera's fridge area (2026-10-18)
FRAME_MS = 500


def _row(name: str, s) -> str:
    return f"{name}  TP {s.tp}  FP {s.fp}  FN {s.fn}  dir {s.direction_errors}"


def report_lines(run: str, report: RunReport) -> list[str]:
    lines = [f"== {run} =="]
    lines += [_row(key, score) for key, score in report.per_opening.items()]
    rates = f"precision {report.precision}  recall {report.recall}"
    lines.append(f"{_row('TOTAL', report.total)}  {rates}")
    if report.missing:
        lines.append(f"missing answers: {', '.join(report.missing)}")
    return lines


def build_video(path: Path, area=FRIDGE_AREA) -> tuple[bytes, int]:
    """The analysis video for a clip that is already cut to the open span: every frame
    FRAME_MS apart, thinned and cropped as the pipeline does. Returns (MP4 bytes, frames)."""
    import io as _io

    from PIL import Image

    from fridgesense import clip_frames
    from fridgesense.door_events import _crop_box, _frame_jpeg, video_frame_indexes
    from fridgesense.fridge_area import analysis_box

    frames = [_frame_jpeg(img) for _, img in clip_frames.sample_frames(path, FRAME_MS)]
    indexes, _ = video_frame_indexes(list(range(len(frames))))
    box = analysis_box(area, None)
    images = [_crop_box(Image.open(_io.BytesIO(frames[i])).convert("RGB"), box) for i in indexes]
    return clip_frames.encode_video(images), len(indexes)


def _tool_input(record) -> dict | None:
    for block in (
        ((record.response or {}).get("output") or {}).get("message", {}).get("content", [])
    ):
        if "toolUse" in block:
            return block["toolUse"].get("input")
    return None


def live(run: str, fixtures: Path, analyzer, inventory: list[str]) -> int:
    labels = load_labels(fixtures / "labels.json")
    folder = fixtures / run
    folder.mkdir(parents=True, exist_ok=True)
    spent = 0.0
    for key in labels:
        clip = eval_clips_dir() / f"{key}.mp4"
        if not clip.exists():
            print(f"{key}: skipped, no clip at {clip}")
            continue
        video, frames = build_video(clip)
        calls = []
        result = analyzer.analyze(
            [],
            inventory,
            {"eval_opening": key},
            on_call=calls.append,
            video=video,
            video_frames=frames,
        )
        spent += result.usd
        answers = [_tool_input(c) for c in calls if c.outcome == "ok"]
        if answers and answers[-1] is not None:
            (folder / f"{key}.json").write_text(json.dumps(answers[-1], indent=2) + "\n")
            print(f"{key}: {frames} frames, ${result.usd:.6f}")
        else:
            print(f"{key}: no valid answer")
    print(f"total cost ${spent:.6f}")
    return 0


def main(argv: list[str] | None = None, fixtures: Path = FIXTURES, analyzer=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", help="comma-separated run names to score")
    group.add_argument("--live", help="analyze the local clips with Nova into this run")
    parser.add_argument("--inventory", default="", help="comma-separated names sent to Nova")
    args = parser.parse_args(argv)
    if args.live:
        if analyzer is None:
            from fridgesense.analysis import NovaAnalyzer
            from fridgesense.handlers.pipeline import bedrock_client

            analyzer = NovaAnalyzer.from_env(bedrock_client())
        names = [n.strip() for n in args.inventory.split(",") if n.strip()]
        return live(args.live, fixtures, analyzer, names)
    runs = [r.strip() for r in args.run.split(",") if r.strip()]
    unknown = [r for r in runs if not (fixtures / r).is_dir()]
    if unknown:
        print(f"no recorded answers for run(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    labels = load_labels(fixtures / "labels.json")
    for run in runs:
        print("\n".join(report_lines(run, score_run(labels, load_run(fixtures / run)))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
