"""M1 – Tài khoản và người dùng.

Giao diện đã có sẵn (ui/ + js/). Các API dưới đây là việc cần làm, js/ đang gọi đúng các
đường dẫn này. Chưa làm thì giao diện báo "Chức năng này chưa được xây dựng".

| Task        | Phương thức + đường dẫn                         | Gọi từ                          |
|-------------|-------------------------------------------------|---------------------------------|
| US-ACC-001  | POST  /api/auth/register                        | js/accounts.js (register.html)  |
| US-ACC-002  | POST  /api/auth/login                           | js/accounts.js (login.html)     |
| US-ACC-002  | GET   /api/auth/me                              | js/account-menu.js (mọi trang)  |
| US-ACC-003  | GET   /api/auth/google/login  + /callback       | login.html, register.html       |
| US-ACC-004  | GET   /api/auth/facebook/login + /callback      | login.html, register.html       |
| US-ACC-003/4| GET   /api/auth/providers                       | js/accounts.js                  |
| US-ACC-005  | POST  /api/auth/forgot-password                 | forgot-password.html            |
| US-ACC-005  | POST  /api/auth/reset-password                  | reset-password.html             |
| US-ACC-006  | PATCH /api/users/me                             | js/profile.js                   |
| US-ACC-006  | POST / DELETE /api/users/me/avatar              | js/profile.js                   |
| US-ACC-006  | GET   /api/users/me/stats                       | js/profile.js                   |
| US-ACC-007  | POST  /api/auth/change-password                 | js/profile.js                   |
| US-ACC-008  | POST  /api/auth/logout                          | js/account-menu.js              |

Bảng dùng: users, oauth_accounts, password_reset_tokens (models.py).
Mọi API trả về qua core/response.py build_response(), báo lỗi bằng lớp trong core/errors.py.
"""
from fastapi import APIRouter

router = APIRouter(tags=["M1 - Tài khoản"])

# TODO: thêm các endpoint theo bảng trên
