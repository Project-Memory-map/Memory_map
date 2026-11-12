"""Lấy người dùng đang đăng nhập từ header Authorization: Bearer <token>."""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token
from app.modules.accounts.models import User

bearer = HTTPBearer(auto_error=False)


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload or not str(payload.get("sub", "")).isdigit():
        return None
    user = db.get(User, int(payload["sub"]))
    if user is None or user.token_version != payload.get("tv"):
        return None
    return user


def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    if user is None:
        raise UnauthorizedException()
    if user.status == "locked":
        raise ForbiddenException("Tài khoản của bạn đã bị khóa")
    return user
