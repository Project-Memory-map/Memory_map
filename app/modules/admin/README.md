# app/modules/admin/ – M4 Quản trị

Ẩn/bỏ ẩn/xóa ký ức vi phạm, khóa/mở khóa tài khoản, nhật ký thao tác, thống kê (US-ADM-001 → 003).

| File | Công dụng |
|---|---|
| `router.py` | Toàn bộ API quản trị (prefix `/api/admin`), mọi route qua `get_current_admin` (đăng nhập + `role = 'admin'`, người dùng thường nhận 403 "Bạn không có quyền truy cập"). Docstring đầu file có bảng API |
| `models.py` | Model ORM bảng `AdminAction` (admin_actions – nhật ký quản trị, không sửa/xóa được) |
| `__init__.py` | Đánh dấu package (để trống) |

| Task | API | Ghi chú |
|---|---|---|
| US-ADM-001 | `GET /stats` | Số tài khoản, tài khoản bị khóa, ký ức, ký ức công khai, bị ẩn, mới trong 7 ngày |
| US-ADM-001 | `GET /memories?q=&status=` | Ký ức công khai chưa xóa; tìm theo tiêu đề, địa điểm, tên tác giả; lọc đang hiển thị/đã ẩn |
| US-ADM-001 | `POST /memories/{id}/hide` · `/unhide` | Ẩn bắt buộc lý do (BR-10); chủ ký ức vẫn thấy kèm trạng thái "Đã bị quản trị viên ẩn" |
| US-ADM-002 | `POST /memories/{id}/delete` | Xóa mềm, bắt buộc lý do; ký ức đã bị chủ xóa → "Ký ức không tồn tại" |
| US-ADM-003 | `GET /users?q=&status=` | Tìm theo email hoặc tên hiển thị, kèm trạng thái và số ký ức |
| US-ADM-003 | `POST /users/{id}/lock` · `/unlock` | Khóa bắt buộc lý do, không tự khóa mình (BR-11); khóa thì đăng xuất ngay và ẩn ký ức công khai của người đó khỏi cộng đồng |
| US-ADM-001→003 | `GET /actions?action=` | Nhật ký: người thao tác, thời điểm, đối tượng, lý do |

| Thư mục | Công dụng |
|---|---|
| [`ui/`](ui/README.md) | Giao diện trang quản trị `/admin/` |
| [`js/`](js/README.md) | Xử lý phía trình duyệt của trang quản trị (người dùng thường mở trang sẽ được đưa về bản đồ kèm thông báo "Bạn không có quyền truy cập") |

Trigger trong MySQL chặn thêm một lớp: thao tác ẩn/xóa/khóa thiếu lý do, admin tự khóa mình, sửa/xóa nhật ký.

Tạo tài khoản quản trị: chạy `scripts/seed_demo.py` (có sẵn `admin@example.com`), hoặc đổi `users.role = 'admin'` trong database.

Test: `tests/admin/`.

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
