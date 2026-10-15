"""Minimal request/response helpers for API Gateway HTTP API (payload v2)."""

import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs


@dataclass
class Request:
    method: str
    path: str
    headers: dict[str, str]
    query: dict[str, str]
    raw_body: bytes

    @classmethod
    def from_event(cls, event: dict) -> "Request":
        body = event.get("body") or ""
        raw = base64.b64decode(body) if event.get("isBase64Encoded") else body.encode()
        http = event.get("requestContext", {}).get("http", {})
        return cls(
            method=http.get("method", ""),
            path=event.get("rawPath", http.get("path", "")),
            headers={k.lower(): v for k, v in (event.get("headers") or {}).items()},
            query=dict(event.get("queryStringParameters") or {}),
            raw_body=raw,
        )

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip().lower()

    def fields(self) -> dict[str, str]:
        """Body fields from JSON or a form; empty if the body is neither."""
        if self.content_type == "application/json":
            try:
                data = json.loads(self.raw_body or b"{}")
            except ValueError:
                return {}
            return {k: str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        if self.content_type == "application/x-www-form-urlencoded":
            return {k: v[0] for k, v in parse_qs(self.raw_body.decode()).items()}
        return {}


def json_response(status: int, body: Any) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def html_response(status: int, html: str) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "content-type": "text/html; charset=utf-8",
            "cache-control": "no-store",
            "x-frame-options": "DENY",
        },
        "body": html,
    }
