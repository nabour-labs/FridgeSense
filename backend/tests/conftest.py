import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture
def fixture():
    return load_fixture


APP_SECRET = "fridgesense/ring-app"
TOKEN_SECRET = "fridgesense/ring-tokens"
TABLE = "fridgesense"
APP_CONFIG = {
    "client_id": "cid",
    "client_secret": "csecret",
    "hmac_key": "test-hmac-key",
    "passcode": "open-sesame",
}


@pytest.fixture
def aws(monkeypatch):
    """Moto-backed Secrets Manager and DynamoDB with FridgeSense's resources."""
    import boto3
    from moto import mock_aws

    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("RING_APP_SECRET_ID", APP_SECRET)
    monkeypatch.setenv("RING_TOKENS_SECRET_ID", TOKEN_SECRET)
    monkeypatch.setenv("TABLE_NAME", TABLE)
    with mock_aws():
        sm = boto3.client("secretsmanager")
        sm.create_secret(Name=APP_SECRET, SecretString=json.dumps(APP_CONFIG))
        sm.create_secret(Name=TOKEN_SECRET, SecretString="{}")
        boto3.client("dynamodb").create_table(
            TableName=TABLE,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


class MemoryTokenStore:
    """In-memory stand-in for TokenStore."""

    def __init__(self, tokens=None):
        self.tokens = tokens
        self.saves = 0

    def load(self):
        return self.tokens

    def save(self, tokens):
        self.tokens = tokens
        self.saves += 1


@pytest.fixture(autouse=True)
def _reset_config_cache(monkeypatch):
    import fridgesense.store

    monkeypatch.setattr(fridgesense.store, "_config_cache", None)


def api_event(
    method: str,
    path: str,
    body: bytes | str | None = None,
    headers: dict[str, str] | None = None,
    query: dict[str, str] | None = None,
    base64: bool = False,
) -> dict:
    """An API Gateway HTTP API (payload v2) event."""
    import base64 as b64

    raw = body.encode() if isinstance(body, str) else body
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "&".join(f"{k}={v}" for k, v in (query or {}).items()),
        "queryStringParameters": query,
        "headers": {k.lower(): v for k, v in (headers or {}).items()},
        "requestContext": {"http": {"method": method, "path": path}},
        "body": None if raw is None else (b64.b64encode(raw).decode() if base64 else raw.decode()),
        "isBase64Encoded": base64,
    }


def jpeg(
    brightness: float = 0.0,
    bright_box: tuple[float, float, float, float] | None = None,
    size: tuple[int, int] = (320, 180),
) -> bytes:
    """A test JPEG: uniformly `brightness` (0-1), or dark with one bright box (fractions)."""
    import io

    from PIL import Image, ImageDraw

    level = round(brightness * 255)
    img = Image.new("L", size, level if bright_box is None else 0)
    if bright_box is not None:
        x, y, w, h = bright_box
        W, H = size
        ImageDraw.Draw(img).rectangle([x * W, y * H, (x + w) * W - 1, (y + h) * H - 1], fill=255)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=95)
    return buf.getvalue()
