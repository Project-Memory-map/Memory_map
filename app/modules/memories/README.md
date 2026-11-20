# app/modules/memories/ – M2 Ký ức, chuyến đi, bản đồ

Tạo/xem/sửa/xóa ký ức, tìm địa điểm, ảnh/video, riêng tư/công khai, hashtag, chuyến đi, lọc ký ức của tôi (US-MEM-001 → 010, US-EXP-005).

| File | Công dụng |
|---|---|
| `create_router.py` | US-MEM-001/002: `GET /api/geocode?q=` (tìm địa điểm theo tên), `GET /api/geocode/reverse` (tọa độ → tên), `POST /api/memories` (tạo ký ức, mặc định riêng tư, tự gán tỉnh/thành theo tọa độ) |
| `router.py` | `serialize_memory()` dùng chung (link ảnh/video có chữ ký). US-EXP-005: `GET /api/memories/mine`, `/mine/pins`, `/mine/years` (lọc theo năm, tháng, khoảng ngày). US-MEM-005/006/007: `GET`, `PATCH`, `DELETE /api/memories/{id}` (đổi tọa độ thì đổi luôn khu vực; xóa mềm) |
| `images_router.py` | US-MEM-003: `GET`/`POST /api/memories/{id}/images` (tối đa 10 ảnh, mỗi ảnh ≤ 5 MB, thêm/bỏ/sắp xếp), `GET /api/media/{id}` (ảnh qua link có chữ ký) |
| `video_router.py` | US-MEM-004: `GET`/`POST /api/memories/{id}/video` (1 video .mp4/.mov ≤ 50 MB), `GET /api/media/{id}/stream` (phát video, hỗ trợ Range) |
| `privacy_router.py` | US-MEM-008: `PATCH /api/memories/{id}/visibility` (riêng tư ↔ công khai) |
| `trips_router.py` | US-MEM-009: CRUD `/api/trips`, thêm/bỏ ký ức trong chuyến đi (chỉ ký ức của mình, sắp theo ngày rồi thời điểm tạo) |
| `hashtags_router.py` | US-MEM-010 + FR-3.6: gắn/sửa/xóa hashtag của ký ức, `GET /api/hashtags`, `POST /api/memories/suggest-hashtags` (gợi ý bằng Gemini, không có khóa thì gợi ý theo từ khóa) |
| `hashtag_service.py` | Chuẩn hóa hashtag (bỏ `#`, chữ thường, chỉ chữ/số/`_`, ≤ 30 ký tự, ≤ 10/ký ức – BR-06) và gợi ý hashtag |
| `services/place_search_service.py` | Gọi Nominatim `/search` cho ô tìm địa điểm: cache 24 giờ, chuẩn hóa kết quả `{name, display_name, latitude, longitude}` |
| `services/reverse_geocode_service.py` | Gọi Nominatim `/reverse` khi chọn vị trí trên bản đồ, cache theo tọa độ |
| `services/nominatim_gate.py` | BR-19: tối đa 1 yêu cầu/giây tới Nominatim cho toàn hệ thống (yêu cầu sau chờ tới lượt) |
| `services/image_media_service.py` | Kiểm định dạng ảnh bằng chữ ký tệp, giới hạn dung lượng, lưu vào `uploads/images/`, đường dẫn an toàn |
| `services/image_metadata.py` | Xóa EXIF/GPS/XMP khỏi ảnh JPEG, PNG, WebP trước khi lưu (không nén lại ảnh) |
| `services/video_media_service.py` | Kiểm định dạng/dung lượng video, lưu vào `uploads/videos/`, ký link phát video |
| `models.py` | Model ORM của 6 bảng: `Memory`, `Media`, `Trip`, `TripMemory`, `Hashtag`, `MemoryHashtag` |
| `__init__.py` | Đánh dấu package (để trống) |

| Thư mục | Công dụng |
|---|---|
| [`ui/`](ui/README.md) | CSS của panel "Của tôi", "Chuyến đi" và form ký ức |
| [`js/`](js/README.md) | Xử lý phía trình duyệt: ký ức, chuyến đi |

HTML của panel và form ký ức nằm trong `app/shared/ui/map.html`.

Quy tắc quyền xem ký ức (BR-03): người khác chỉ thấy ký ức **công khai**, **không bị ẩn**, **chưa xóa** và chủ ký ức **không bị khóa**; chủ ký ức luôn thấy ký ức của mình (kèm trạng thái "Đã bị quản trị viên ẩn").

Test: `tests/memories/` và `tests/test_us_mem_*.py`.

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
