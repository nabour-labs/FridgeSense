"""Door check accuracy on local fridge recordings. Local only: no Ring, AWS or Bedrock calls.

    uv sync --group clips
    uv run python scripts/door_clip_report.py                     # accuracy over labelled clips
    uv run python scripts/door_clip_report.py --threshold 0.005,0.01,0.02 --interval 500,1000
    uv run python scripts/door_clip_report.py --dump

The report runs every labelled clip in the clips folder (FRIDGESENSE_CLIPS_DIR, default tmp/)
through the unchanged fetch-stills task and scores it against tests/fixtures/clips/door_labels.json.
Clip frames stand in for Ring stills; compression and resolution may differ.

`--dump` writes every sampled still of every clip in the clips folder (FRIDGESENSE_CLIPS_DIR,
default tmp/) to `<dump dir>/<clip>/<offset ms>.jpg`, with a `values.csv` of zone values and
verdicts, to help label opened and closed times. Stills are written under tmp/ only.
"""

import argparse
import csv
import os
import sys
from collections.abc import Callable
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/, for tests.clips

from fridgesense.door_events import DoorCheck  # noqa: E402
from tests.clips.harness import (  # noqa: E402
    EPOCH_MS,
    LABELS,
    REPO,
    AvSource,
    ClipResult,
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


def _span(span) -> str:
    return "-" if span is None else f"{span[0]:.1f}-{span[1]:.1f} s"


def _err(error: float | None) -> str:
    return "" if error is None else f"{error:+.1f} s"


def row(result: ClipResult) -> str:
    merged = f"  (merged {result.merged})" if result.merged else ""
    return (
        f"{result.clip:34} {result.verdict:3} labelled {_span(result.expected):12} "
        f"detected {_span(result.detected):12} open {_err(result.open_error_s):7} "
        f"close {_err(result.close_error_s):7} best {result.best_value:.3f}{merged}"
    )


def counts(results: list[ClipResult]) -> str:
    n = {v: sum(r.verdict == v for r in results) for v in ("TP", "FP", "FN", "TN")}
    return "  ".join(f"{v} {c}" for v, c in n.items())


def _mean_max(errors: list[float]) -> tuple[float, float] | None:
    found = [abs(e) for e in errors if e is not None]
    return (sum(found) / len(found), max(found)) if found else None


def summary_lines(results: list[ClipResult]) -> list[str]:
    """The confusion matrix, then mean and max absolute timing error over true openings."""
    lines = [counts(results)]
    for what, attr in (("open", "open_error_s"), ("close", "close_error_s")):
        found = _mean_max([getattr(r, attr) for r in results])
        label = f"{what} error".ljust(12)
        if found is None:
            lines.append(f"{label} n/a")
        else:
            lines.append(f"{label} mean {found[0]:.2f} s  max {found[1]:.2f} s")
    return lines


def _mean_text(results: list[ClipResult], attr: str) -> str:
    found = _mean_max([getattr(r, attr) for r in results])
    return "n/a" if found is None else f"{found[0]:.2f} s"


def parse_list(text: str | None, option: str, kind, minimum: float, inclusive: bool) -> list:
    """Comma-separated values of `kind`, each above (or at) `minimum`; errors name the option."""
    if text is None:
        return [None]
    try:
        values = [kind(v) for v in text.split(",")]
    except ValueError:
        raise ValueError(f"{option} {text}: needs comma-separated numbers") from None
    if any(v < minimum or (v == minimum and not inclusive) for v in values):
        sign = ">=" if inclusive else ">"
        raise ValueError(f"{option} {text}: every value must be {sign} {minimum}")
    return values


def main(
    argv: list[str] | None = None,
    repo: Path = REPO,
    open_clip: Callable[[Path], FrameSource] = AvSource,
    labels: Path = LABELS,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dump", action="store_true", help="write sampled stills for labelling")
    parser.add_argument("--dump-dir", default=DEFAULT_DUMP_DIR, help="under tmp/ only")
    parser.add_argument("--threshold", help="comma-separated door thresholds to sweep")
    parser.add_argument("--interval", help="comma-separated still intervals (ms) to sweep")
    args = parser.parse_args(argv)
    try:
        thresholds = parse_list(args.threshold, "--threshold", float, 0.0, inclusive=True)
        intervals = parse_list(args.interval, "--interval", int, 0, inclusive=False)
        target = dump_dir_of(args.dump_dir, repo) if args.dump else None
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2

    folder = clips_dir()
    labelled = load_labels(labels) if Path(labels).exists() else {}
    clips = sorted(p for p in folder.glob("*.mp4")) if folder.is_dir() else []
    if args.dump:
        if not clips:
            print(f"no clips found in {folder}")
            return 0
        for path in clips:
            result = evaluate_clip(path.name, open_clip(path), labelled.get(path.name, []))
            written = dump_clip(result, target / path.stem)
            print(f"{path.name}: {written} stills -> {target / path.stem}")
        return 0

    scored = [p for p in clips if p.name in labelled]
    unlabelled = [p.name for p in clips if p.name not in labelled]
    if not scored:
        print(f"no labelled clips found in {folder}")
        return 0
    print("Clip frames stand in for Ring stills; compression and resolution may differ.")
    sources = {p.name: open_clip(p) for p in scored}  # each clip decoded once, cached
    sweep = len(thresholds) * len(intervals) > 1
    base = DoorCheck.from_config(os.environ.get("DOOR_ZONES"), os.environ.get("DOOR_THRESHOLD"))
    for threshold, interval in product(thresholds, intervals):
        check = base if threshold is None else DoorCheck(zones=base.zones, threshold=threshold)
        results = [
            evaluate_clip(name, source, labelled[name], check, interval)
            for name, source in sources.items()
        ]
        if sweep:
            print(
                f"sweep threshold {check.threshold:g}  interval {interval} ms  {counts(results)}"
                f"  open {_mean_text(results, 'open_error_s')}"
                f"  close {_mean_text(results, 'close_error_s')}"
            )
            continue
        for result in results:
            print(row(result))
        print()
        for line in summary_lines(results):
            print(line)
    if unlabelled:
        print("\nunlabelled (not scored):")
        for name in unlabelled:
            print(f"  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
