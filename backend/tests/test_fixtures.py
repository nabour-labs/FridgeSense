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
]
NOVA_FIXTURES = [
    "converse_tool_use.json",
    "converse_text_then_tool.json",
    "converse_end_turn.json",
]
REKOGNITION_FIXTURES = ["detect_faces_one.json", "detect_faces_two.json"]


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
