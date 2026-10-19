"""Item analysis on real openings: labels, recorded answers, and a direction-aware score.

Shared by the eval tests and `scripts/analysis_eval.py`, so both score the same way.
Fixtures hold only item names and recorded tool inputs; clips stay in the local clips folder.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures" / "analysis_eval"
REPO = Path(__file__).resolve().parents[3]


def eval_clips_dir() -> Path:
    """Labelled openings' clips: <clips folder>/analysis-eval/<window start ms>.mp4."""
    import os

    return Path(os.environ.get("FRIDGESENSE_CLIPS_DIR") or REPO / "tmp") / "analysis-eval"


LABELS = FIXTURES / "labels.json"
DIRECTIONS = ("added", "removed")


class LabelError(ValueError):
    """The labels file is malformed; the message names the opening and the problem."""


@dataclass(frozen=True)
class LabelItem:
    item: str
    quantity: int
    also: tuple[str, ...] = ()


@dataclass(frozen=True)
class OpeningLabel:
    added: list[LabelItem]
    removed: list[LabelItem]
    note: str = ""
    skip: str = ""  # why nobody could judge this opening: left out of the totals


def _item(opening: str, raw) -> LabelItem:
    if not isinstance(raw, dict):
        raise LabelError(f"{opening}: each item must be an object")
    name = raw.get("item")
    if not isinstance(name, str) or not name.strip():
        raise LabelError(f"{opening}: item must be a non-empty name")
    quantity = raw.get("quantity")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise LabelError(f"{opening}: {name}: quantity must be a whole number of 1 or more")
    also = raw.get("also", [])
    if not isinstance(also, list) or not all(isinstance(a, str) and a.strip() for a in also):
        raise LabelError(f"{opening}: {name}: also must be a list of names")
    return LabelItem(name.strip(), quantity, tuple(a.strip() for a in also))


def _opening(opening: str, entry) -> OpeningLabel:
    if not isinstance(entry, dict):
        raise LabelError(f"{opening}: must be an object")
    skip = entry.get("skip")
    if skip is not None:
        if not isinstance(skip, str) or not skip.strip():
            raise LabelError(f"{opening}: skip must be the reason, as text")
        return OpeningLabel(added=[], removed=[], skip=skip.strip())
    lists = {}
    for direction in DIRECTIONS:
        raw = entry.get(direction)
        if not isinstance(raw, list):
            raise LabelError(f"{opening}: {direction} must be a list")
        lists[direction] = [_item(opening, r) for r in raw]
    note = entry.get("note", "")
    return OpeningLabel(**lists, note=note if isinstance(note, str) else "")


def load_labels(path: Path = LABELS) -> dict[str, OpeningLabel]:
    """Openings by window start ms. Raises LabelError for a malformed file."""
    openings = json.loads(Path(path).read_text()).get("openings")
    if not isinstance(openings, dict):
        raise LabelError("labels.json: openings must be an object")
    return {key: _opening(key, entry) for key, entry in openings.items()}


def load_run(directory: Path) -> dict[str, dict]:
    """A run's recorded tool inputs, by window start ms."""
    return {p.stem: json.loads(p.read_text()) for p in sorted(Path(directory).glob("*.json"))}


def answer_changes(answer: dict) -> list[tuple[str, str]]:
    """(direction, item) pairs the pipeline would apply for a recorded answer: the evidence
    shape goes through the analysis's own direction rules; the old shape is read as is."""
    if "items" in answer:
        from fridgesense.analysis import changes_from

        changes = changes_from(answer)
        return [("added", c.item) for c in changes.added] + [
            ("removed", c.item) for c in changes.removed
        ]
    return [
        (direction, str(c.get("item", "")))
        for direction in DIRECTIONS
        for c in answer.get(direction, [])
        if isinstance(c, dict) and str(c.get("item", "")).strip()
    ]


@dataclass(frozen=True)
class Score:
    tp: int
    fp: int
    fn: int
    direction_errors: int

    def __add__(self, other: "Score") -> "Score":
        return Score(*(a + b for a, b in zip(self.astuple(), other.astuple(), strict=True)))

    def astuple(self) -> tuple[int, int, int, int]:
        return (self.tp, self.fp, self.fn, self.direction_errors)


def _key(name: str) -> str:
    from fridgesense.inventory import normalize_name

    return normalize_name(name)[0]


def score_opening(label: OpeningLabel, answer: dict) -> Score:
    """Items, not quantities: each labelled item matches at most one predicted change."""
    unmatched = {
        d: [{_key(i.item), *(_key(a) for a in i.also)} for i in getattr(label, d)]
        for d in DIRECTIONS
    }
    tp = fp = flipped = 0
    for direction, item in answer_changes(answer):
        key = _key(item)
        hit = next((names for names in unmatched[direction] if key in names), None)
        if hit is not None:
            unmatched[direction].remove(hit)
            tp += 1
            continue
        fp += 1
        other = "removed" if direction == "added" else "added"
        if any(key in names for names in unmatched[other]):
            flipped += 1
    fn = sum(len(v) for v in unmatched.values())
    return Score(tp, fp, fn, flipped)


@dataclass
class RunReport:
    per_opening: dict[str, Score]
    missing: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)

    @property
    def total(self) -> Score:
        return sum(self.per_opening.values(), Score(0, 0, 0, 0))

    @property
    def precision(self) -> float | None:
        t = self.total
        return round(t.tp / (t.tp + t.fp), 3) if t.tp + t.fp else None

    @property
    def recall(self) -> float | None:
        t = self.total
        return round(t.tp / (t.tp + t.fn), 3) if t.tp + t.fn else None


def score_run(labels: dict[str, OpeningLabel], answers: dict[str, dict]) -> RunReport:
    """Every labelled opening that is not skipped; one without an answer scores as empty."""
    judged = {k: lbl for k, lbl in labels.items() if not lbl.skip}
    empty = {"added": [], "removed": []}
    return RunReport(
        per_opening={k: score_opening(lbl, answers.get(k, empty)) for k, lbl in judged.items()},
        missing=[k for k in judged if k not in answers],
        skipped={k: lbl.skip for k, lbl in labels.items() if lbl.skip},
    )
