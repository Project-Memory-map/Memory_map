from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str | None
    display_name: str
    avatar_path: str | None
    bio: str | None
    role: str
    created_at: datetime


class RegisterRequest(BaseModel):
    # Kiểu str thô: quy tắc FR-1.1 / BR-07 / BR-08 kiểm tra ở service để trả đúng thông báo của AC.
    display_name: str
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
