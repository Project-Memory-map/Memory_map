"""M1 – Tài khoản và người dùng.

File này chứa API đăng ký; các API khác của module nằm ở file router riêng (cột "File"), gắn trong app/main.py.

| Task        | Phương thức + đường dẫn                              | File                        | Gọi từ                         |
|-------------|------------------------------------------------------|-----------------------------|--------------------------------|
| US-ACC-001  | POST  /api/auth/register                             | router.py                   | js/accounts.js (register.html) |
| US-ACC-002  | POST  /api/auth/login · GET /api/auth/me             | login_router.py             | js/accounts.js, account-menu.js|
| US-ACC-003  | GET   /api/auth/google/login + /callback             | google_router.py            | login.html, register.html      |
| US-ACC-004  | GET   /api/auth/facebook/login + /callback           | facebook_router.py          | login.html, register.html      |
| US-ACC-003/4| GET   /api/auth/providers                            | facebook_router.py          | js/accounts.js                 |
| US-ACC-005  | POST  /api/auth/forgot-password · /validate-reset-token · /reset-password | password_reset_router.py | forgot/reset-password.html |
| US-ACC-006  | PATCH /api/users/me · POST/DELETE /api/users/me/avatar · GET /api/users/me/stats | users_router.py | js/profile.js |
| US-ACC-007  | POST  /api/auth/change-password                      | password_router.py          | js/profile.js                  |
| US-ACC-008  | POST  /api/auth/logout                               | logout_router.py            | js/account-menu.js             |

Bảng dùng: users, oauth_accounts, password_reset_tokens (models.py).
Mọi API trả về qua core/response.py build_response(), báo lỗi bằng lớp trong core/errors.py.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import build_response
from app.modules.accounts import service
from app.modules.accounts.schemas import RegisterRequest

router = APIRouter(tags=["M1 - Tài khoản"])

# ----- US-ACC-001: Đăng ký bằng email

@router.post("/api/auth/register", status_code=201)
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    data = service.register(db, payload)
    return build_response(201, service.MSG_REGISTER_OK, request, data=data)

