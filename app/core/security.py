from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import Settings
from app.modules.accounts.models import User


class MissingJWTSecretError(Exception):
    pass


def create_access_token(user: User, settings: Settings) -> str:
    if not settings.jwt_secret_key:
        raise MissingJWTSecretError

    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "user_id": user.id,
        "role": user.role,
        "token_version": user.token_version,
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")