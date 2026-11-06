from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_token_payload, get_token_payload_optional
from app.core.errors import ForbiddenException, UnauthorizedException
from app.modules.accounts.models import User


def _load_active_user(payload: dict, db: Session) -> User:
    user = db.get(User, int(payload["sub"]))
    if user is None or payload.get("tv") != user.token_version:
        raise UnauthorizedException("Phiên đăng nhập không còn hiệu lực, vui lòng đăng nhập lại")
    if user.status == "locked":
        raise ForbiddenException("Tài khoản của bạn đã bị khóa")
    return user


def get_current_user(payload: dict = Depends(get_token_payload), db: Session = Depends(get_db)) -> User:
    return _load_active_user(payload, db)


def get_optional_user(
    payload: dict | None = Depends(get_token_payload_optional), db: Session = Depends(get_db)
) -> User | None:
    if payload is None:
        return None
    return _load_active_user(payload, db)


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise ForbiddenException()
    return current_user
