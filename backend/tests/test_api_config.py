"""analysis-config: the config routes on the app API."""

import base64
import json

import pytest

from fridgesense.handlers import api
from fridgesense.store import load_app_config
from tests.api_helpers import NOW, call, configure, link_account, sign_in
from tests.conftest import api_event

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 60_000
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
INSTRUCTIONS_ERROR = {"error": "instructions must be text of at most 1000 characters"}


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


@pytest.fixture
def tokens(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    link_account()
    configure(demo_passcode="look-only")
    load_app_config(refresh=True)
    return {"owner": sign_in(), "viewer": sign_in("look-only")}


@pytest.fixture
def owner(tokens):
    return tokens["owner"]


def add(token, annotation, image=JPEG):
    return call(
        "POST", "/api/config/references", {"annotation": annotation, "image": b64(image)}, token
    )


# Nothing configured
def test_nothing_configured(owner):
    assert call("GET", "/api/config", token=owner) == (200, {"instructions": "", "references": []})


# Config with references (viewer read)
def test_config_with_references(tokens, monkeypatch):
    add(tokens["owner"], "milk bag")
    monkeypatch.setattr(api, "now", lambda: NOW + 1)
    add(tokens["owner"], "soda can")
    call(
        "PUT",
        "/api/config/instructions",
        {"instructions": "Count yogurt cups individually."},
        tokens["owner"],
    )
    status, body = call("GET", "/api/config", token=tokens["viewer"])
    assert status == 200
    assert body["instructions"] == "Count yogurt cups individually."
    assert [r["annotation"] for r in body["references"]] == ["milk bag", "soda can"]
    for ref in body["references"]:
        assert ref["id"] and ref["image"] == b64(JPEG)
        assert ref["created_at"].startswith("2026-") and ref["created_at"].endswith("Z")


# Save instructions
def test_save_instructions(owner):
    status, body = call(
        "PUT",
        "/api/config/instructions",
        {"instructions": "  Count yogurt cups individually.  "},
        owner,
    )
    assert status == 200
    assert body == {"instructions": "Count yogurt cups individually.", "references": []}


# Clear instructions
def test_clear_instructions(owner):
    call("PUT", "/api/config/instructions", {"instructions": "x"}, owner)
    status, body = call("PUT", "/api/config/instructions", {"instructions": ""}, owner)
    assert status == 200 and body["instructions"] == ""


# Instructions too long or wrong type
@pytest.mark.parametrize("body", [{"instructions": "x" * 1001}, {"instructions": 5}, {}])
def test_instructions_too_long_or_wrong_type(owner, body):
    call("PUT", "/api/config/instructions", {"instructions": "keep me"}, owner)
    assert call("PUT", "/api/config/instructions", body, owner) == (400, INSTRUCTIONS_ERROR)
    assert call("GET", "/api/config", token=owner)[1]["instructions"] == "keep me"


def test_instructions_not_json(owner):
    headers = {"content-type": "application/json", "Authorization": f"Bearer {owner}"}
    resp = api.handler(api_event("PUT", "/api/config/instructions", "{nope", headers, None), None)
    assert resp["statusCode"] == 400 and json.loads(resp["body"]) == INSTRUCTIONS_ERROR


# Add a reference
def test_add_reference(owner):
    status, body = add(owner, "milk bag (2 L, white with blue print)")
    assert status == 200
    last = body["references"][-1]
    assert last["annotation"] == "milk bag (2 L, white with blue print)"
    assert last["image"] == b64(JPEG)


# Bad annotation
@pytest.mark.parametrize("annotation", [None, "   ", "x" * 301])
def test_bad_annotation(owner, annotation):
    body = (
        {"image": b64(JPEG)}
        if annotation is None
        else {"annotation": annotation, "image": b64(JPEG)}
    )
    assert call("POST", "/api/config/references", body, owner) == (
        400,
        {"error": "annotation must be 1 to 300 characters"},
    )
    assert call("GET", "/api/config", token=owner)[1]["references"] == []


# Not a JPEG or too large
@pytest.mark.parametrize(
    "image", ["not base64!!", b64(PNG), b64(b"\xff\xd8\xff" + b"\x00" * 199_998)]
)
def test_not_a_jpeg_or_too_large(owner, image):
    body = {"annotation": "milk", "image": image}
    assert call("POST", "/api/config/references", body, owner) == (
        400,
        {"error": "image must be a JPEG of at most 200 KB"},
    )
    assert call("GET", "/api/config", token=owner)[1]["references"] == []


# Seventh reference
def test_seventh_reference(owner):
    for n in range(6):
        assert add(owner, f"item {n}")[0] == 200
    assert add(owner, "one more") == (409, {"error": "at most 6 reference images"})
    assert len(call("GET", "/api/config", token=owner)[1]["references"]) == 6


# Delete a reference
def test_delete_reference(owner):
    add(owner, "milk bag")
    _, body = add(owner, "soda can")
    milk = next(r["id"] for r in body["references"] if r["annotation"] == "milk bag")
    status, body = call("DELETE", f"/api/config/references/{milk}", token=owner)
    assert status == 200
    assert [r["annotation"] for r in body["references"]] == ["soda can"]


# Unknown reference
@pytest.mark.parametrize("ref_id", ["bm9wZQ", "!!", api.encode_id("PENDING#x")])
def test_unknown_reference(owner, ref_id):
    add(owner, "milk bag")
    assert call("DELETE", f"/api/config/references/{ref_id}", token=owner)[0] == 404
    assert len(call("GET", "/api/config", token=owner)[1]["references"]) == 1


# Viewer cannot change config
def test_viewer_cannot_change_config(tokens):
    _, body = add(tokens["owner"], "milk bag")
    ref_id = body["references"][0]["id"]
    viewer = tokens["viewer"]
    for method, path, payload in [
        ("PUT", "/api/config/instructions", {"instructions": "x"}),
        ("POST", "/api/config/references", {"annotation": "x", "image": b64(JPEG)}),
        ("DELETE", f"/api/config/references/{ref_id}", None),
        ("PATCH", f"/api/config/references/{ref_id}", {"annotation": "x"}),
    ]:
        assert call(method, path, payload, viewer) == (403, {"error": "read-only"})
    assert call("GET", "/api/config", token=viewer)[1] == {
        "instructions": "",
        "references": body["references"],
    }


def edit(token, ref_id, payload):
    return call("PATCH", f"/api/config/references/{ref_id}", payload, token)


@pytest.fixture
def milk_and_soda(owner, monkeypatch):
    add(owner, "milk bag")
    monkeypatch.setattr(api, "now", lambda: NOW + 1)
    _, body = add(owner, "soda can")
    return body["references"]


# Edit the annotation
def test_edit_the_annotation(owner, milk_and_soda):
    milk = milk_and_soda[0]
    status, body = edit(owner, milk["id"], {"annotation": " chocolate milk "})
    assert status == 200
    assert body["references"] == [{**milk, "annotation": "chocolate milk"}, milk_and_soda[1]]


# Replace the image
def test_replace_the_image(owner, milk_and_soda):
    milk = milk_and_soda[0]
    new = b"\xff\xd8\xff\xe1" + b"\x01" * 500
    status, body = edit(owner, milk["id"], {"image": b64(new)})
    assert status == 200
    assert body["references"][0] == {**milk, "image": b64(new)}


# Edit both
def test_edit_both(owner, milk_and_soda):
    milk = milk_and_soda[0]
    new = b"\xff\xd8\xff\xe1" + b"\x01" * 500
    _, body = edit(owner, milk["id"], {"annotation": "chocomilk", "image": b64(new)})
    assert body["references"][0] == {**milk, "annotation": "chocomilk", "image": b64(new)}


# Nothing to change
def test_nothing_to_change(owner, milk_and_soda):
    ref_id = milk_and_soda[0]["id"]
    assert edit(owner, ref_id, {}) == (400, {"error": "send an annotation or an image"})
    headers = {"content-type": "application/json", "Authorization": f"Bearer {owner}"}
    event = api_event("PATCH", f"/api/config/references/{ref_id}", "{nope", headers, None)
    resp = api.handler(event, None)
    assert resp["statusCode"] == 400
    assert json.loads(resp["body"]) == {"error": "send an annotation or an image"}
    assert call("GET", "/api/config", token=owner)[1]["references"] == milk_and_soda


# Bad edit
@pytest.mark.parametrize(
    "payload, error",
    [
        ({"annotation": "   "}, "annotation must be 1 to 300 characters"),
        ({"annotation": "ok", "image": b64(PNG)}, "image must be a JPEG of at most 200 KB"),
    ],
)
def test_bad_edit(owner, milk_and_soda, payload, error):
    assert edit(owner, milk_and_soda[0]["id"], payload) == (400, {"error": error})
    assert call("GET", "/api/config", token=owner)[1]["references"] == milk_and_soda


# Edit an unknown reference
@pytest.mark.parametrize("ref_id", ["bm9wZQ", "!!", api.encode_id("PENDING#x")])
def test_edit_an_unknown_reference(owner, milk_and_soda, ref_id):
    assert edit(owner, ref_id, {"annotation": "x"})[0] == 404
    assert call("GET", "/api/config", token=owner)[1]["references"] == milk_and_soda


# No token
def test_no_token(tokens):
    assert call("GET", "/api/config") == (401, {"error": "sign in"})
