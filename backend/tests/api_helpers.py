"""Shared helpers for the inventory API tests."""

import json

import boto3

from fridgesense.handlers import api
from fridgesense.store import Tokens, TokenStore
from tests.conftest import APP_CONFIG, APP_SECRET, api_event

ACCOUNT = "ava1.ring.account.A1"
NOW = 1_786_000_000.0


def configure(**fields):
    boto3.client("secretsmanager").put_secret_value(
        SecretId=APP_SECRET, SecretString=json.dumps({**APP_CONFIG, **fields})
    )


def link_account():
    TokenStore().save(
        Tokens(
            account_id=ACCOUNT,
            access_token="at1",
            refresh_token="rt1",
            expires_at=int(NOW) + 3600,
            link_status="linked",
        )
    )


def call(method, path, body=None, token=None, query=None):
    headers = {"content-type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    raw = None if body is None else json.dumps(body)
    resp = api.handler(api_event(method, path, raw, headers, query), None)
    return resp["statusCode"], json.loads(resp["body"]) if resp.get("body") else None


def sign_in(passcode="open-sesame"):
    status, body = call("POST", "/api/session", {"passcode": passcode})
    assert status == 200, body
    return body["token"]
