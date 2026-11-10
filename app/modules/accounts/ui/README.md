# app/modules/accounts/ui/

Giao diện module tài khoản (HTML + CSS), phục vụ ở `/accounts/...`.

| File | Công dụng |
|---|---|
| `login.html` | Trang đăng nhập `/accounts/login.html` (email + mật khẩu, nút Google/Facebook) |
| `register.html` | Trang đăng ký `/accounts/register.html` |
| `forgot-password.html` | Trang quên mật khẩu: nhập email để nhận liên kết đặt lại |
| `reset-password.html` | Trang đặt lại mật khẩu (mở từ liên kết trong email, có `?token=`) |
| `profile.html` | Trang hồ sơ cá nhân: thông tin, ảnh đại diện, đổi mật khẩu, thống kê, ký ức và chuyến đi của tôi |
| `oauth-callback.html` | Trang trung gian sau khi đăng nhập Google/Facebook (hiện "Đang đăng nhập...") |
| `accounts.css` | CSS các trang tài khoản + menu tài khoản góc trên (dùng cả ở trang bản đồ và trang quản trị) |

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
