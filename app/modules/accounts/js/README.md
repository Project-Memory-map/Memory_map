# app/modules/accounts/js/

Xử lý phía trình duyệt của module tài khoản, phục vụ ở `/accounts/js/...`.

| File | Công dụng |
|---|---|
| `accounts.js` | Xử lý chung cho mọi form tài khoản: form có `data-endpoint` sẽ gửi tới API đó, hiện lỗi/thành công, chuyển trang. Dùng ở login, register, forgot/reset-password |
| `account-menu.js` | `AccountMenu`: menu góc trên. Khách thấy Đăng nhập/Đăng ký, người dùng thấy ảnh, tên, Hồ sơ, Quản trị, Đăng xuất. Gọi `GET /api/auth/me` |
| `profile.js` | Trang hồ sơ: sửa thông tin, ảnh đại diện, đổi mật khẩu, ký ức + chuyến đi lọc theo thời gian |
| `oauth-callback.js` | Nhận JWT trả về sau đăng nhập Google/Facebook rồi chuyển vào bản đồ |

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
