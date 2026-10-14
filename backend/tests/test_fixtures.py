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
]


@pytest.mark.parametrize("name", RING_FIXTURES)
def test_ring_fixture_parses(name):
    assert isinstance(load_fixture(f"ring/{name}"), dict)
