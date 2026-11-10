# app/modules/accounts/ – M1 Tài khoản và người dùng

Đăng ký, đăng nhập (email, Google, Facebook), quên/đặt lại mật khẩu, hồ sơ cá nhân, đổi mật khẩu, đăng xuất (US-ACC-001 → 008).

| File | Công dụng |
|---|---|
| `router.py` | API của module. Hiện **chưa có endpoint**: đầu file có bảng các API cần làm, kèm mã task và file JS nào đang gọi |
| `models.py` | Model ORM của 3 bảng: `User` (users), `OAuthAccount` (oauth_accounts), `PasswordResetToken` (password_reset_tokens) |
| `schemas.py` | ⚠️ *Chưa có nội dung* – kiểu dữ liệu vào/ra (Pydantic) cho đăng ký, đăng nhập, hồ sơ... |
| `deps.py` | ⚠️ *Chưa có nội dung* – `get_current_user`, `get_optional_user`, `require_admin` (lấy người dùng từ JWT). Làm cùng US-ACC-002; **các module khác cần dùng** |
| `__init__.py` | Đánh dấu package (để trống) |

| Thư mục | Công dụng |
|---|---|
| [`ui/`](ui/README.md) | Giao diện: 6 trang tài khoản + CSS |
| [`js/`](js/README.md) | Xử lý phía trình duyệt của các trang tài khoản |

Nên làm `POST /api/auth/login` và `GET /api/auth/me` trước, vì các module khác cần đăng nhập mới thử được.

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
