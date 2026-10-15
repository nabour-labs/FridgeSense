"""fridge-change-analysis: One Nova request per door opening."""

import boto3
from botocore.stub import Stubber

from fridgesense.analysis import (
    CATEGORIES,
    DEFAULT_MODEL_ID,
    TOOL_NAME,
    NovaAnalyzer,
    build_request,
)
from tests.conftest import jpeg, load_fixture

STILLS = [jpeg(0.1 * n) for n in range(1, 5)]


def content_of(request: dict) -> list[dict]:
    [message] = request["messages"]
    assert message["role"] == "user"
    return message["content"]


# Request built from stills and inventory
def test_request_built_from_stills_and_inventory():
    req = build_request(DEFAULT_MODEL_ID, STILLS, ["milk", "eggs"])
    assert DEFAULT_MODEL_ID == "us.amazon.nova-2-lite-v1:0"
    assert req["modelId"] == DEFAULT_MODEL_ID
    content = content_of(req)
    assert [c.get("text") for c in content[:-1:2]] == [f"Image {n} of 4" for n in range(1, 5)]
    assert [c["image"]["source"]["bytes"] for c in content[1:-1:2]] == STILLS
    assert "[milk, eggs]" in content[-1]["text"]
    assert req["toolConfig"]["toolChoice"] == {"tool": {"name": TOOL_NAME}}
    assert TOOL_NAME == "record_fridge_changes"
    assert req["inferenceConfig"]["temperature"] == 0


def test_tool_schema_follows_nova_rules():
    req = build_request(DEFAULT_MODEL_ID, STILLS, [])
    [tool] = req["toolConfig"]["tools"]
    schema = tool["toolSpec"]["inputSchema"]["json"]
    assert set(schema) == {"type", "properties", "required"}
    assert schema["required"] == ["added", "removed"]
    item = schema["properties"]["added"]["items"]
    assert item["required"] == ["item", "category", "quantity", "confidence"]
    assert item["properties"]["category"]["enum"] == CATEGORIES
    assert schema["properties"]["removed"]["items"] == item


# Empty inventory
def test_empty_inventory():
    assert "[]" in content_of(build_request(DEFAULT_MODEL_ID, STILLS, []))[-1]["text"]


# Stills sent as bytes
def test_stills_sent_as_bytes():
    images = [
        c["image"] for c in content_of(build_request(DEFAULT_MODEL_ID, STILLS, [])) if "image" in c
    ]
    assert images == [{"format": "jpeg", "source": {"bytes": s}} for s in STILLS]


def test_at_most_four_images():
    many = [jpeg(0.5)] * 6
    images = [c for c in content_of(build_request(DEFAULT_MODEL_ID, many, [])) if "image" in c]
    assert len(images) == 4


def test_analyzer_sends_exactly_the_built_request():
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    expected = build_request(DEFAULT_MODEL_ID, STILLS, ["milk"])
    with Stubber(client) as stub:
        stub.add_response("converse", load_fixture("nova/converse_tool_use.json"), expected)
        NovaAnalyzer(client).analyze(STILLS, ["milk"])
        stub.assert_no_pending_responses()
