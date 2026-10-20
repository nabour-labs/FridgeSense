"""fridge-change-analysis: One Nova request per door opening."""

import copy

import boto3
import pytest
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


# Schema order and required fields
def test_schema_order_and_required_fields():
    req = build_request(DEFAULT_MODEL_ID, STILLS, [])
    [tool] = req["toolConfig"]["tools"]
    schema = tool["toolSpec"]["inputSchema"]["json"]
    assert set(schema) == {"type", "properties", "required"}
    assert list(schema["properties"]) == ["observations", "items"]
    assert schema["required"] == ["observations", "items"]
    assert schema["properties"]["observations"]["type"] == "string"
    item = schema["properties"]["items"]["items"]
    assert item["required"] == ["item", "category", "quantity", "going_in", "coming_out"]
    assert item["properties"]["category"]["enum"] == CATEGORIES
    assert item["properties"]["going_in"]["type"] == "boolean"
    assert item["properties"]["coming_out"]["type"] == "boolean"


# Hand-evidence instructions
def test_hand_evidence_instructions():
    text = content_of(build_request(DEFAULT_MODEL_ID, STILLS, ["milk"]))[-1]["text"]
    assert "in a person's hand" in text
    assert "crossing the fridge opening" in text
    assert "resting on shelves or in the door are not changes" in text
    assert (
        "Names already in the inventory (reuse them for the same kind of item; "
        "do not report them unless you see them carried): [milk]"
    ) in text
    assert "Compare" not in text


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


REFS = [("milk bag", jpeg(0.7)), ("soda can", jpeg(0.8))]
REF_HEADER = (
    "Reference images: examples of items in this fridge. They are not part of this door opening."
)


# References before stills
def test_references_before_stills():
    content = content_of(build_request(DEFAULT_MODEL_ID, STILLS, ["milk"], references=REFS))
    assert content[0] == {"text": REF_HEADER}
    assert content[1] == {"text": "Reference 1: milk bag"}
    assert content[2] == {"image": {"format": "jpeg", "source": {"bytes": REFS[0][1]}}}
    assert content[3] == {"text": "Reference 2: soda can"}
    assert content[4] == {"image": {"format": "jpeg", "source": {"bytes": REFS[1][1]}}}
    assert content[5] == {"text": "Image 1 of 4"}
    assert content[6]["image"]["source"]["bytes"] == STILLS[0]
    assert "[milk]" in content[-1]["text"]


# Reference images as bytes
def test_reference_images_as_bytes_and_still_cap():
    six_stills = STILLS + [jpeg(0.5), jpeg(0.6)]
    content = content_of(build_request(DEFAULT_MODEL_ID, six_stills, [], references=REFS))
    images = [c["image"]["source"]["bytes"] for c in content if "image" in c]
    assert images == [REFS[0][1], REFS[1][1], *STILLS]
    assert [c["text"] for c in content if c.get("text", "").startswith("Image ")] == [
        f"Image {n} of 4" for n in range(1, 5)
    ]


# Custom instructions in the final text
def test_custom_instructions_in_the_final_text():
    final = content_of(
        build_request(
            DEFAULT_MODEL_ID, STILLS, ["milk"], instructions="Count yogurt cups individually."
        )
    )[-1]["text"]
    owner = "Owner's instructions: Count yogurt cups individually."
    assert owner in final
    assert final.index("[milk]") < final.index(owner)
    assert final.endswith(f"Call {TOOL_NAME} with your answer.")


def test_custom_instructions_with_braces_are_kept_verbatim():
    final = content_of(build_request(DEFAULT_MODEL_ID, STILLS, [], instructions="Use {x} as is"))
    assert "Owner's instructions: Use {x} as is" in final[-1]["text"]


# No config
def test_no_config_request_is_unchanged():
    plain = build_request(DEFAULT_MODEL_ID, STILLS, ["milk", "eggs"])
    assert (
        build_request(DEFAULT_MODEL_ID, STILLS, ["milk", "eggs"], references=[], instructions="")
        == plain
    )
    text = content_of(plain)[-1]["text"]
    assert "Owner's instructions" not in text
    assert content_of(plain)[0] == {"text": "Image 1 of 4"}


CACHE_POINT = {"cachePoint": {"type": "default"}}
REFS = [("milk bag", jpeg(0.3)), ("soda can", jpeg(0.6))]


def has_cache_point(value) -> bool:
    if isinstance(value, dict):
        return "cachePoint" in value or any(has_cache_point(v) for v in value.values())
    if isinstance(value, list):
        return any(has_cache_point(v) for v in value)
    return False


# Caching off by default
def test_caching_off_by_default():
    req = build_request(DEFAULT_MODEL_ID, STILLS, ["milk"], REFS, "Count cups.")
    assert not has_cache_point(req)
    assert req == build_request(
        DEFAULT_MODEL_ID, STILLS, ["milk"], REFS, "Count cups.", cache=False
    )


