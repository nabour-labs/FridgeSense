"""Ring app config and Ring tokens, both kept in Secrets Manager.

Jayson writes the app config once; only the Lambdas write the tokens.
"""

import json
import os
import time
from collections.abc import Callable
from typing import Literal

import boto3
from pydantic import BaseModel

CONFIG_TTL_S = 300


# Names of the deployed resources. The Lambdas get them as environment variables;
# the defaults let the CLI run from a laptop.
def app_secret_id() -> str:
    return os.environ.get("RING_APP_SECRET_ID", "fridgesense/ring-app")


def tokens_secret_id() -> str:
    return os.environ.get("RING_TOKENS_SECRET_ID", "fridgesense/ring-tokens")


def table_name() -> str:
    return os.environ.get("TABLE_NAME", "fridgesense")


LinkStatus = Literal["unclaimed", "linked", "needs_relink"]


class AppConfig(BaseModel):
    client_id: str = ""
    client_secret: str = ""
    hmac_key: str = ""
    passcode: str = ""
    demo_passcode: str = ""  # optional read-only passcode for judges


class Tokens(BaseModel):
    account_id: str
    access_token: str
    refresh_token: str
    expires_at: int  # epoch seconds
    link_status: LinkStatus


_config_cache: tuple[float, AppConfig] | None = None


def _secrets():
    return boto3.client("secretsmanager")


def load_app_config(now: Callable[[], float] = time.time, refresh: bool = False) -> AppConfig:
    global _config_cache
    t = now()
    if not refresh and _config_cache and t - _config_cache[0] < CONFIG_TTL_S:
        return _config_cache[1]
    raw = _secrets().get_secret_value(SecretId=app_secret_id())["SecretString"]
    cfg = AppConfig.model_validate(json.loads(raw or "{}"))
    _config_cache = (t, cfg)
    return cfg


class TokenStore:
    def __init__(self, secret_id: str | None = None):
        self.secret_id = secret_id or tokens_secret_id()
        self.client = _secrets()

    def load(self) -> Tokens | None:
        raw = self.client.get_secret_value(SecretId=self.secret_id)["SecretString"]
        data = json.loads(raw or "{}")
        return Tokens.model_validate(data) if data else None

    def save(self, tokens: Tokens) -> None:
        self.client.put_secret_value(SecretId=self.secret_id, SecretString=tokens.model_dump_json())
