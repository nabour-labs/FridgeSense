"""Door check accuracy on local fridge recordings. Local only: no Ring, AWS or Bedrock calls.

    uv sync --group clips
    uv run python scripts/door_clip_report.py --dump

`--dump` writes every sampled still of every clip in the clips folder (FRIDGESENSE_CLIPS_DIR,
default tmp/) to `<dump dir>/<clip>/<offset ms>.jpg`, with a `values.csv` of zone values and
verdicts, to help label opened and closed times. Stills are written under tmp/ only.
"""

import argparse
import csv
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/, for tests.clips

from tests.clips.harness import (  # noqa: E402
    EPOCH_MS,
    LABELS,
    REPO,
    AvSource,
    FrameSource,
    clips_dir,
    evaluate_clip,
    load_labels,
)

DEFAULT_DUMP_DIR = "tmp/clip-stills"


def dump_dir_of(text: str, repo: Path) -> Path:
    """The dump folder (relative paths from the repo root); it must lie inside tmp/."""
    path = Path(text)
    path = (path if path.is_absolute() else repo / path).resolve()
    if not path.is_relative_to((repo / "tmp").resolve()):
        raise ValueError(f"--dump-dir {text}: stills may only be written under tmp/")
    return path


def dump_clip(result, folder: Path) -> int:
    """Write the clip's sampled stills and values.csv; returns how many stills were written."""
    trace = result.trace
    folder.mkdir(parents=True, exist_ok=True)
    zones = len(trace.check.rules)
    written = 0
    with (folder / "values.csv").open("w", newline="") as f:
        out = csv.writer(f)
        out.writerow(["offset_ms", *(f"zone_{z}" for z in range(1, zones + 1)), "verdict"])
        for still in trace.stills:
            offset_ms = still.at_ms - EPOCH_MS
            values = trace.values.get(still.n)
            if still.data is None or values is None:
                out.writerow([offset_ms, *([""] * zones), "missing"])
                continue
            (folder / f"{offset_ms}.jpg").write_bytes(still.data)
            written += 1
            verdict = "open" if trace.check.result_of(values).is_open else "closed"
            out.writerow([offset_ms, *(f"{v.value:.4f}" for v in values), verdict])
    return written


def main(
    argv: list[str] | None = None,
    repo: Path = REPO,
    open_clip: Callable[[Path], FrameSource] = AvSource,
    labels: Path = LABELS,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dump", action="store_true", help="write sampled stills for labelling")
    parser.add_argument("--dump-dir", default=DEFAULT_DUMP_DIR, help="under tmp/ only")
    args = parser.parse_args(argv)
    if not args.dump:
        print("only --dump is available so far", file=sys.stderr)
        return 2
    try:
        target = dump_dir_of(args.dump_dir, repo)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2

    folder = clips_dir()
    labelled = load_labels(labels) if Path(labels).exists() else {}
    clips = sorted(p for p in folder.glob("*.mp4")) if folder.is_dir() else []
    if not clips:
        print(f"no clips found in {folder}")
        return 0
    for path in clips:
        result = evaluate_clip(path.name, open_clip(path), labelled.get(path.name, []))
        written = dump_clip(result, target / path.stem)
        print(f"{path.name}: {written} stills -> {target / path.stem}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
