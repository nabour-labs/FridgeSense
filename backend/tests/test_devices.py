"""ring-device-discovery: devices saved after linking, and the device command."""

import time
from urllib.parse import urlencode

import pytest
import respx

from fridgesense import cli
from fridgesense.crypto import nonce_for
from fridgesense.devices import Device, DeviceRepository
from fridgesense.handlers import http
from fridgesense.ring import API_BASE
from fridgesense.store import Tokens, TokenStore
from tests.conftest import APP_CONFIG, api_event, load_fixture

NOW = 1_771_131_000.0
NOW_MS = int(NOW * 1000)
ACCOUNT = "ava1.ring.account.A1"
INTEGRATIONS = f"{API_BASE}/v1/accounts/me/app-integrations"
DEVICES = f"{API_BASE}/v1/devices"
TWO_DEVICES = {
    "data": [
        {"type": "devices", "id": "ava1.ring.device.D1", "attributes": {"name": "Fridge Cam"}},
        {"type": "devices", "id": "ava1.ring.device.D2", "attributes": {"name": "Front Door"}},
    ]
}


def tokens(status="unclaimed", expires_at=int(NOW) + 3600):
    return Tokens(
        account_id=ACCOUNT,
        access_token="at1",
        refresh_token="rt1",
        expires_at=expires_at,
        link_status=status,
    )


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(http, "now", lambda: NOW)


def link(devices_response):
    time_ms = str(NOW_MS - 60_000)
    body = urlencode(
        {
            "passcode": APP_CONFIG["passcode"],
            "time": time_ms,
            "nonce": nonce_for(APP_CONFIG["hmac_key"], time_ms, ACCOUNT),
        }
    )
    with respx.mock() as mock:
        mock.post(INTEGRATIONS).respond(201, json={})
        mock.patch(INTEGRATIONS).respond(200, json=load_fixture("ring/app_integrations_patch.json"))
        mock.get(DEVICES).mock(return_value=devices_response)
        return http.handler(
            api_event(
                "POST", "/ring/link", body, {"content-type": "application/x-www-form-urlencoded"}
            ),
            None,
        )


def names(account=ACCOUNT):
    return {d.device_id: d.name for d in DeviceRepository().list(account)}


# One camera returned
def test_one_camera_returned(aws, clock):
    import httpx

    TokenStore().save(tokens())
    resp = link(httpx.Response(200, json=load_fixture("ring/devices.json")))
    assert resp["statusCode"] == 200
    assert names() == {"ava1.ring.device.D1": "Fridge Cam"}
    assert "Fridge Cam" in resp["body"]


# Device removed since last link
def test_device_removed_since_last_link(aws, clock):
    import httpx

    repo = DeviceRepository()
    repo.replace(
        ACCOUNT,
        [Device("ava1.ring.device.D1", "Fridge Cam"), Device("ava1.ring.device.D2", "Old Cam")],
    )
    TokenStore().save(tokens())
    link(httpx.Response(200, json=load_fixture("ring/devices.json")))
    assert names() == {"ava1.ring.device.D1": "Fridge Cam"}


def test_devices_of_other_accounts_untouched(aws):
    repo = DeviceRepository()
    repo.replace("ava1.ring.account.OTHER", [Device("ava1.ring.device.X", "Garage")])
    repo.replace(ACCOUNT, [Device("ava1.ring.device.D1", "Fridge Cam")])
    assert names("ava1.ring.account.OTHER") == {"ava1.ring.device.X": "Garage"}


# Device list unavailable
def test_device_list_unavailable(aws, clock):
    import httpx

    DeviceRepository().replace(ACCOUNT, [Device("ava1.ring.device.D1", "Fridge Cam")])
    TokenStore().save(tokens())
    resp = link(httpx.Response(503))
    assert resp["statusCode"] == 200
    assert TokenStore().load().link_status == "linked"
    assert names() == {"ava1.ring.device.D1": "Fridge Cam"}
    assert "could not be loaded" in resp["body"]


# Listing devices from the command line
def test_listing_devices_from_the_command_line(aws, capsys):
    TokenStore().save(tokens(status="linked", expires_at=int(time.time()) + 3600))
    with respx.mock() as mock:
        mock.get(DEVICES).respond(200, json=TWO_DEVICES)
        code = cli.devices_main()
    out = capsys.readouterr().out.splitlines()
    assert code == 0
    assert out == ["ava1.ring.device.D1  Fridge Cam", "ava1.ring.device.D2  Front Door"]
    assert names() == {"ava1.ring.device.D1": "Fridge Cam", "ava1.ring.device.D2": "Front Door"}


# No linked account
def test_device_command_without_linked_account(aws, capsys):
    assert cli.devices_main() == 1
    assert "No Ring account is linked" in capsys.readouterr().out


def test_device_command_when_ring_fails(aws, capsys):
    TokenStore().save(tokens(status="linked", expires_at=int(time.time()) + 3600))
    with respx.mock() as mock:
        mock.get(DEVICES).respond(500)
        assert cli.devices_main() == 1
    assert "Could not load devices" in capsys.readouterr().out
