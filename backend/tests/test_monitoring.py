"""fridge-monitoring: whether FridgeSense is active or paused, per account and device."""

from fridgesense import monitoring
from fridgesense.table import FridgeTable

A, B = "ava1.ring.account.A1", "ava1.ring.account.B1"
D1 = "ava1.ring.device.D1"
T0 = 1792332300000  # 2026-10-18T14:05:00Z
T1 = 1792335600000  # 2026-10-18T15:00:00Z


# Never paused
def test_never_paused(aws):
    state = monitoring.load(FridgeTable(), A, D1)
    assert state.to_body() == {"paused": False, "since": None}


# Kept per account and device
def test_kept_per_account_and_device(aws):
    monitoring.set_paused(FridgeTable(), A, D1, True, T0)
    assert monitoring.load(FridgeTable(), A, D1).paused is True
    assert monitoring.load(FridgeTable(), B, D1).paused is False


def test_pause_then_resume_sets_since(aws):
    paused = monitoring.set_paused(FridgeTable(), A, D1, True, T0)
    assert paused.to_body() == {"paused": True, "since": "2026-10-18T14:05:00.000Z"}
    resumed = monitoring.set_paused(FridgeTable(), A, D1, False, T1)
    assert resumed.to_body() == {"paused": False, "since": "2026-10-18T15:00:00.000Z"}
    assert monitoring.load(FridgeTable(), A, D1) == resumed


# Pause twice
def test_pause_twice_keeps_since(aws):
    monitoring.set_paused(FridgeTable(), A, D1, True, T0)
    again = monitoring.set_paused(FridgeTable(), A, D1, True, T1)
    assert again.since == "2026-10-18T14:05:00.000Z"
    assert monitoring.load(FridgeTable(), A, D1).since == "2026-10-18T14:05:00.000Z"
