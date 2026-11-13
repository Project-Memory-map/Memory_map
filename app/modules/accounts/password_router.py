"""US-ACC-007 – Đổi mật khẩu khi đang đăng nhập (T05B575).

- Tài khoản đã có mật khẩu: phải nhập đúng mật khẩu hiện tại.
- Tài khoản chỉ đăng nhập Google/Facebook (chưa có mật khẩu): được tạo mật khẩu mới.
- BR-20: tăng token_version để đăng xuất mọi phiên khác, trả token mới cho phiên hiện tại.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import BadRequestException
from app.core.passwords import hash_password, verify_password
from app.core.response import build_response
from app.modules.accounts import service
from app.modules.accounts.deps import get_current_user
from app.modules.accounts.models import User
from app.modules.accounts.schemas import ChangePasswordRequest

router = APIRouter(tags=["M1 - Tài khoản"])

MSG_CHANGED = "Đổi mật khẩu thành công"
MSG_CREATED = "Tạo mật khẩu thành công"
MSG_CURRENT_REQUIRED = "Vui lòng nhập mật khẩu hiện tại"
# Trả 400 chứ không phải 401: api.js coi 401 là hết phiên và tự đăng xuất.
MSG_CURRENT_WRONG = "Mật khẩu hiện tại không đúng"
MSG_SAME_PASSWORD = "Mật khẩu mới phải khác mật khẩu hiện tại"


@router.post("/api/auth/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    had_password = bool(current_user.password_hash)

    if had_password:
        if not payload.current_password:
            raise BadRequestException(MSG_CURRENT_REQUIRED)
        if not verify_password(payload.current_password, current_user.password_hash):
            raise BadRequestException(MSG_CURRENT_WRONG)
        if verify_password(payload.new_password, current_user.password_hash):
            raise BadRequestException(MSG_SAME_PASSWORD)

    try:
        current_user.password_hash = hash_password(payload.new_password)
        current_user.token_version = (current_user.token_version or 0) + 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(current_user)

    response = build_response(
        200,
        MSG_CHANGED if had_password else MSG_CREATED,
        request,
        data=service.issue_token(current_user),
    )
    response.headers["Cache-Control"] = "no-store"
    return response
