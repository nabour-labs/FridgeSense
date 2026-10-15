"""inventory-api: pending changes and corrections over HTTP, and the read-only viewer."""

import pytest

from fridgesense.handlers import api
from fridgesense.handlers.api import encode_id
from fridgesense.inventory import save_task
from fridgesense.store import load_app_config
from fridgesense.table import FridgeTable, account_pk
from tests.api_helpers import ACCOUNT, NOW, call, configure, link_account, sign_in

PK = account_pk(ACCOUNT)
OPENED = "2026-08-14T13:53:16.000Z"
DOOR_SK = f"DOOR#{OPENED}#ava1.ring.device.D1"


@pytest.fixture
def tokens(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    link_account()
    configure(demo_passcode="look-only")
    load_app_config(refresh=True)
    return {"owner": sign_in(), "viewer": sign_in("look-only")}


@pytest.fixture
def pending(tokens):
    table = FridgeTable()
    table.put(
        {
            "pk": PK,
            "sk": "ITEM#chocolate bar",
            "name": "chocolate bar",
            "category": "snack",
            "quantity": 2,
            "first_seen_at": OPENED,
            "last_changed_at": OPENED,
        }
    )
    table.put(
        {"pk": PK, "sk": DOOR_SK, "status": "analyzing", "opened_at": OPENED, "closed_at": OPENED}
    )
    save_task(
        table,
        {
            "account_id": ACCOUNT,
            "door_sk": DOOR_SK,
            "analysis": {
                "added": [],
                "removed": [
                    {
                        "item": "chocolate bar",
                        "category": "snack",
                        "quantity": 1,
                        "confidence": 0.62,
                    }
                ],
            },
        },
    )
    [p] = table.query(ACCOUNT, "PENDING#")
    return p


def quantity_of(key):
    item = FridgeTable().get(PK, f"ITEM#{key}")
    return None if item is None else item["quantity"]


def test_list_pending(tokens, pending):
    status, body = call("GET", "/api/pending", token=tokens["owner"])
    assert status == 200
    assert body == {
        "pending": [
            {
                "id": encode_id(pending["sk"]),
                "door_event_id": encode_id(DOOR_SK),
                "item": "chocolate bar",
                "category": "snack",
                "direction": "removed",
                "quantity": 1,
                "confidence": 0.62,
                "opened_at": OPENED,
            }
        ]
    }


# Confirm over HTTP
def test_confirm_over_http(tokens, pending):
    status, body = call(
        "POST", f"/api/pending/{encode_id(pending['sk'])}/confirm", token=tokens["owner"]
    )
    assert status == 200
    assert [(i["key"], i["quantity"]) for i in body["items"]] == [("chocolate bar", 1)]
    assert body["pending_count"] == 0
    assert call("GET", "/api/pending", token=tokens["owner"])[1] == {"pending": []}


def test_confirm_with_correction_over_http(tokens, pending):
    status, _ = call(
        "POST",
        f"/api/pending/{encode_id(pending['sk'])}/confirm",
        {"item": "Chocolate Bar", "quantity": 2},
        token=tokens["owner"],
    )
    assert status == 200
    assert quantity_of("chocolate bar") == 0


def test_reject_over_http(tokens, pending):
    status, body = call(
        "POST", f"/api/pending/{encode_id(pending['sk'])}/reject", token=tokens["owner"]
    )
    assert status == 200 and body["pending_count"] == 0
    assert quantity_of("chocolate bar") == 2


# Pending change not found
@pytest.mark.parametrize("action", ["confirm", "reject"])
@pytest.mark.parametrize("pending_id", [encode_id("PENDING#x#9"), encode_id("ITEM#milk"), "@@"])
def test_pending_change_not_found(tokens, action, pending_id):
    status, _ = call("POST", f"/api/pending/{pending_id}/{action}", token=tokens["owner"])
    assert status == 404


def test_set_quantity_over_http(tokens):
    status, body = call("PUT", "/api/items/whole%20milk", {"quantity": 2}, token=tokens["owner"])
    assert status == 200
    assert [(i["key"], i["quantity"]) for i in body["items"]] == [("whole milk", 2)]


# Invalid quantity
@pytest.mark.parametrize(
    "body", [{"quantity": -1}, {"quantity": "two"}, {"quantity": 1.5}, {"quantity": True}, {}]
)
def test_invalid_quantity_set(tokens, body):
    assert call("PUT", "/api/items/milk", body, token=tokens["owner"])[0] == 400
    assert quantity_of("milk") is None


def test_invalid_quantity_confirm(tokens, pending):
    status, _ = call(
        "POST",
        f"/api/pending/{encode_id(pending['sk'])}/confirm",
        {"quantity": 0},
        token=tokens["owner"],
    )
    assert status == 400
    assert len(FridgeTable().query(ACCOUNT, "PENDING#")) == 1


# Viewer write refused
def test_viewer_write_refused(tokens, pending):
    viewer = tokens["viewer"]
    for method, path, body in [
        ("POST", f"/api/pending/{encode_id(pending['sk'])}/confirm", None),
        ("POST", f"/api/pending/{encode_id(pending['sk'])}/reject", None),
        ("PUT", "/api/items/milk", {"quantity": 2}),
    ]:
        assert call(method, path, body, token=viewer) == (403, {"error": "read-only"})
    assert len(FridgeTable().query(ACCOUNT, "PENDING#")) == 1
    assert quantity_of("chocolate bar") == 2 and quantity_of("milk") is None


# Viewer reads
def test_viewer_reads(tokens, pending):
    for path in ["/api/inventory", "/api/events", "/api/pending"]:
        owner = call("GET", path, token=tokens["owner"])
        viewer = call("GET", path, token=tokens["viewer"])
        assert viewer[0] == 200 and viewer == owner
