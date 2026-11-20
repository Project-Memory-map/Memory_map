"""US-ACC-005 – Quên mật khẩu và đặt lại mật khẩu qua email (BR-14).

Dựa trên reset_feature.py của Lê Minh Trí (nhánh LeMinhTri_Sprint3), chuyển sang cấu trúc hiện tại.
- Token ngẫu nhiên, DB chỉ lưu SHA-256; hiệu lực 30 phút; dùng một lần (đặt xong vô hiệu mọi link còn lại).
- Email có hay không tồn tại đều trả cùng một thông báo (AC2: không lộ email nào đã đăng ký).
- Chưa cấu hình SMTP ở môi trường dev: trả dev_reset_url để forgot-password.html hiện link thử.
  Môi trường thật (APP_ENV khác dev) không bao giờ trả link qua API.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import BadRequestException
from app.core.passwords import hash_password
from app.core.response import build_response
from app.modules.accounts.models import PasswordResetToken, User
from app.modules.accounts.schemas import check_password_strength, normalize_email
from app.modules.accounts.service import find_user_by_email

router = APIRouter(tags=["M1 - Tài khoản"])
logger = logging.getLogger("bandokyuc.password_reset")

TOKEN_MINUTES = 30
RESEND_SECONDS = 60
MSG_SENT = "Nếu email tồn tại, chúng tôi đã gửi hướng dẫn đặt lại mật khẩu"
MSG_INVALID = "Liên kết không hợp lệ hoặc đã được sử dụng"
MSG_EXPIRED = "Liên kết đã hết hạn, vui lòng yêu cầu lại"
MSG_DONE = "Đặt lại mật khẩu thành công, bạn có thể đăng nhập bằng mật khẩu mới"


class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return normalize_email(value)


class TokenRequest(BaseModel):
    token: str


class ResetPasswordRequest(TokenRequest):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _new_password(cls, value: str) -> str:
        return check_password_strength(value)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def reset_url(raw_token: str) -> str:
    return f"{settings.app_base_url.rstrip('/')}/accounts/reset-password.html?{urlencode({'token': raw_token})}"


def send_reset_email(recipient: str, raw_token: str) -> None:
    """Chạy nền sau khi trả lời. Lỗi SMTP chỉ ghi log (không ghi token hay mật khẩu SMTP)."""
    message = EmailMessage()
    message["Subject"] = "Bản đồ Ký ức – Đặt lại mật khẩu"
    message["From"] = settings.smtp_from or settings.smtp_username
    message["To"] = recipient
    message.set_content(
        f"Mở liên kết sau để đặt lại mật khẩu:\n\n{reset_url(raw_token)}\n\n"
        f"Liên kết có hiệu lực {TOKEN_MINUTES} phút và chỉ dùng được một lần.\n"
        "Nếu bạn không yêu cầu, hãy bỏ qua email này."
    )
    try:
        context = ssl.create_default_context()
        if settings.smtp_ssl:
            client = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context)
        else:
            client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        with client:
            if not settings.smtp_ssl:
                client.starttls(context=context)
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)
    except (OSError, smtplib.SMTPException):
        logger.error("Gửi email đặt lại mật khẩu thất bại, kiểm tra cấu hình SMTP trong .env")


def _load_token(db: Session, raw_token: str, lock: bool = False) -> PasswordResetToken:
    stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token or ""))
    if lock:
        stmt = stmt.with_for_update()
    record = db.scalar(stmt.execution_options(populate_existing=True))
    if record is None or record.used_at is not None:
        raise BadRequestException(MSG_INVALID)
    if record.expires_at <= _now():
        raise BadRequestException(MSG_EXPIRED)
    return record


@router.post("/api/auth/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    raw_token = None
    user = find_user_by_email(db, payload.email)
    # Tài khoản bị khóa cũng nhận cùng thông báo nhưng không được cấp link
    if user is not None and user.status == "active":
        now = _now()
        recent = db.scalar(
            select(PasswordResetToken.id).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.created_at > now - timedelta(seconds=RESEND_SECONDS),
            ).limit(1)
        )
        if recent is None:  # tối đa 1 email / 60 giây / tài khoản
            raw_token = secrets.token_urlsafe(32)
            db.add(PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(raw_token),
                expires_at=now + timedelta(minutes=TOKEN_MINUTES),
                created_at=now,
            ))
            db.commit()

    data = None
    if raw_token:
        if settings.smtp_host:
            background_tasks.add_task(send_reset_email, user.email, raw_token)
        elif settings.is_dev:
            data = {"dev_reset_url": reset_url(raw_token)}
        else:
            logger.error("Chưa cấu hình SMTP: không gửi được email đặt lại mật khẩu")
    return build_response(200, MSG_SENT, request, data=data)


@router.post("/api/auth/validate-reset-token")
def validate_reset_token(payload: TokenRequest, request: Request, db: Session = Depends(get_db)):
    """reset-password.html gọi khi mở trang để báo ngay link hết hạn (AC4)."""
    record = _load_token(db, payload.token)
    user = db.get(User, record.user_id)
    if user is None or user.status != "active":
        raise BadRequestException(MSG_INVALID)
    return build_response(200, "Liên kết hợp lệ", request)


@router.post("/api/auth/reset-password")
def reset_password(payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    try:
        record = _load_token(db, payload.token, lock=True)
        user = db.scalar(select(User).where(User.id == record.user_id).with_for_update())
        if user is None or user.status != "active":
            raise BadRequestException(MSG_INVALID)

        user.password_hash = hash_password(payload.new_password)
        user.token_version = (user.token_version or 0) + 1  # BR-20: JWT cũ hết hiệu lực (trigger MySQL cũng làm)
        user.failed_login_count = 0
        user.first_failed_at = None
        user.login_locked_until = None
        # AC3: link này và mọi link chưa dùng khác của tài khoản không dùng lại được
        db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=_now())
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return build_response(200, MSG_DONE, request)
