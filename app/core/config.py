from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    facebook_app_id: str | None = None
    facebook_app_secret: str | None = None
    facebook_redirect_uri: str = (
        "http://localhost:8000/api/accounts/facebook/callback"
    )
    jwt_secret_key: str | None = None
    database_path: str = "memory_map.sqlite3"
    facebook_http_timeout_seconds: float = 5.0
    cookie_secure: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        timeout_value = os.getenv("FACEBOOK_HTTP_TIMEOUT_SECONDS", "5")
        try:
            timeout = float(timeout_value)
        except ValueError as exc:
            raise ValueError(
                "FACEBOOK_HTTP_TIMEOUT_SECONDS phải là số dương"
            ) from exc
        if timeout <= 0:
            raise ValueError("FACEBOOK_HTTP_TIMEOUT_SECONDS phải là số dương")

        return cls(
            facebook_app_id=os.getenv("FACEBOOK_APP_ID") or None,
            facebook_app_secret=os.getenv("FACEBOOK_APP_SECRET") or None,
            facebook_redirect_uri=os.getenv(
                "FACEBOOK_REDIRECT_URI",
                "http://localhost:8000/api/accounts/facebook/callback",
            ),
            jwt_secret_key=os.getenv("JWT_SECRET_KEY") or None,
            database_path=os.getenv("DATABASE_PATH", "memory_map.sqlite3"),
            facebook_http_timeout_seconds=timeout,
            cookie_secure=os.getenv("COOKIE_SECURE", "false").lower()
            in {"1", "true", "yes"},
        )