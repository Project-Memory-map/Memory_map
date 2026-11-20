# app/modules/

4 module chức năng. Mỗi module chứa trọn phần của mình: API (`*.py`), giao diện (`ui/`, phục vụ ở `/<module>/...`) và xử lý phía trình duyệt (`js/`, phục vụ ở `/<module>/js/...`).

| Module | Thư mục | User story | Nội dung |
|---|---|---|---|
| M1 Tài khoản | [`accounts/`](accounts/README.md) | US-ACC-001 → 008 | Đăng ký, đăng nhập (email, Google, Facebook), quên/đặt lại mật khẩu, hồ sơ, đổi mật khẩu, đăng xuất |
| M2 Ký ức, chuyến đi | [`memories/`](memories/README.md) | US-MEM-001 → 010, US-EXP-005 | Tạo/xem/sửa/xóa ký ức, tìm địa điểm, ảnh/video, riêng tư/công khai, hashtag (có gợi ý AI), chuyến đi, lọc ký ức của tôi theo thời gian |
| M3 Khám phá | [`explore/`](explore/README.md) | US-EXP-001 → 004 | Bản đồ ký ức công khai, lọc theo hashtag và tỉnh/thành, tìm theo từ khóa |
| M4 Quản trị | [`admin/`](admin/README.md) | US-ADM-001 → 003 | Ẩn/bỏ ẩn/xóa ký ức vi phạm, khóa/mở khóa tài khoản, nhật ký thao tác, thống kê |

| File | Công dụng |
|---|---|
| `__init__.py` | Đánh dấu package (để trống) |

Quy ước chung:
- Mỗi chức năng một file router (`<chuc_nang>_router.py`), gắn vào `app/main.py`. Docstring đầu file ghi mã user story.
- Gọi dịch vụ bên ngoài (Google, Facebook, Nominatim, Gemini) đặt trong `services/` của module, có timeout và báo lỗi tiếng Việt.
- Module dùng model của module khác thì import trực tiếp (vd explore đọc `Memory` của memories), không sao chép.

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
