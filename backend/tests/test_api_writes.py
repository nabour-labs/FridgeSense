"""inventory-api: pending changes and corrections over HTTP, and the read-only viewer."""

import json

import pytest

from fridgesense.door_events import iso_utc
from fridgesense.handlers import api
from fridgesense.handlers.api import encode_id
from fridgesense.inventory import save_task
from fridgesense.store import load_app_config
from fridgesense.table import FridgeTable, account_pk
from tests.api_helpers import ACCOUNT, NOW, api_event, call, configure, link_account, sign_in

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


# Quantity only, as before
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


def raw_call(method, path, raw, token):
    headers = {"content-type": "application/json", "Authorization": f"Bearer {token}"}
    resp = api.handler(api_event(method, path, raw, headers, None), None)
    return resp["statusCode"], json.loads(resp["body"])


def put_stock(key, quantity, name=None, category="other"):
    FridgeTable().put(
        {
            "pk": PK,
            "sk": f"ITEM#{key}",
            "name": name or key,
            "category": category,
            "quantity": quantity,
            "first_seen_at": OPENED,
            "last_changed_at": OPENED,
        }
    )


def items_by_key(body):
    return {i["key"]: i for i in body["items"]}


# Add over HTTP
def test_add_over_http(tokens):
    body = {"name": "Butter", "category": "dairy", "quantity": 1}
    status, resp = call("POST", "/api/items", body, token=tokens["owner"])
    assert status == 200
    assert items_by_key(resp)["butter"] == {
        "key": "butter",
        "name": "Butter",
        "category": "dairy",
        "quantity": 1,
        "last_changed_at": iso_utc(int(NOW * 1000)),
    }
    assert resp["pending_count"] == 0


# Add to an existing item over HTTP
def test_add_to_an_existing_item_over_http(tokens):
    put_stock("eggs", 4)
    body = {"name": "eggs", "category": "dairy", "quantity": 6}
    status, resp = call("POST", "/api/items", body, token=tokens["owner"])
    assert status == 200
    assert items_by_key(resp)["eggs"]["quantity"] == 10


# Bad add body
@pytest.mark.parametrize(
    "raw, error",
    [
        ("not json", "invalid body"),
        ("[]", "invalid body"),
        ("{}", "name must be 1 to 60 characters"),
        ('{"name": "", "category": "dairy", "quantity": 1}', "name must be 1 to 60 characters"),
        ('{"name": "Butter", "category": "sweets", "quantity": 1}', "unknown category"),
        (
            '{"name": "Butter", "category": "dairy", "quantity": 0}',
            "quantity must be a whole number of 1 or more",
        ),
        (
            '{"name": "Butter", "category": "dairy", "quantity": "2"}',
            "quantity must be a whole number of 1 or more",
        ),
    ],
)
def test_bad_add_body(tokens, raw, error):
    assert raw_call("POST", "/api/items", raw, tokens["owner"]) == (400, {"error": error})
    assert FridgeTable().query(ACCOUNT, "ITEM#") == []


def test_quantity_only_keeps_name_and_category(tokens):
    put_stock("eggs", 18, name="Eggs", category="dairy")
    status, resp = call("PUT", "/api/items/eggs", {"quantity": 12}, token=tokens["owner"])
    assert status == 200
    eggs = items_by_key(resp)["eggs"]
    assert (eggs["quantity"], eggs["name"], eggs["category"]) == (12, "Eggs", "dairy")


# Rename over HTTP
def test_rename_over_http(tokens):
    put_stock("bottle", 1)
    body = {"quantity": 1, "name": "Oat Milk", "category": "dairy"}
    status, resp = call("PUT", "/api/items/bottle", body, token=tokens["owner"])
    assert status == 200
    items = items_by_key(resp)
    assert "bottle" not in items
    milk = items["oat milk"]
    assert (milk["name"], milk["category"], milk["quantity"]) == ("Oat Milk", "dairy", 1)


# Key with spaces
def test_key_with_spaces(tokens):
    put_stock("oat milk", 1, name="Oat Milk", category="dairy")
    body = {"quantity": 2, "category": "beverage"}
    status, resp = call("PUT", "/api/items/oat%20milk", body, token=tokens["owner"])
    assert status == 200
    milk = items_by_key(resp)["oat milk"]
    assert (milk["quantity"], milk["category"]) == (2, "beverage")


# Rename clash over HTTP
def test_rename_clash_over_http(tokens):
    put_stock("bottle", 1)
    put_stock("oat milk", 2, name="Oat Milk", category="dairy")
    body = {"quantity": 1, "name": "oat milk"}
    assert call("PUT", "/api/items/bottle", body, token=tokens["owner"]) == (
        409,
        {"error": "item exists"},
    )
    assert (quantity_of("bottle"), quantity_of("oat milk")) == (1, 2)


# Rename unknown item over HTTP
def test_rename_unknown_item_over_http(tokens):
    body = {"quantity": 1, "name": "Greek Yogurt"}
    assert call("PUT", "/api/items/yogurt", body, token=tokens["owner"]) == (
        404,
        {"error": "not found"},
    )
    assert FridgeTable().query(ACCOUNT, "ITEM#") == []


# Bad edit fields
@pytest.mark.parametrize(
    "body, error",
    [
        ({"quantity": 6, "name": "   "}, "name must be 1 to 60 characters"),
        ({"quantity": 6, "name": 7}, "name must be 1 to 60 characters"),
        ({"quantity": 6, "category": "sweets"}, "unknown category"),
    ],
)
def test_bad_edit_fields(tokens, body, error):
    put_stock("eggs", 6, category="dairy")
    assert call("PUT", "/api/items/eggs", body, token=tokens["owner"]) == (400, {"error": error})
    eggs = FridgeTable().get(PK, "ITEM#eggs")
    assert (eggs["quantity"], eggs["category"], eggs["name"]) == (6, "dairy", "eggs")


# Delete over HTTP
def test_delete_over_http(tokens):
    put_stock("mystery jar", 1)
    put_stock("eggs", 6)
    status, resp = call("DELETE", "/api/items/mystery%20jar", token=tokens["owner"])
    assert status == 200
    assert list(items_by_key(resp)) == ["eggs"]


# Delete unknown item over HTTP
def test_delete_unknown_item_over_http(tokens):
    assert call("DELETE", "/api/items/yogurt", token=tokens["owner"]) == (
        404,
        {"error": "not found"},
    )


# Delete without a token
def test_delete_without_a_token(tokens):
    put_stock("eggs", 6)
    assert call("DELETE", "/api/items/eggs") == (401, {"error": "sign in"})
    assert quantity_of("eggs") == 6


# Viewer cannot add or delete items
def test_viewer_cannot_add_or_delete_items(tokens):
    put_stock("eggs", 6)
    viewer = tokens["viewer"]
    body = {"name": "Butter", "category": "dairy", "quantity": 1}
    assert call("POST", "/api/items", body, token=viewer) == (403, {"error": "read-only"})
    assert call("DELETE", "/api/items/eggs", token=viewer) == (403, {"error": "read-only"})
    assert quantity_of("butter") is None
    assert quantity_of("eggs") == 6
