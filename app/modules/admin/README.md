# app/modules/admin/ – M4 Quản trị

Ẩn/bỏ ẩn/xóa ký ức vi phạm, khóa/mở khóa tài khoản, nhật ký thao tác (US-ADM-001 → 003).

| File | Công dụng |
|---|---|
| `router.py` | API của module. Hiện **chưa có endpoint**: đầu file có bảng các API cần làm, kèm mã task và file JS nào đang gọi. Mọi route phải kiểm tra role = admin |
| `models.py` | Model ORM bảng `AdminAction` (admin_actions – nhật ký quản trị) |
| `__init__.py` | Đánh dấu package (để trống) |

| Thư mục | Công dụng |
|---|---|
| [`ui/`](ui/README.md) | Giao diện trang quản trị |
| [`js/`](js/README.md) | Xử lý phía trình duyệt của trang quản trị |

> Khi cần thêm `schemas.py`, `service.py`... thì tạo trong thư mục này và bổ sung vào bảng trên.

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
