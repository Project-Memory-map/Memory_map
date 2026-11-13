import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import (
    ForbiddenException,
    TooManyRequestsException,
    UnauthorizedException,
)
from app.core.passwords import hash_password, verify_password
from app.core.response import build_response
from app.modules.accounts import service
from app.modules.accounts.deps import get_current_user
from app.modules.accounts.models import User
from app.modules.accounts.schemas import LoginRequest

router = APIRouter(tags=["M1 - Tài khoản"])

DUMMY_HASH = hash_password(secrets.token_urlsafe(24))
WINDOW = timedelta(minutes=15)

WRONG = "Email hoặc mật khẩu không đúng"
LOCKED = (
    "Bạn đã nhập sai quá nhiều lần, "
    "vui lòng thử lại sau 15 phút"
)


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ----- Đăng nhập

@router.post("/api/auth/login")
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()

    try:
        user = db.scalar(
            select(User)
            .where(func.lower(User.email) == email)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        now = now_utc()

        if (
            user
            and user.login_locked_until
            and user.login_locked_until > now
        ):
            raise TooManyRequestsException(LOCKED)

        stored_hash = (
            user.password_hash
            if user and user.password_hash
            else DUMMY_HASH
        )

        valid = verify_password(
            payload.password,
            stored_hash,
        )

        if user is None:
            raise UnauthorizedException(WRONG)

        if user.login_locked_until:
            user.failed_login_count = 0
            user.first_failed_at = None
            user.login_locked_until = None

        if not valid or not user.password_hash:
            if (
                user.first_failed_at is None
                or now - user.first_failed_at >= WINDOW
            ):
                user.failed_login_count = 0
                user.first_failed_at = now

            user.failed_login_count = (
                user.failed_login_count or 0
            ) + 1

            blocked = user.failed_login_count >= 5

            if blocked:
                user.login_locked_until = now + WINDOW

            # Lưu bộ đếm trước khi trả lỗi.
            db.commit()

            if blocked:
                raise TooManyRequestsException(LOCKED)

            raise UnauthorizedException(WRONG)

        if user.status != "active":
            raise ForbiddenException(
                "Tài khoản của bạn đã bị khóa"
            )

        user.failed_login_count = 0
        user.first_failed_at = None
        user.login_locked_until = None
        user.last_login_at = now

        db.commit()

        response = build_response(
            200,
            "Đăng nhập thành công",
            request,
            data=service.issue_token(user),
        )

        response.headers["Cache-Control"] = "no-store"
        return response

    except Exception:
        db.rollback()
        raise


# ----- Tài khoản đang đăng nhập

@router.get("/api/auth/me")
def read_me(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    response = build_response(
        200,
        "Lấy thông tin tài khoản thành công",
        request,
        data=service.to_user_response(current_user),
    )

    response.headers["Cache-Control"] = "no-store"
    return response