# Caching on with references
def test_caching_on_with_references():
    on = build_request(DEFAULT_MODEL_ID, STILLS, ["milk"], REFS, "Count cups.", cache=True)
    off = build_request(DEFAULT_MODEL_ID, STILLS, ["milk"], REFS, "Count cups.")
    content, plain = content_of(on), content_of(off)
    # header + 2 x (label, image) = 5 blocks, then a cache point; 4 x (label, image), then one more
    assert content[5] == CACHE_POINT
    assert content[14] == CACHE_POINT
    assert content[6] == {"text": "Image 1 of 4"}
    assert [c for c in content if c != CACHE_POINT] == plain
    assert content[-1] == plain[-1]


# Caching on without references
def test_caching_on_without_references():
    content = content_of(build_request(DEFAULT_MODEL_ID, STILLS[:2], [], cache=True))
    assert [i for i, c in enumerate(content) if c == CACHE_POINT] == [4]
    assert content[3]["image"]["source"]["bytes"] == STILLS[1]
    assert "text" in content[5]


# Cache point shape and placement limits
def test_cache_point_shape_and_limits():
    req = build_request(DEFAULT_MODEL_ID, STILLS, ["milk"], REFS, cache=True)
    points = [c["cachePoint"] for c in content_of(req) if "cachePoint" in c]
    assert points == [{"type": "default"}] * 2
    [tool] = req["toolConfig"]["tools"]
    assert set(tool) == {"toolSpec"}
    assert "system" not in req


@pytest.mark.parametrize(
    "setting, expected", [("true", True), (None, False), ("yes please", False), ("false", False)]
)
def test_cache_setting_from_environment(monkeypatch, setting, expected):
    # "Unrecognized setting value": anything but "true" leaves caching off
    if setting is None:
        monkeypatch.delenv("NOVA_CACHE_ANALYSIS", raising=False)
    else:
        monkeypatch.setenv("NOVA_CACHE_ANALYSIS", setting)
    analyzer = NovaAnalyzer.from_env(boto3.client("bedrock-runtime", region_name="us-east-1"))
    assert analyzer.cache_analysis is expected


# Retry sends the same cached request
def test_retry_sends_the_same_cached_request():
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    sent = []
    client.meta.events.register(
        "provide-client-params.bedrock-runtime.Converse",
        lambda params, **_: sent.append(copy.deepcopy(params)),
    )
    with Stubber(client) as stub:
        stub.add_response("converse", load_fixture("nova/converse_end_turn.json"))
        stub.add_response("converse", load_fixture("nova/converse_tool_use.json"))
        NovaAnalyzer(client, cache_analysis=True).analyze(STILLS, ["milk"], references=REFS)
    first, second = sent
    assert first == second
    assert has_cache_point(first)


# Scenario: Schema and prompt ask for images
def test_schema_and_prompt_ask_for_images():
    req = build_request(DEFAULT_MODEL_ID, STILLS, [])
    [tool] = req["toolConfig"]["tools"]
    item = tool["toolSpec"]["inputSchema"]["json"]["properties"]["items"]["items"]
    assert item["properties"]["moments"]["type"] == "array"
    assert item["properties"]["moments"]["items"] == {"type": "number"}
    assert "moments" not in item["required"]
    assert "moments" in content_of(req)[-1]["text"]


VIDEO = b"\x00\x00\x00\x18ftypmp42 analysis video bytes"
VIDEO_TEXT = "Video of the door opening, slowed down, in time order."


# Video instead of stills
def test_video_instead_of_stills():
    content = content_of(build_request(DEFAULT_MODEL_ID, STILLS, ["milk"], video=VIDEO))
    assert [c for c in content if "image" in c] == []
    assert content[0] == {"text": VIDEO_TEXT}
    assert content[1] == {"video": {"format": "mp4", "source": {"bytes": VIDEO}}}
    assert len(content) == 3
    assert "seconds from the start of the video" in content[-1]["text"]


# References before the video
def test_references_before_the_video():
    refs = [("milk bag", jpeg(0.3)), ("soda can", jpeg(0.6))]
    content = content_of(build_request(DEFAULT_MODEL_ID, STILLS, [], refs, video=VIDEO))
    assert [content[i].get("text") for i in (0, 1, 3)] == [
        REF_HEADER,
        "Reference 1: milk bag",
        "Reference 2: soda can",
    ]
    assert content[5] == {"text": VIDEO_TEXT}
    assert "video" in content[6]


# Cache point after the video
def test_cache_point_after_the_video():
    content = content_of(build_request(DEFAULT_MODEL_ID, STILLS, [], video=VIDEO, cache=True))
    points = [i for i, c in enumerate(content) if "cachePoint" in c]
    assert points == [2]
    assert "video" in content[1] and "text" in content[3]
