import pytest

from tests.conftest import load_fixture

RING_FIXTURES = [
    "webhook_motion_detected.json",
    "webhook_app_integration_added.json",
    "webhook_button_press.json",
    "oauth_token.json",
    "oauth_refresh.json",
    "users_me.json",
    "devices.json",
    "app_integrations_patch.json",
    "history_events.json",
    "history_events_pending.json",
    "history_events_string_ts.json",
    "device_detail.json",
    "device_detail_recorded.json",
    "webhook_device_online.json",
    "webhook_device_offline.json",
    "video_download_303.json",
    "video_media_not_found.json",
]
NOVA_FIXTURES = [
    "converse_tool_use.json",
    "converse_text_then_tool.json",
    "converse_end_turn.json",
    "converse_old_shape.json",
    "converse_items_dropped.json",
]
REKOGNITION_FIXTURES = ["detect_faces_one.json", "detect_faces_two.json"]
CONVERSE_FIXTURES = [
    "tool_use_find_milk.json",
    "tool_use_inventory.json",
    "tool_use_find_eggs.json",
    "tool_use_two_finds.json",
    "tool_use_last_opened.json",
    "end_turn_milk.json",
    "end_turn_cook.json",
    "end_turn_hello.json",
    "end_turn_not_linked.json",
    "end_turn_thinking_only.json",
]


@pytest.mark.parametrize("name", RING_FIXTURES)
def test_ring_fixture_parses(name):
    assert isinstance(load_fixture(f"ring/{name}"), dict)


@pytest.mark.parametrize("name", NOVA_FIXTURES)
def test_nova_fixture_parses(name):
    assert "output" in load_fixture(f"nova/{name}")


@pytest.mark.parametrize("name", REKOGNITION_FIXTURES)
def test_rekognition_fixture_parses(name):
    faces = load_fixture(f"rekognition/{name}")["FaceDetails"]
    assert faces and all({"BoundingBox", "Confidence"} <= f.keys() for f in faces)


@pytest.mark.parametrize("name", CONVERSE_FIXTURES)
def test_converse_fixture_parses(name):
    resp = load_fixture(f"converse/{name}")
    assert resp["stopReason"] in {"tool_use", "end_turn"}
    assert {"inputTokens", "outputTokens"} <= resp["usage"].keys()
