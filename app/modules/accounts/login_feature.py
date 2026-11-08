"""T05B570 / US-ACC-002: Đăng nhập email và mật khẩu."""

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
from app.core.response import build_response
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.modules.accounts.auth_inputs import LoginRequest
from app.modules.accounts.models import User
from app.modules.accounts.schemas import UserResponse


router = APIRouter()

DUMMY_HASH = hash_password(secrets.token_urlsafe(24))

WRONG = "Email hoặc mật khẩu không đúng"
LOCKED = (
    "Bạn đã nhập sai quá nhiều lần, "
    "vui lòng thử lại sau 15 phút"
)


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    email = str(payload.email).lower()

    try:
        # Khóa bản ghi để cập nhật bộ đếm nhập sai.
        user = db.scalar(
            select(User)
            .where(func.lower(User.email) == email)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Đang khóa tạm: nhập đúng vẫn không được đăng nhập.
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

        try:
            valid = (
                len(payload.password.encode("utf-8")) <= 72
                and verify_password(
                    payload.password,
                    stored_hash,
                )
            )
        except ValueError:
            valid = False

        if user is None:
            raise UnauthorizedException(WRONG)

        # Đã hết thời gian khóa tạm.
        if user.login_locked_until:
            user.failed_login_count = 0
            user.first_failed_at = None
            user.login_locked_until = None

        if not valid or not user.password_hash:
            # Bắt đầu lại nếu lần sai đầu đã quá 15 phút.
            if (
                not user.first_failed_at
                or now - user.first_failed_at
                >= timedelta(minutes=15)
            ):
                user.failed_login_count = 0
                user.first_failed_at = now

            user.failed_login_count += 1
            blocked = user.failed_login_count >= 5

            if blocked:
                user.login_locked_until = (
                    now + timedelta(minutes=15)
                )

            # Lưu bộ đếm trước khi báo lỗi.
            db.commit()

            if blocked:
                raise TooManyRequestsException(LOCKED)

            raise UnauthorizedException(WRONG)

        # Tài khoản bị quản trị viên khóa.
        if user.status != "active":
            raise ForbiddenException(
                "Tài khoản của bạn đã bị khóa"
            )

        # Đăng nhập thành công.
        user.failed_login_count = 0
        user.first_failed_at = None
        user.login_locked_until = None
        user.last_login_at = now

        db.commit()

        response = build_response(
            200,
            "Đăng nhập thành công",
            request,
            data={
                "access_token": create_access_token(
                    user.id,
                    user.role,
                    user.token_version,
                ),
                "token_type": "bearer",
                "user": UserResponse.model_validate(user),
            },
        )

        response.headers["Cache-Control"] = "no-store"
        return response

    except Exception:
        db.rollback()
        raise