"""US-ACC-003: Google OAuth 2.0 (luồng authorization code chạy ở máy chủ, giống facebook_auth.py).

Cấu hình trong .env: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
(Google Cloud Console → APIs & Services → Credentials → OAuth client ID loại "Web application",
thêm Authorized redirect URI đúng bằng GOOGLE_REDIRECT_URI).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, settings

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class GoogleProfile:
    google_id: str
    display_name: str
    email: str | None
    email_verified: bool


class GoogleAuthService:
    def __init__(self, settings_obj: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings_obj or settings
        self.transport = transport

    def _credentials(self) -> tuple[str, str]:
        client_id, secret = self.settings.google_client_id, self.settings.google_client_secret
        if not client_id or not secret:
            raise GoogleOAuthError(503, "Đăng nhập Google chưa được cấu hình")
        return client_id, secret

    def authorization_url(self, state: str) -> str:
        client_id, _ = self._credentials()
        return str(httpx.URL(AUTHORIZE_URL, params={
            "client_id": client_id,
            "redirect_uri": self.settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }))

    async def profile_from_code(self, code: str) -> GoogleProfile:
        client_id, secret = self._credentials()
        tokens = await self._request("POST", TOKEN_URL, data={
            "code": code,
            "client_id": client_id,
            "client_secret": secret,
            "redirect_uri": self.settings.google_redirect_uri,
            "grant_type": "authorization_code",
        })
        access_token = tokens.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise GoogleOAuthError(401, "Google không chấp nhận mã đăng nhập")
        info = await self._request("GET", USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})

        google_id, email = info.get("sub"), info.get("email")
        if not isinstance(google_id, str) or not google_id:
            raise GoogleOAuthError(502, "Google trả về hồ sơ không hợp lệ")
        email = email.strip().lower() if isinstance(email, str) and email.strip() else None
        name = info.get("name") if isinstance(info.get("name"), str) and info["name"].strip() else None
        return GoogleProfile(
            google_id=google_id,
            display_name=(name or (email.split("@")[0] if email else "Người dùng Google")).strip()[:100],
            email=email,
            email_verified=info.get("email_verified") is True,
        )

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.settings.google_http_timeout_seconds, transport=self.transport) as client:
                response = await client.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise GoogleOAuthError(502, "Google không phản hồi kịp thời") from exc
        except httpx.RequestError as exc:
            raise GoogleOAuthError(502, "Không thể kết nối tới Google") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise GoogleOAuthError(502, "Google trả về phản hồi không hợp lệ") from exc
        if response.is_error or not isinstance(data, dict) or "error" in data:
            raise GoogleOAuthError(401 if response.status_code in (400, 401) else 502, "Mã đăng nhập Google không hợp lệ")
        return data


def authorization_url(state: str) -> str:
    return GoogleAuthService(settings).authorization_url(state)


async def profile_from_code(code: str) -> GoogleProfile:
    return await GoogleAuthService(settings).profile_from_code(code)
