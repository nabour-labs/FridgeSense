"""Whether FridgeSense is active or paused for a camera, so the owner can stop door openings
being recorded and analyzed while cleaning, servicing or renovating. One item per device; a
missing item means active."""

from dataclasses import dataclass

from fridgesense.door_events import iso_utc
from fridgesense.table import FridgeTable, account_pk


def monitoring_sk(device_id: str) -> str:
    return f"MONITORING#{device_id}"


@dataclass(frozen=True)
class Monitoring:
    paused: bool
    since: str | None  # when the current state began; None if never changed

    def to_body(self) -> dict:
        return {"paused": self.paused, "since": self.since}


ACTIVE = Monitoring(paused=False, since=None)


def load(table: FridgeTable, account_id: str, device_id: str) -> Monitoring:
    item = table.get(account_pk(account_id), monitoring_sk(device_id))
    if item is None:
        return ACTIVE
    return Monitoring(paused=bool(item["paused"]), since=item["since"])


def set_paused(
    table: FridgeTable, account_id: str, device_id: str, paused: bool, now_ms: int
) -> Monitoring:
    """Store the state; sending the current state again keeps its `since`."""
    current = load(table, account_id, device_id)
    if current.paused == paused and current.since is not None:
        return current
    state = Monitoring(paused=paused, since=iso_utc(now_ms))
    table.put(
        {
            "pk": account_pk(account_id),
            "sk": monitoring_sk(device_id),
            "paused": state.paused,
            "since": state.since,
        }
    )
    return state
