# app/modules/accounts/ – M1 Tài khoản và người dùng

Đăng ký, đăng nhập (email, Google, Facebook), quên/đặt lại mật khẩu, hồ sơ cá nhân, đổi mật khẩu, đăng xuất (US-ACC-001 → 008).

| File | Công dụng |
|---|---|
| `router.py` | US-ACC-001: `POST /api/auth/register`. Docstring đầu file có bảng toàn bộ API của module |
| `login_router.py` | US-ACC-002: `POST /api/auth/login` (khóa tạm 15 phút sau 5 lần sai trong 15 phút, chặn tài khoản bị khóa), `GET /api/auth/me` |
| `google_router.py` | US-ACC-003: `GET /api/auth/google/login` → Google → `/api/auth/google/callback`. Tạo tài khoản mới hoặc liên kết vào tài khoản cùng email (chỉ khi Google xác nhận email), chặn tài khoản bị khóa |
| `facebook_router.py` | US-ACC-004: `GET /api/auth/facebook/login` + `/callback`; `GET /api/auth/providers` (Google/Facebook đã cấu hình đủ khóa chưa) |
| `password_reset_router.py` | US-ACC-005: `POST /api/auth/forgot-password`, `/validate-reset-token`, `/reset-password`. Token lưu dạng SHA-256, hạn 30 phút, dùng một lần; cùng một thông báo cho email có/không tồn tại. Chưa cấu hình SMTP ở `APP_ENV=dev` thì trả `dev_reset_url` để thử |
| `users_router.py` | US-ACC-006: `PATCH /api/users/me` (tên ≤ 100 ký tự, email, giới thiệu), `POST`/`DELETE /api/users/me/avatar` (≤ 5 MB, chỉ ảnh, xóa EXIF/GPS), `GET /api/users/{id}/avatar`, `GET /api/users/me/stats` |
| `password_router.py` | US-ACC-007: `POST /api/auth/change-password`: đổi mật khẩu, hoặc tạo mật khẩu cho tài khoản chỉ đăng nhập mạng xã hội |
| `logout_router.py` | US-ACC-008: `POST /api/auth/logout` (đăng xuất phía trình duyệt, BR-20) |
| `service.py` | Logic dùng chung: tìm người dùng theo email (không phân biệt hoa thường), đăng ký, cấp JWT, `to_user_response()` |
| `schemas.py` | Kiểu dữ liệu vào/ra (Pydantic) + kiểm tra dùng chung: `normalize_email()`, `check_password_strength()` (≥ 8 ký tự gồm chữ và số) |
| `deps.py` | `get_current_user` / `get_current_user_optional`: lấy người dùng từ JWT, chặn token cũ (`token_version`) và tài khoản bị khóa. **Các module khác dùng** |
| `avatar.py` | `avatar_url(user)`: link công khai của ảnh đại diện (`/api/users/{id}/avatar?v=...`). Mọi API trả thông tin người dùng/tác giả dùng hàm này, không trả `avatar_path` |
| `services/google_auth.py` | Gọi Google OAuth 2.0 (đổi mã lấy token, đọc hồ sơ) |
| `services/facebook_auth.py` | Gọi Facebook Graph API (đổi mã lấy token, đọc hồ sơ) |
| `models.py` | Model ORM của 3 bảng: `User` (users), `OAuthAccount` (oauth_accounts), `PasswordResetToken` (password_reset_tokens) |
| `__init__.py` | Đánh dấu package (để trống) |

| Thư mục | Công dụng |
|---|---|
| [`ui/`](ui/README.md) | Giao diện: 6 trang tài khoản + CSS |
| [`js/`](js/README.md) | Xử lý phía trình duyệt của các trang tài khoản |

Cấu hình liên quan trong `.env`: `JWT_SECRET`, `ACCESS_TOKEN_MINUTES`, `GOOGLE_*`, `FACEBOOK_*`, `SMTP_*`, `APP_BASE_URL` (xem `.env.example`).

Test: `tests/accounts/` (đăng ký, đăng nhập, Google, Facebook, quên mật khẩu, hồ sơ, đổi mật khẩu, đăng xuất).

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
