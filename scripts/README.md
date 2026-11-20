# scripts/

Các script chạy tay bằng dòng lệnh, từ thư mục gốc dự án (đã kích hoạt `.venv`). Thông tin MySQL lấy từ `.env`.

| File | Công dụng | Lệnh |
|---|---|---|
| `init_db.py` | Tạo database từ `database/schema.sql` + `seed_regions.sql` (bảng, 11 trigger, view, 34 tỉnh/thành), thay cho chạy tay trong Workbench. Hiểu cú pháp `DELIMITER` của trigger. Chạy lại an toàn, không mất dữ liệu | `python scripts/init_db.py` · thêm `--xoa-cu` để xóa và tạo lại từ đầu (**mất dữ liệu**) · `--ten <tên>` để tạo database tên khác |
| `seed_demo.py` | Dữ liệu mẫu để thử giao diện / demo: 1 quản trị viên, 2 người dùng, 10 ký ức ở nhiều tỉnh (có hashtag, công khai/riêng tư), 1 chuyến đi. Đã có thì bỏ qua | `python scripts/seed_demo.py` |
| `gan_khu_vuc.py` | Gán tỉnh/thành (`memories.region_id`) theo tọa độ cho ký ức tạo trước khi có tính năng gán khu vực. Giữ nguyên `updated_at`. **Chạy một lần trên database cũ sau khi cập nhật code** | `python scripts/gan_khu_vuc.py` · thêm `--tat-ca` để tính lại cho mọi ký ức |
| `tao_ranh_gioi_tinh.py` | Dựng lại `app/modules/explore/data/provinces.geojson` từ dữ liệu ranh giới gốc (34 file `province.geojson` của [ThangLeQuoc/vietnamese-provinces-database](https://github.com/ThangLeQuoc/vietnamese-provinces-database), giấy phép MIT), rút gọn còn ~200 KB. Chỉ cần khi nguồn dữ liệu cập nhật | `python scripts/tao_ranh_gioi_tinh.py <thư-mục-chứa-34-file>` |

Tài khoản mẫu của `seed_demo.py` (chỉ dùng ở máy phát triển):

| Vai trò | Email | Mật khẩu |
|---|---|---|
| Quản trị | `admin@example.com` | `Admin12345` |
| Người dùng | `an@example.com` | `Matkhau123` |
| Người dùng | `binh@example.com` | `Matkhau123` |

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
