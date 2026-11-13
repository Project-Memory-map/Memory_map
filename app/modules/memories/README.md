# app/modules/memories/ – M2 Ký ức, chuyến đi, bản đồ

Tạo/xem/sửa/xóa ký ức, ảnh/video, riêng tư/công khai, hashtag, chuyến đi (US-MEM-001 → 010, US-EXP-005).

| File | Công dụng |
|---|---|
| `router.py` | API của module. Hiện **chưa có endpoint**: đầu file có bảng các API cần làm, kèm mã task và file JS nào đang gọi |
| `create_router.py` | US-MEM-002: `GET /api/geocode/reverse` (tọa độ → tên địa điểm) và `POST /api/memories` (tạo ký ức tại vị trí đã chọn) |
| `services/reverse_geocode_service.py` | Gọi Nominatim `/reverse` có User-Agent và cache kết quả trong bộ nhớ (BR-19) |
| `models.py` | Model ORM của 6 bảng: `Memory`, `Media`, `Trip`, `TripMemory`, `Hashtag`, `MemoryHashtag` |
| `__init__.py` | Đánh dấu package (để trống) |

| Thư mục | Công dụng |
|---|---|
| [`ui/`](ui/README.md) | CSS của panel "Của tôi", "Chuyến đi" và form ký ức |
| [`js/`](js/README.md) | Xử lý phía trình duyệt: ký ức, chuyến đi |

HTML của panel và form ký ức nằm trong `app/shared/ui/map.html`.

> Khi cần thêm `schemas.py`, `service.py`... thì tạo trong thư mục này và bổ sung vào bảng trên.

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
