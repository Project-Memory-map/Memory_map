from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.accounts.models import User

_bearer_scheme = HTTPBearer(auto_error=False)
_LOGIN_REQUIRED = "Vui lòng đăng nhập để tiếp tục"


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_LOGIN_REQUIRED,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> User:
    if credentials is None:
        raise _unauthorized()

    settings = request.app.state.settings
    if not settings.jwt_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT_SECRET_KEY chưa được cấu hình",
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=["HS256"],
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized() from exc

    user_id = payload.get("user_id")
    token_version = payload.get("token_version")
    if type(user_id) is not int or type(token_version) is not int:
        raise _unauthorized()

    user = request.app.state.user_repository.get_by_id(user_id)
    if (
        user is None
        or user.status == "locked"
        or user.token_version != token_version
    ):
        raise _unauthorized()
    return user