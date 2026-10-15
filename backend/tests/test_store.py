"""App config and token store on Secrets Manager."""

import json

import boto3

from fridgesense.store import AppConfig, Tokens, TokenStore, load_app_config
from tests.conftest import APP_SECRET, TOKEN_SECRET


def test_load_app_config(aws):
    cfg = load_app_config(now=lambda: 0.0, refresh=True)
    assert cfg == AppConfig(
        client_id="cid", client_secret="csecret", hmac_key="test-hmac-key", passcode="open-sesame"
    )


def test_app_config_cached_for_five_minutes(aws):
    load_app_config(now=lambda: 1000.0, refresh=True)
    boto3.client("secretsmanager").put_secret_value(
        SecretId=APP_SECRET, SecretString=json.dumps({"client_id": "new"})
    )
    assert load_app_config(now=lambda: 1299.0).client_id == "cid"
    assert load_app_config(now=lambda: 1301.0).client_id == "new"


def test_app_config_missing_fields_are_empty(aws):
    boto3.client("secretsmanager").put_secret_value(SecretId=APP_SECRET, SecretString="{}")
    cfg = load_app_config(now=lambda: 0.0, refresh=True)
    assert cfg.hmac_key == ""


def test_empty_token_store_returns_none(aws):
    assert TokenStore().load() is None


def test_token_store_round_trip(aws):
    tokens = Tokens(
        account_id="ava1.ring.account.A1",
        access_token="at1",
        refresh_token="rt1",
        expires_at=1_771_145_306,
        link_status="unclaimed",
    )
    TokenStore().save(tokens)
    assert TokenStore().load() == tokens
    raw = boto3.client("secretsmanager").get_secret_value(SecretId=TOKEN_SECRET)
    assert json.loads(raw["SecretString"])["link_status"] == "unclaimed"


def test_resource_names_default_to_deployed_names(aws, monkeypatch):
    from fridgesense.devices import DeviceRepository

    for var in ["RING_APP_SECRET_ID", "RING_TOKENS_SECRET_ID", "TABLE_NAME"]:
        monkeypatch.delenv(var)
    assert load_app_config(now=lambda: 0.0, refresh=True).client_id == "cid"
    assert TokenStore().secret_id == "fridgesense/ring-tokens"
    assert DeviceRepository().table.name == "fridgesense"


def test_mcp_key_is_optional(aws):
    assert load_app_config(now=lambda: 0.0, refresh=True).mcp_key == ""
