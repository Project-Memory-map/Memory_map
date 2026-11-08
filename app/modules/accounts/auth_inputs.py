import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class ForgotRequest(BaseModel):
    email: EmailStr = Field(max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if isinstance(value, str):
            return value.strip().lower()
        return value


class LoginRequest(ForgotRequest):
    password: str = Field(min_length=1, max_length=256)


class TokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class ResetRequest(TokenRequest):
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def check_password(cls, value):
        has_letter = any(char.isalpha() for char in value)
        has_digit = re.search(r"\d", value) is not None

        if not has_letter or not has_digit:
            raise ValueError(
                "Mật khẩu phải có ít nhất 8 ký tự gồm chữ và số"
            )

        if len(value.encode("utf-8")) > 72:
            raise ValueError(
                "Mật khẩu không được dài quá 72 byte"
            )

        return value