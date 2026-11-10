# app/core/

Phần lõi dùng chung cho cả 4 module. Sửa thư mục này cần báo cả nhóm (cần 2 người duyệt PR).

| File | Công dụng |
|---|---|
| `config.py` | Đọc cấu hình từ file `.env` (thông tin MySQL, CORS). Chức năng cần thêm cấu hình (JWT, SMTP, OAuth, Gemini...) thì thêm biến vào class `Settings` và vào `.env.example` |
| `database.py` | Kết nối MySQL bằng SQLAlchemy: `engine`, `Base` (lớp cha của model), `get_db()` (dùng với `Depends`), `check_database()` |
| `response.py` | `build_response()`: khung phản hồi chung `{statusCode, message, error, data, path, timestamp}` mà JS phía trình duyệt đang đọc |
| `errors.py` | Các lớp lỗi (`ValidationException`, `NotFoundException`, `ForbiddenException`...) và bộ xử lý lỗi. Lỗi do trigger MySQL chặn (mã 1644) tự trả về 422 kèm câu thông báo của trigger |
| `deps.py` | ⚠️ *Chưa có nội dung* – dependency dùng chung (vd. phân trang). Ai cần thì bổ sung |
| `security.py` | ⚠️ *Chưa có nội dung* – băm mật khẩu (bcrypt), tạo/kiểm tra JWT, ký URL ảnh/video (BR-17, BR-20). Thành viên làm đăng nhập (US-ACC-002) và ảnh/video (US-MEM-003) bổ sung |
| `storage.py` | ⚠️ *Chưa có nội dung* – lưu tệp ảnh/video vào thư mục `uploads/`. Thành viên làm US-MEM-003/004 bổ sung |
| `__init__.py` | Đánh dấu package (để trống) |

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
