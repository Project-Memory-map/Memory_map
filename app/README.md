# app/

Toàn bộ mã nguồn của ứng dụng (FastAPI + giao diện).

| File | Công dụng |
|---|---|
| `main.py` | Khởi tạo FastAPI: gắn router của 4 module, phục vụ giao diện (`ui/`) và JS (`js/`), trang `/ban-do`, API kiểm tra `/api/health`, thêm header bảo mật. Đường dẫn `/api/...` không có router nào xử lý thì trả "Chức năng này chưa được xây dựng" |
| `models.py` | Gom model ORM của 4 module (11 bảng) để SQLAlchemy nạp đủ quan hệ khi khởi động (`register_models()`) |
| `__init__.py` | Đánh dấu `app` là package Python (để trống) |

| Thư mục | Công dụng |
|---|---|
| [`core/`](core/README.md) | Phần lõi dùng chung: cấu hình, kết nối MySQL, JWT, mật khẩu, khung phản hồi, xử lý lỗi |
| [`shared/`](shared/README.md) | Giao diện và JS dùng chung: trang mở đầu, trang chủ bản đồ, CSS chung, tiện ích JS |
| [`modules/`](modules/README.md) | 4 module chức năng, mỗi module chứa trọn API + giao diện + JS của mình |

**Thứ tự gắn router trong `main.py` có ý nghĩa:** nếu hai router cùng khai báo một đường dẫn thì router gắn trước chạy, router sau bị che. Vì vậy mỗi đường dẫn API chỉ được khai báo ở một file.

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
