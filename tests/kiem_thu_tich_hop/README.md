# tests/kiem_thu_tich_hop/ – Kiểm thử tích hợp 108 AC (task T05B58C)

Chạy lại toàn bộ 108 tiêu chí nghiệm thu (26 user story) trên **máy chủ thật + MySQL thật** (có trigger), và kiểm giao diện trên **Edge ở cỡ máy tính và điện thoại**. Khác với các file `test_*.py` (chạy trên SQLite trong bộ nhớ), thư mục này không chạy bằng `pytest`.

## Kết quả gần nhất

| Lần chạy | ĐẠT | LỖI | CHẶN | CẦN CẤU HÌNH |
|---|---|---|---|---|
| Lần 1 – trước khi sửa (21/11/2026) | 86 | 5 | 17 | – |
| Lần 2 – sau khi sửa 16 lỗi | **103** | **0** | **0** | 5 |

- Giao diện: 46/46 ca đạt trên cả máy tính và điện thoại, không có lỗi JavaScript, không trang nào tràn ngang.
- 5 AC "cần cấu hình" là đăng nhập Google (AC1, 2, 4) và Facebook (AC1, 2): code đã có, test với nhà cung cấp giả lập đã đạt, chỉ cần điền khóa OAuth thật vào `.env` rồi đăng nhập thử 1 lần.
- Danh sách 18 lỗi tìm được (16 đã sửa, 1 ghi nhận theo thiết kế BR-20, 1 chờ khóa OAuth) ở sheet "Danh sách lỗi" của báo cáo và trong `danh_sach_loi.json`.

## Các file

| File | Công dụng |
|---|---|
| `BaoCao_KiemThuTichHop_108AC.xlsx` | **Báo cáo nộp**: tổng quan (so sánh trước/sau khi sửa), kết quả từng AC (API + máy tính + điện thoại), danh sách lỗi kèm cách sửa, kiểm tra thêm, giao diện & thiết bị, cách chạy lại |
| `danh_sach_ac.json` | 108 AC trích từ `ProductBacklog_BanDoKyUc.xlsx` (bản 04/11, sheet Acceptance Criteria) |
| `danh_sach_loi.json` | Danh sách lỗi (mức độ, AC ảnh hưởng, vị trí code, đề xuất, trạng thái, đã sửa thế nào). Sửa thêm lỗi nào thì cập nhật `trang_thai`/`cach_sua` rồi tạo lại báo cáo |
| `chuan_bi_db.py` | Tạo lại database riêng `ban_do_ky_uc_kiemthu` bằng `scripts/init_db.py`. **Không đụng** database làm việc `ban_do_ky_uc` |
| `chay_server.py` | Chạy server trên database kiểm thử, cổng 8010, thư mục upload riêng `ket_qua/uploads/` |
| `kiem_thu_api.py` | Kiểm 108 AC qua HTTP, đối chiếu đúng câu thông báo trong AC và dữ liệu trong DB; thêm 3 phép kiểm lỗi tiềm ẩn (lệch giờ, lộ đường dẫn ảnh đại diện, gán tỉnh/thành) → `ket_qua/api.json`. Ca tìm địa điểm gọi Nominatim thật nên cần Internet |
| `kiem_thu_giao_dien.mjs` | Kiểm các AC cần trình duyệt (đăng ký, đăng nhập, tìm địa điểm và tạo ký ức, chi tiết ảnh/video, xác nhận xóa, nhấp đúp/chạm giữ bản đồ, hồ sơ, quên/đặt lại mật khẩu, đăng xuất + nút Back, trang quản trị, vùng bản đồ trống) trên máy tính 1366×800 và điện thoại giả lập Pixel 7 → `ket_qua/giao_dien.json` + ảnh chụp |
| `tao_bao_cao.mjs` | Gộp các file trên thành báo cáo Excel |
| `package.json`, `package-lock.json` | Thư viện Node: `playwright-core` (điều khiển Edge có sẵn trên máy, không tải trình duyệt) và `exceljs` |
| `ket_qua/` | Kết quả lần chạy gần nhất (`api.json`, `giao_dien.json`). `uploads/` và `anh_chup/` không commit |
| `.gitignore` | Bỏ qua `node_modules/`, `ket_qua/uploads/`, `ket_qua/anh_chup/` |

## Chạy lại

Từ thư mục gốc dự án, đã kích hoạt `.venv`, MySQL đang chạy, `.env` đã điền. Máy cần có Microsoft Edge, Node.js và Internet (bản đồ nền, Nominatim).

```bash
python tests/kiem_thu_tich_hop/chuan_bi_db.py          # 1. tạo database kiểm thử
python tests/kiem_thu_tich_hop/chay_server.py          # 2. chạy server (để cửa sổ này mở)
python tests/kiem_thu_tich_hop/kiem_thu_api.py         # 3. kiểm 108 AC qua API
cd tests/kiem_thu_tich_hop
npm install                                            # lần đầu
npm run giao-dien                                      # 4. kiểm giao diện máy tính + điện thoại
npm run bao-cao                                        # 5. tạo lại báo cáo Excel
```

- Muốn chạy lại bước 3 thì làm lại bước 1 trước: vài ca đếm số ghim trong một vùng bản đồ cố định nên cần database sạch.
- Server không tự nạp lại code: sửa code xong phải dừng và chạy lại bước 2.
- Đã điền khóa Google/Facebook trong `.env` thì 5 AC "cần cấu hình" phải thử tay: bấm nút đăng nhập Google/Facebook bằng tài khoản thử.

## Ý nghĩa kết quả

- **ĐẠT**: đúng AC.
- **LỖI**: sai AC hoặc lỗi chức năng (xem mã lỗi trong sheet "Danh sách lỗi").
- **CHẶN**: chưa kiểm được vì chức năng chưa được xây dựng.
- **CẦN CẤU HÌNH**: code và test giả lập đã đạt, chỉ thiếu khóa của dịch vụ ngoài (Google, Facebook) để đi hết luồng thật.

AC chỉ phụ thuộc quy tắc máy chủ (độ dài, dung lượng, quyền, thông báo lỗi) được kiểm qua API một lần, vì máy tính và điện thoại gọi cùng API. AC phụ thuộc thao tác hoặc hiển thị thì kiểm thêm trên cả hai thiết bị. Điện thoại là **giả lập** Pixel 7 trên Edge (có cảm ứng); trước khi demo nên thử nhanh chạm giữ bản đồ trên 1 điện thoại thật.

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
