"""T05B573 / US-ACC-005: Gửi email và đặt lại mật khẩu."""

import logging
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR
from app.core.database import get_db
from app.core.errors import AppException
from app.core.response import build_response
from app.core.security import hash_password, hash_token
from app.modules.accounts.auth_inputs import (
    ForgotRequest,
    ResetRequest,
    TokenRequest,
)
from app.modules.accounts.models import PasswordResetToken, User


router = APIRouter()
logger = logging.getLogger(__name__)

INVALID = "Liên kết không hợp lệ hoặc đã được sử dụng"
EXPIRED = "Liên kết đã hết hạn, vui lòng yêu cầu lại"
SENT = (
    "Nếu email tồn tại, chúng tôi đã gửi "
    "hướng dẫn đặt lại mật khẩu"
)


class MailSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_base_url: AnyHttpUrl = "http://127.0.0.1:8000"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_ssl: bool = False


mail = MailSettings()


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def send_email(recipient: str, raw_token: str):
    url = (
        str(mail.app_base_url).rstrip("/")
        + "/accounts/reset-password.html?"
        + urlencode({"token": raw_token})
    )

    message = EmailMessage()
    message["Subject"] = "Bản đồ Ký ức - Đặt lại mật khẩu"
    message["From"] = mail.smtp_from or mail.smtp_username
    message["To"] = recipient

    message.set_content(
        f"Mở liên kết để đặt lại mật khẩu:\n\n{url}\n\n"
        "Liên kết có hiệu lực 30 phút và chỉ sử dụng một lần.\n"
        "Nếu bạn không yêu cầu, hãy bỏ qua email này."
    )

    try:
        if not mail.smtp_host:
            raise RuntimeError("Chưa cấu hình SMTP")

        context = ssl.create_default_context()

        if mail.smtp_ssl:
            client = smtplib.SMTP_SSL(
                mail.smtp_host,
                mail.smtp_port,
                timeout=15,
                context=context,
            )
        else:
            client = smtplib.SMTP(
                mail.smtp_host,
                mail.smtp_port,
                timeout=15,
            )

        with client:
            if not mail.smtp_ssl:
                client.starttls(context=context)

            if mail.smtp_username:
                client.login(
                    mail.smtp_username,
                    mail.smtp_password,
                )

            client.send_message(message)

    except (OSError, smtplib.SMTPException, RuntimeError):
        # Không ghi token hoặc mật khẩu SMTP vào log.
        logger.error(
            "Gửi email thất bại. Hãy kiểm tra cấu hình SMTP."
        )


def check_token(record):
    if record is None or record.used_at is not None:
        raise AppException(INVALID)

    if record.expires_at <= now_utc():
        raise AppException(EXPIRED)


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    email = str(payload.email).lower()
    delivery = None

    try:
        user = db.scalar(
            select(User)
            .where(func.lower(User.email) == email)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        if user and user.status == "active":
            now = now_utc()

            # Một lần gửi mỗi 60 giây/tài khoản.
            recent = db.scalar(
                select(PasswordResetToken.id)
                .where(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.created_at
                    > now - timedelta(seconds=60),
                )
                .limit(1)
            )

            if recent is None:
                raw = secrets.token_urlsafe(32)

                # Database chỉ lưu hash, không lưu token gốc.
                db.add(
                    PasswordResetToken(
                        user_id=user.id,
                        token_hash=hash_token(raw),
                        expires_at=now + timedelta(minutes=30),
                        created_at=now,
                    )
                )

                delivery = (user.email, raw)

        db.commit()

    except Exception:
        db.rollback()
        raise

    # Chỉ gửi email sau khi token đã được lưu.
    if delivery:
        background_tasks.add_task(send_email, *delivery)

    # Email có tồn tại hay không đều trả cùng thông báo.
    return build_response(
        200,
        SENT,
        request,
    )


@router.post("/validate-reset-token")
def validate_token(
    payload: TokenRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    record = db.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash
            == hash_token(payload.token)
        )
        .execution_options(populate_existing=True)
    )

    check_token(record)

    user = db.get(User, record.user_id)

    if user is None or user.status != "active":
        raise AppException(INVALID)

    return build_response(
        200,
        "Liên kết hợp lệ",
        request,
    )


@router.post("/reset-password")
def reset_password(
    payload: ResetRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        digest = hash_token(payload.token)

        user_id = db.scalar(
            select(PasswordResetToken.user_id).where(
                PasswordResetToken.token_hash == digest
            )
        )

        if user_id is None:
            raise AppException(INVALID)

        # Khóa user trước, token sau.
        user = db.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        record = db.scalar(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == digest)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        check_token(record)

        if user is None or user.status != "active":
            raise AppException(INVALID)

        user.password_hash = hash_password(
            payload.new_password
        )

        # Vô hiệu hóa JWT được cấp trước khi đổi mật khẩu.
        user.token_version += 1

        user.failed_login_count = 0
        user.first_failed_at = None
        user.login_locked_until = None

        # Vô hiệu hóa tất cả link chưa dùng của tài khoản.
        db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=now_utc())
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return build_response(
        200,
        "Đã đặt lại mật khẩu, vui lòng đăng nhập lại",
        request,
    )