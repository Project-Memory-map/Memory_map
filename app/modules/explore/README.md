# app/modules/explore/ – M3 Khám phá, tìm kiếm

Bản đồ ký ức công khai (ghim đỏ), lọc theo hashtag, khu vực (34 tỉnh/thành), tìm theo từ khóa (US-EXP-001 → 004).

| File | Công dụng |
|---|---|
| `router.py` | API của module. Hiện **chưa có endpoint**: đầu file có bảng các API cần làm, kèm mã task và file JS nào đang gọi |
| `models.py` | Model ORM bảng `Region` (regions, 34 tỉnh/thành nạp từ `database/seed_regions.sql`) |
| `repository.py` | ⚠️ *Chưa có nội dung* – các câu truy vấn đọc ký ức công khai (nên dùng view `v_public_memories`) |
| `service.py` | ⚠️ *Chưa có nội dung* – xử lý nghiệp vụ lọc/tìm kiếm, gọi repository |
| `schemas.py` | ⚠️ *Chưa có nội dung* – kiểu dữ liệu vào/ra (Pydantic) cho ghim, danh sách ký ức, khu vực |
| `__init__.py` | Đánh dấu package (để trống) |

| Thư mục | Công dụng |
|---|---|
| [`ui/`](ui/README.md) | CSS panel "Khám phá" |
| [`js/`](js/README.md) | Xử lý phía trình duyệt của panel "Khám phá" |

HTML của panel "Khám phá" nằm trong `app/shared/ui/map.html`.

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
