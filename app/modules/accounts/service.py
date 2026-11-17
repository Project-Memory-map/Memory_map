from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictException
from app.core.passwords import hash_password
from app.core.security import create_access_token
from app.modules.accounts.models import User
from app.modules.accounts.schemas import AuthResponse, RegisterRequest, UserResponse

MSG_REGISTER_OK = "Đăng ký thành công"
MSG_EMAIL_TAKEN = "Email này đã được đăng ký"


def find_user_by_email(db: Session, email: str) -> User | None:
    """BR-08: email duy nhất, không phân biệt hoa thường."""
    statement = select(User).where(func.lower(User.email) == email.strip().lower())
    return db.execute(statement).scalar_one_or_none()


def to_user_response(user: User) -> UserResponse:
    # profile.js đọc has_password + providers để chọn "Đổi mật khẩu" hay "Tạo mật khẩu" (US-ACC-007)
    providers = sorted({account.provider for account in user.oauth_accounts})
    return UserResponse.model_validate(user).model_copy(
        update={"has_password": bool(user.password_hash), "providers": providers}
    )


def issue_token(user: User) -> AuthResponse:
    token = create_access_token(user.id, user.token_version or 0)
    return AuthResponse(access_token=token, user=to_user_response(user))


def register(db: Session, payload: RegisterRequest) -> AuthResponse:
    """FR-1.1 / US-ACC-001: tạo tài khoản email + mật khẩu rồi đăng nhập luôn (GĐ1 chưa bắt buộc xác thực email)."""
    if find_user_by_email(db, payload.email) is not None:
        raise ConflictException(MSG_EMAIL_TAKEN)

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role="user",
        status="active",
        token_version=0,
        failed_login_count=0,
        last_login_at=datetime.now(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Hai yêu cầu cùng email gửi đồng thời: UNIQUE trên users.email chặn bản thứ hai
        db.rollback()
        raise ConflictException(MSG_EMAIL_TAKEN) from None
    db.refresh(user)
    return issue_token(user)
