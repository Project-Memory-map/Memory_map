# app/modules/explore/ – M3 Khám phá, tìm kiếm

Bản đồ ký ức công khai (ghim đỏ), lọc theo hashtag, khu vực (34 tỉnh/thành), tìm theo từ khóa (US-EXP-001 → 004).

| File | Công dụng |
|---|---|
| `router.py` | `GET /api/explore/pins` (ghim trong vùng bản đồ đang xem, tối đa 500), `GET /api/explore/memories` (danh sách có phân trang), `GET /api/explore/overview` (số ký ức công khai, số tỉnh/thành). Lọc chung: `q` (FULLTEXT, không phân biệt dấu và hoa thường, ≥ 2 ký tự), `hashtags` (phép OR – BR-16), `region` (id hoặc slug), vùng bản đồ |
| `region_router.py` | US-EXP-003: `GET /api/explore/regions` (34 tỉnh/thành kèm số ký ức công khai) |
| `hashtag_router.py` | US-EXP-002: `GET /api/explore/hashtags` (hashtag phổ biến trong ký ức công khai) |
| `region_lookup.py` | Xác định tỉnh/thành của một tọa độ bằng ranh giới GeoJSON (`province_slug`, `region_id_for`). Dùng khi tạo/sửa ký ức. Ghim sát bờ biển được gán tỉnh gần nhất trong ~5 km; ngoài Việt Nam thì không gắn khu vực |
| `data/provinces.geojson` | Ranh giới 34 tỉnh/thành sau sắp xếp 2025 (đã rút gọn, ~200 KB). Nguồn: [ThangLeQuoc/vietnamese-provinces-database](https://github.com/ThangLeQuoc/vietnamese-provinces-database) (giấy phép MIT), dựng lại bằng `scripts/tao_ranh_gioi_tinh.py` |
| `models.py` | Model ORM bảng `Region` (regions, 34 tỉnh/thành nạp từ `database/seed_regions.sql`) |
| `repository.py`, `service.py`, `schemas.py` | Để trống, dành cho khi tách logic truy vấn khỏi `router.py` |
| `__init__.py` | Đánh dấu package (để trống) |

| Thư mục | Công dụng |
|---|---|
| [`ui/`](ui/README.md) | CSS panel "Khám phá" |
| [`js/`](js/README.md) | Xử lý phía trình duyệt của panel "Khám phá" |

HTML của panel "Khám phá" nằm trong `app/shared/ui/map.html`.

Mọi truy vấn công khai đi qua `public_query()` trong `router.py`, đủ 4 điều kiện BR-03: công khai, không bị ẩn, chưa xóa, tác giả không bị khóa. Kết quả chỉ có tên hiển thị của tác giả, không có email (BR-12).

Test: `tests/test_us_exp_*.py`, `tests/memories/test_region_assignment_and_media.py`.

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
