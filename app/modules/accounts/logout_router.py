"""US-ACC-008 – Đăng xuất khỏi hệ thống (T05B576)."""
from fastapi import APIRouter, Depends, Request

from app.core.response import build_response
from app.modules.accounts.deps import get_current_user
from app.modules.accounts.models import User

router = APIRouter(tags=["M1 - Tài khoản"])


@router.post("/api/auth/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Kết thúc phiên trên trình duyệt (BR-20: không tăng token_version khi đăng xuất)."""
    response = build_response(200, "Đăng xuất thành công", request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response
