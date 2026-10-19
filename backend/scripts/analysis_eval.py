"""Item analysis accuracy on labelled real openings. Offline unless --live is given.

    uv run python scripts/analysis_eval.py --run baseline
    uv run python scripts/analysis_eval.py --run baseline,video-v1

Each run is a folder of recorded `record_fridge_changes` tool inputs under
tests/fixtures/analysis_eval/<run>/<window start ms>.json, scored against labels.json:
true and false positives and negatives count items (not quantities) with their direction,
and `dir` counts names that matched a label with the opposite direction.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/, for tests.analysis_eval

from tests.analysis_eval.harness import FIXTURES, RunReport, load_labels, load_run, score_run  # noqa: E402


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


def main(argv: list[str] | None = None, fixtures: Path = FIXTURES) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True, help="comma-separated run names to score")
    args = parser.parse_args(argv)
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
