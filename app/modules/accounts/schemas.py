import re
from datetime import datetime

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, field_validator

from app.core.passwords import PASSWORD_MAX_BYTES

MSG_INVALID_EMAIL = "Email không hợp lệ"
MSG_WEAK_PASSWORD = (
    "Mật khẩu phải có ít nhất 8 ký tự gồm chữ và số"
)
MSG_PASSWORD_TOO_LONG = "Mật khẩu không được dài quá 72 byte"
MSG_DISPLAY_NAME = (
    "Tên hiển thị không được để trống và tối đa 100 ký tự"
)

PASSWORD_MIN_LENGTH = 8
DISPLAY_NAME_MAX_LENGTH = 100
EMAIL_MAX_LENGTH = 255


# ----- Kiểm tra dùng chung

def normalize_email(value: str) -> str:
    email = value.strip()

    if not email or len(email) > EMAIL_MAX_LENGTH:
        raise ValueError(MSG_INVALID_EMAIL)

    try:
        result = validate_email(
            email,
            check_deliverability=False,
        )
    except EmailNotValidError:
        raise ValueError(MSG_INVALID_EMAIL) from None

    return result.normalized.lower()


def check_password_strength(value: str) -> str:
    has_letter = any(char.isalpha() for char in value)
    has_digit = re.search(r"\d", value) is not None

    if (
        len(value) < PASSWORD_MIN_LENGTH
        or not has_letter
        or not has_digit
    ):
        raise ValueError(MSG_WEAK_PASSWORD)

    if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(MSG_PASSWORD_TOO_LONG)

    return value


# ----- Dữ liệu đầu vào

class RegisterRequest(BaseModel):
    display_name: str
    email: str
    password: str

    @field_validator("display_name")
    @classmethod
    def _display_name(cls, value: str) -> str:
        name = value.strip()

        if not name or len(name) > DISPLAY_NAME_MAX_LENGTH:
            raise ValueError(MSG_DISPLAY_NAME)

        return name

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        return check_password_strength(value)


class LoginRequest(BaseModel):
    email: str
    password: str


# ----- Dữ liệu trả về

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str | None
    display_name: str
    avatar_url: str | None = None
    bio: str | None
    role: str
    created_at: datetime | None
    has_password: bool = False


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse