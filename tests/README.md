# tests/

Hai loại kiểm thử:

| Loại | Ở đâu | Chạy trên | Lệnh |
|---|---|---|---|
| **Test tự động** (238 test) | Các file `test_*.py` trong thư mục này | SQLite trong bộ nhớ, không cần MySQL; dịch vụ ngoài (Google, Facebook, Nominatim, Gemini) được giả lập | `python -m pytest -q` |
| **Kiểm thử tích hợp 108 AC** | [`kiem_thu_tich_hop/`](kiem_thu_tich_hop/README.md) | Máy chủ thật + MySQL thật (có trigger) + trình duyệt Edge (máy tính và điện thoại) | Xem README trong thư mục |

Test tự động chạy nhanh, nên chạy trước mỗi lần commit. Kiểm thử tích hợp bắt được các lỗi mà SQLite không có: trigger MySQL, FULLTEXT, lệch múi giờ giữa MySQL và Python, hiển thị trên trình duyệt.

## Test tự động

| File | Kiểm |
|---|---|
| `conftest.py` | Cấu hình chung: database SQLite trong bộ nhớ cho mỗi test, `client` (TestClient), bỏ thời gian chờ 1 giây của Nominatim |
| `accounts/test_register.py` | US-ACC-001 – Đăng ký bằng email |
| `accounts/test_login.py` | US-ACC-002 – Đăng nhập, khóa tạm sau 5 lần sai |
| `accounts/test_us_acc_003_google.py` | US-ACC-003 – Đăng nhập Google (tạo mới, liên kết email đã xác thực, từ chối, tài khoản bị khóa) |
| `accounts/test_us_acc_004_facebook.py` | US-ACC-004 – Đăng nhập Facebook |
| `accounts/test_us_acc_005_reset_password.py` | US-ACC-005 – Quên mật khẩu, đặt lại, link hết hạn, dùng lại link |
| `accounts/test_us_acc_006_profile.py` | US-ACC-006 – Hồ sơ: tên 100/101 ký tự, ảnh 6 MB, tệp PDF, xóa GPS ảnh đại diện, thống kê |
| `accounts/test_us_acc_007_change_password.py` | US-ACC-007 – Đổi/tạo mật khẩu |
| `accounts/test_us_acc_008_logout.py` | US-ACC-008 – Đăng xuất |
| `memories/test_us_mem_001_geocode_search.py` | US-MEM-001 – Tìm địa điểm theo tên |
| `test_us_mem_002_pick_on_map.py` | US-MEM-002 – Chọn vị trí trên bản đồ, đổi tọa độ thành tên |
| `test_us_mem_003_images.py` | US-MEM-003 – Ảnh: số lượng, dung lượng, định dạng, link có chữ ký |
| `test_us_mem_004_video.py` | US-MEM-004 – Video: dung lượng, định dạng, phát theo Range |
| `memories/test_us_mem_007_delete.py` | US-MEM-007 – Xóa ký ức |
| `memories/test_us_mem_008_privacy.py` | US-MEM-008 – Riêng tư/công khai |
| `memories/test_us_mem_009_trips.py` | US-MEM-009 – Chuyến đi |
| `memories/test_us_mem_010_hashtags.py` | US-MEM-010 – Hashtag |
| `memories/test_region_assignment_and_media.py` | Gán tỉnh/thành theo tọa độ, link ảnh/video trong API chi tiết, xóa EXIF/GPS |
| `test_fr_3_6_ai_hashtags.py` | FR-3.6 – Gợi ý hashtag bằng Gemini |
| `test_us_exp_001_004.py` | US-EXP-001, 004 – Bản đồ công khai, tìm kiếm |
| `test_us_exp_002_hashtags.py` | US-EXP-002 – Lọc theo hashtag |
| `test_us_exp_003_regions.py` | US-EXP-003 – Lọc theo khu vực |
| `test_us_exp_005_mine.py` | US-EXP-005 – Lọc ký ức của tôi theo thời gian |
| `admin/conftest.py` | Dữ liệu dùng chung cho test quản trị (admin, chủ ký ức, người khác) |
| `admin/test_us_adm_001_hide_memory.py` | US-ADM-001 – Ẩn/bỏ ẩn, thống kê, nhật ký |
| `admin/test_us_adm_002_delete_memory.py` | US-ADM-002 – Xóa ký ức vi phạm |
| `admin/test_us_adm_003_lock_user.py` | US-ADM-003 – Khóa/mở khóa tài khoản |

Quy ước: mỗi user story một file `test_us_<mã>_<tên>.py`, mỗi AC ít nhất một test, tên test ghi rõ AC (vd `test_ac3_ten_101_ky_tu`).

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
