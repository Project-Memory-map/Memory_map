from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, settings

GRAPH_API_BASE = "https://graph.facebook.com"
FACEBOOK_AUTHORIZE_URL = "https://www.facebook.com/dialog/oauth"


class FacebookOAuthError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class FacebookProfile:
    facebook_id: str
    display_name: str
    email: str | None


class FacebookAuthService:
    def __init__(
        self,
        settings_obj: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings_obj or settings
        self.transport = transport

    def authorization_url(self, state: str) -> str:
        app_id, _ = self._credentials()
        return str(
            httpx.URL(
                FACEBOOK_AUTHORIZE_URL,
                params={
                    "client_id": app_id,
                    "redirect_uri": self.settings.facebook_redirect_uri,
                    "response_type": "code",
                    "scope": "email",
                    "state": state,
                },
            )
        )

    async def profile_from_code(self, code: str) -> FacebookProfile:
        app_id, app_secret = self._credentials()
        access_token = await self._exchange_code(code, app_id, app_secret)
        return await self.profile_from_access_token(access_token)

    async def profile_from_access_token(
        self,
        access_token: str,
    ) -> FacebookProfile:
        if not access_token.strip():
            raise FacebookOAuthError(401, "Facebook access token không hợp lệ")

        data = await self._get_json(
            f"{GRAPH_API_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "id,name,email"},
        )
        facebook_id = data.get("id")
        display_name = data.get("name")
        email = data.get("email")
        if not isinstance(facebook_id, str) or not facebook_id:
            raise FacebookOAuthError(502, "Facebook trả về hồ sơ không hợp lệ")
        if not isinstance(display_name, str) or not display_name.strip():
            raise FacebookOAuthError(502, "Facebook không trả về tên hiển thị")
        if email is not None and not isinstance(email, str):
            raise FacebookOAuthError(502, "Facebook trả về email không hợp lệ")
        return FacebookProfile(
            facebook_id=facebook_id,
            display_name=display_name.strip(),
            email=email.strip().lower() if email and email.strip() else None,
        )

    async def _exchange_code(
        self,
        code: str,
        app_id: str,
        app_secret: str,
    ) -> str:
        data = await self._get_json(
            f"{GRAPH_API_BASE}/oauth/access_token",
            params={
                "client_id": app_id,
                "client_secret": app_secret,
                "redirect_uri": self.settings.facebook_redirect_uri,
                "code": code,
            },
        )
        access_token = data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise FacebookOAuthError(401, "Facebook không chấp nhận mã đăng nhập")
        return access_token

    async def _get_json(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.facebook_http_timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(url, params=params, headers=headers)
        except httpx.TimeoutException as exc:
            raise FacebookOAuthError(
                502,
                "Facebook không phản hồi kịp thời",
            ) from exc
        except httpx.RequestError as exc:
            raise FacebookOAuthError(
                502,
                "Không thể kết nối tới Facebook",
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise FacebookOAuthError(
                502,
                "Facebook trả về phản hồi không hợp lệ",
            ) from exc
        if not isinstance(data, dict):
            raise FacebookOAuthError(502, "Facebook trả về phản hồi không hợp lệ")

        if response.is_error or "error" in data:
            error = data.get("error")
            error_code = error.get("code") if isinstance(error, dict) else None
            status_code = (
                401
                if response.status_code in {400, 401}
                or error_code == 190
                else 502
            )
            raise FacebookOAuthError(
                status_code,
                "Facebook access token hoặc mã đăng nhập không hợp lệ",
            )
        return data

    def _credentials(self) -> tuple[str, str]:
        app_id = self.settings.facebook_app_id
        app_secret = self.settings.facebook_app_secret
        if not app_id or not app_secret:
            raise FacebookOAuthError(
                503,
                "Đăng nhập Facebook chưa được cấu hình",
            )
        return app_id, app_secret


def authorization_url(state: str) -> str:
    return FacebookAuthService(settings).authorization_url(state)


async def profile_from_code(code: str) -> FacebookProfile:
    return await FacebookAuthService(settings).profile_from_code(code)


async def profile_from_access_token(access_token: str) -> FacebookProfile:
    return await FacebookAuthService(settings).profile_from_access_token(access_token)
