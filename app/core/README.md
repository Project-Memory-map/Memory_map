# app/core/

Phần lõi dùng chung cho cả 4 module. Sửa thư mục này cần báo cả nhóm (cần 2 người duyệt PR).

| File | Công dụng |
|---|---|
| `config.py` | Đọc cấu hình từ file `.env` vào `settings`: MySQL, JWT, khóa ký URL ảnh/video, thư mục upload, Nominatim, Gemini, Google/Facebook OAuth, SMTP, `APP_BASE_URL`. Thêm cấu hình mới thì thêm biến vào class `Settings` **và** vào `.env.example` |
| `database.py` | Kết nối MySQL bằng SQLAlchemy: `engine`, `SessionLocal`, `Base` (lớp cha của model), `get_db()` (dùng với `Depends`), `check_database()` |
| `security.py` | Tạo/đọc JWT (`create_access_token`, `decode_access_token`; kèm `token_version` để thu hồi phiên, BR-20) và ký/kiểm tra URL ảnh có hạn dùng (`sign_media_url`, `verify_media_signature`, BR-17) |
| `passwords.py` | Băm và kiểm tra mật khẩu bằng bcrypt (`hash_password`, `verify_password`, BR-07) |
| `response.py` | `build_response()`: khung phản hồi chung `{statusCode, message, error, data, path, timestamp}` mà JS phía trình duyệt đang đọc |
| `errors.py` | Các lớp lỗi (`ValidationException`, `NotFoundException`, `ForbiddenException`, `ConflictException`, `ServiceUnavailableException`...) và bộ xử lý lỗi. Lỗi kiểm tra dữ liệu (Pydantic) trả 422 kèm câu thông báo tiếng Việt; lỗi do trigger MySQL chặn (mã 1644) trả 422 kèm câu thông báo của trigger |
| `deps.py` | Để trống, dành cho dependency dùng chung sau này (vd phân trang). Lấy người dùng đang đăng nhập dùng `app/modules/accounts/deps.py` |
| `storage.py` | Để trống. Lưu/đọc tệp ảnh, video, ảnh đại diện hiện nằm ở `app/modules/memories/services/image_media_service.py` và `video_media_service.py` |
| `__init__.py` | Đánh dấu package (để trống) |

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
