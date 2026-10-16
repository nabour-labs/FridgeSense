"""Debug traces: what the door check and the Nova analysis saw, decided, spent and took.

Files go to S3 under the event's `debug/` folder (expired with the bucket after 7 days);
one TRACE# summary item per motion makes them listable. Writing a trace never raises.
"""

import io
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from PIL import Image

from fridgesense import door_calibration
from fridgesense.door_events import (
    BASELINE_SIZE,
    DoorCheck,
    Downloaded,
    StillResult,
    ZoneValue,
    iso_utc,
    stills_prefix,
)
from fridgesense.logs import log_event
from fridgesense.table import FridgeTable, account_pk

TRACE_DAYS = 7
WRITE_WORKERS = 8


def debug_prefix(account_id: str, device_id: str, start_ms: int) -> str:
    return f"{stills_prefix(account_id, device_id, start_ms)}debug/"


def trace_sk(device_id: str, start_ms: int) -> str:
    return f"TRACE#{iso_utc(start_ms)}#{device_id}"


@dataclass
class DoorTrace:
    """One motion's door check: every requested still, its zone values, and the outcome."""

    stills: list[Downloaded]
    values: dict[int, list[ZoneValue]]  # by still number, for downloaded stills
    check: DoorCheck
    outcome: str
    open_span: list[int] = field(default_factory=list)  # still numbers
    picked: list[int] = field(default_factory=list)  # still numbers
    stored_keys: list[str] = field(default_factory=list)
    door_sk: str | None = None
    opened_at: str | None = None
    closed_at: str | None = None

    def results(self) -> dict[int, StillResult]:
        return {n: self.check.result_of(v) for n, v in self.values.items()}


def _box_json(box) -> dict:
    return dict(zip(("x", "y", "width", "height"), box, strict=True))


BASELINE_SCALE = 8


def baseline_png(baseline: bytes) -> bytes:
    """The 32x32 RGB baseline as a PNG, scaled up so it can be seen."""
    img = Image.frombytes("RGB", BASELINE_SIZE, baseline)
    w, h = BASELINE_SIZE
    img = img.resize((w * BASELINE_SCALE, h * BASELINE_SCALE), Image.Resampling.NEAREST)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _zone_json(v: ZoneValue) -> dict:
    return {"zone": v.zone, "value": round(v.value, 4), "threshold": v.threshold, "open": v.open}


def writer_from_env(s3, table: FridgeTable, bucket: str) -> "TraceWriter | NullTraceWriter":
    """Tracing is on unless DEBUG_TRACES is `false`."""
    if (os.environ.get("DEBUG_TRACES") or "").strip().lower() == "false":
        return NullTraceWriter()
    return TraceWriter(s3, table, bucket)


class NullTraceWriter:
    """Tracing off: writes nothing."""

    def door(self, state: dict, trace: DoorTrace) -> None:
        pass


class TraceWriter:
    def __init__(self, s3, table: FridgeTable, bucket: str):
        self.s3 = s3
        self.table = table
        self.bucket = bucket

    def _put(self, key: str, body: bytes, content_type: str) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)

    def _failed(self, state: dict, part: str, e: Exception) -> None:
        log_event(
            "debug_trace_failed",
            logging.WARNING,
            account_id=state.get("account_id"),
            device_id=state.get("device_id"),
            part=part,
            error=type(e).__name__,
        )

    def door(self, state: dict, trace: DoorTrace) -> None:
        """Raw stills, then door.json, then the summary item. Never raises."""
        try:
            self._door_files(state, trace)
        except Exception as e:  # a trace must never break the pipeline
            self._failed(state, "door", e)
        try:
            self._door_summary(state, trace)
        except Exception as e:
            self._failed(state, "summary", e)

    def _door_files(self, state: dict, trace: DoorTrace) -> None:
        window = state["window"]
        prefix = debug_prefix(state["account_id"], state["device_id"], window["start_ms"])
        results = trace.results()
        raw = [s for s in trace.stills if s.data is not None]
        with ThreadPoolExecutor(max_workers=WRITE_WORKERS) as pool:
            list(pool.map(lambda s: self._put(f"{prefix}raw-{s.n}.jpg", s.data, "image/jpeg"), raw))
        stills = []
        for s in trace.stills:
            result = results.get(s.n)
            stills.append(
                {
                    "n": s.n,
                    "at_ms": s.at_ms,
                    "key": f"{prefix}raw-{s.n}.jpg" if s.data is not None else None,
                    "missing_status": s.status if s.data is None else None,
                    "zones": [_zone_json(v) for v in trace.values.get(s.n, [])],
                    "best_zone": result.zone if result else None,
                    "open": result.is_open if result else None,
                }
            )
        doc = {
            "window": {
                "start_ms": window["start_ms"],
                "end_ms": window["end_ms"],
                "ring_event_id": window.get("ring_event_id"),
            },
            "outcome": trace.outcome,
            "door_sk": trace.door_sk,
            "opened_at": trace.opened_at,
            "closed_at": trace.closed_at,
            "rule": self._rule(state, trace.check, prefix),
            "stills": stills,
            "open_span": trace.open_span,
            "picked": trace.picked,
            "stored_keys": trace.stored_keys,
        }
        self._put(f"{prefix}door.json", json.dumps(doc).encode(), "application/json")

    def _rule(self, state: dict, check: DoorCheck, prefix: str) -> dict:
        setup = check.source == "setup"
        zones = []
        for n, rule in enumerate(check.rules, 1):
            baseline_key = None
            if setup and rule.baseline is not None:
                baseline_key = f"{prefix}baseline-{n}.png"
                self._put(baseline_key, baseline_png(rule.baseline), "image/png")
            zones.append(
                {
                    "zone": n,
                    "box": _box_json(rule.box),
                    "feature": rule.feature,
                    "direction": rule.direction,
                    "threshold": rule.threshold,
                    "margin": rule.margin if setup else None,
                    "baseline_key": baseline_key,
                }
            )
        references = []
        if setup:
            account_id, device_id = state["account_id"], state["device_id"]
            for ref in door_calibration.list_references(self.table, account_id, device_id):
                ref_id = ref.sk.removeprefix(door_calibration.ref_prefix(device_id))
                key = f"{prefix}door-ref-{ref_id}.jpg"
                self._put(key, ref.image, "image/jpeg")
                references.append(
                    {
                        "id": ref_id,
                        "status": ref.status,
                        "box": _box_json(ref.box),
                        "created_at": ref.created_at,
                        "key": key,
                    }
                )
        return {
            "source": check.source,
            "ran_at": check.ran_at if setup else None,
            "zones": zones,
            "references": references,
        }

    def _door_summary(self, state: dict, trace: DoorTrace) -> None:
        window = state["window"]
        results = list(trace.results().values())
        best = None
        if results:
            b = trace.check.best(results)
            best = {
                "value": round(b.value, 4),
                "zone": b.zone,
                "feature": b.feature,
                "threshold": b.threshold,
            }
        self.table.put(
            {
                "pk": account_pk(state["account_id"]),
                "sk": trace_sk(state["device_id"], window["start_ms"]),
                "device_id": state["device_id"],
                "ring_event_id": window.get("ring_event_id"),
                "start_ms": window["start_ms"],
                "end_ms": window["end_ms"],
                "outcome": trace.outcome,
                "zones_source": trace.check.source,
                "best": best,
                "stills_requested": len(trace.stills),
                "stills_downloaded": sum(1 for d in trace.stills if d.data is not None),
                "door_sk": trace.door_sk,
                "nova_calls": [],
                "ttl": window["start_ms"] // 1000 + TRACE_DAYS * 86400,
            }
        )
