# app/

Toàn bộ mã nguồn của ứng dụng (FastAPI + giao diện).

| File | Công dụng |
|---|---|
| `main.py` | Khởi tạo FastAPI: gắn API của 4 module, phục vụ giao diện (`ui/`) và JS (`js/`), trang `/ban-do`, API kiểm tra `/api/health`. API chưa làm sẽ trả "Chức năng này chưa được xây dựng" |
| `models.py` | Gom model ORM của 4 module (11 bảng) để SQLAlchemy nạp đủ quan hệ khi khởi động |
| `__init__.py` | Đánh dấu `app` là package Python (để trống) |

| Thư mục | Công dụng |
|---|---|
| [`core/`](core/README.md) | Phần lõi dùng chung: cấu hình, kết nối MySQL, khung phản hồi, xử lý lỗi |
| [`shared/`](shared/README.md) | Giao diện và JS dùng chung: trang mở đầu, trang chủ bản đồ, CSS chung, tiện ích JS |
| [`modules/`](modules/README.md) | 4 module chức năng, mỗi module chứa trọn API + giao diện + JS của mình |

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
