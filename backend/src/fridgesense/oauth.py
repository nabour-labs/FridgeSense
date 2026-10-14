"""Ring's OAuth token endpoint: code exchange and refresh."""

import httpx
from pydantic import BaseModel

OAUTH_URL = "https://oauth.ring.com/oauth/token"
TIMEOUT_S = 10.0


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int


class OAuthRejected(Exception):
    """Ring refused the grant (4xx): bad or expired code or refresh token."""


class OAuthUnavailable(Exception):
    """Ring's OAuth endpoint failed or timed out (5xx, network)."""


class OAuthClient:
    def __init__(self, http: httpx.Client, client_id: str, client_secret: str):
        self.http = http
        self.client_id = client_id
        self.client_secret = client_secret

    def exchange_code(self, code: str) -> TokenResponse:
        return self._grant({"grant_type": "authorization_code", "code": code})

    def refresh(self, refresh_token: str) -> TokenResponse:
        return self._grant({"grant_type": "refresh_token", "refresh_token": refresh_token})

    def _grant(self, fields: dict[str, str]) -> TokenResponse:
        data = {**fields, "client_id": self.client_id, "client_secret": self.client_secret}
        try:
            resp = self.http.post(OAUTH_URL, data=data, timeout=TIMEOUT_S)
        except httpx.HTTPError as e:
            raise OAuthUnavailable(type(e).__name__) from None
        if resp.status_code >= 500:
            raise OAuthUnavailable(f"HTTP {resp.status_code}")
        if resp.status_code >= 400:
            raise OAuthRejected(f"HTTP {resp.status_code}")
        return TokenResponse.model_validate(resp.json())
