import re
from datetime import datetime, timezone

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppException, ConflictException
from app.core.security import create_access_token, hash_password
from app.modules.accounts import repository
from app.modules.accounts.schemas import AuthResponse, UserResponse

MSG_REGISTER_OK = "Đăng ký thành công"
MSG_INVALID_EMAIL = "Email không hợp lệ"
MSG_WEAK_PASSWORD = "Mật khẩu phải có ít nhất 8 ký tự gồm chữ và số"
MSG_PASSWORD_TOO_LONG = "Mật khẩu không được dài quá 72 byte"
MSG_EMAIL_TAKEN = "Email này đã được đăng ký"
MSG_DISPLAY_NAME = "Tên hiển thị không được để trống và tối đa 100 ký tự"

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_BYTES = 72  # giới hạn của bcrypt
DISPLAY_NAME_MAX_LENGTH = 100
EMAIL_MAX_LENGTH = 255


class RegisterValidationError(AppException):
    status_code = 422
    error = "VALIDATION_ERROR"


def normalize_email(raw_email: str) -> str:
    email = raw_email.strip()
    if not email or len(email) > EMAIL_MAX_LENGTH:
        raise RegisterValidationError(MSG_INVALID_EMAIL)
    try:
        result = validate_email(email, check_deliverability=False)
    except EmailNotValidError:
        raise RegisterValidationError(MSG_INVALID_EMAIL) from None
    return result.normalized.lower()


def check_password_strength(password: str) -> None:
    # BR-07: tối thiểu 8 ký tự, có ít nhất một chữ cái và một chữ số.
    has_letter = any(char.isalpha() for char in password)
    has_digit = re.search(r"\d", password) is not None
    if len(password) < PASSWORD_MIN_LENGTH or not has_letter or not has_digit:
        raise RegisterValidationError(MSG_WEAK_PASSWORD)
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise RegisterValidationError(MSG_PASSWORD_TOO_LONG)


def clean_display_name(raw_name: str) -> str:
    name = raw_name.strip()
    if not name or len(name) > DISPLAY_NAME_MAX_LENGTH:
        raise RegisterValidationError(MSG_DISPLAY_NAME)
    return name


def register(db: Session, *, display_name: str, email: str, password: str) -> AuthResponse:
    """FR-1.1 / US-ACC-001: tạo tài khoản email + mật khẩu và đăng nhập luôn (GĐ1 chưa bắt buộc xác thực email)."""
    name = clean_display_name(display_name)
    normalized_email = normalize_email(email)
    check_password_strength(password)

    if repository.find_by_email(db, normalized_email) is not None:
        raise ConflictException(MSG_EMAIL_TAKEN)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        user = repository.create_user(
            db,
            email=normalized_email,
            password_hash=hash_password(password),
            display_name=name,
            last_login_at=now,
        )
        db.commit()
    except IntegrityError:
        # Hai yêu cầu đăng ký cùng email gửi đồng thời: UNIQUE uq_users_email chặn bản thứ hai.
        db.rollback()
        raise ConflictException(MSG_EMAIL_TAKEN) from None

    db.refresh(user)
    token = create_access_token(user.id, user.role, user.token_version)
    return AuthResponse(access_token=token, user=UserResponse.model_validate(user))
