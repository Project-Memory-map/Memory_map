# Quy ước làm việc nhóm – Bản đồ Ký ức

Tổng hợp từ cách nhóm đang làm trên GitHub. Nhóm trưởng/PO chỉnh lại nếu nhóm thống nhất khác.

## 1. Nhánh

- Không commit thẳng lên `master`. Mỗi task một nhánh tách từ `master` mới nhất:
  ```bash
  git switch master && git pull
  git switch -c <ten>/<ma-task-hoac-story>      # vd: du/us_adm_003, tri/us_mem_007, vy/t05b590_ai_hashtags
  ```
- Tên nhánh: chữ thường, không dấu, nối bằng `_` hoặc `-`, có tên người làm và mã task/story để dễ tìm.
- Nhánh đã merge thì xóa trên GitHub để danh sách nhánh gọn.

## 2. Commit

- Dòng đầu: `<mã task Trello>: <làm gì>` kèm mã user story trong ngoặc, để commit tự gắn vào task:
  ```
  T05B587: loc ky uc ca nhan theo thoi gian (US-EXP-005)
  ```
- Mỗi commit một việc rõ ràng. Không commit `.env`, `uploads/`, `.venv/`, `node_modules/`, `__pycache__/` (đã có trong `.gitignore`).

## 3. Trước khi mở PR

1. Cập nhật nhánh theo `master` mới nhất (`git pull origin master`), giải xung đột nếu có.
2. Chạy test, tất cả phải đạt:
   ```bash
   python -m pytest -q
   ```
3. Viết test cho chức năng mới: mỗi AC ít nhất một test (xem [tests/README.md](tests/README.md)).
4. Thêm/sửa/xóa file thì cập nhật bảng trong `README.md` của thư mục đó. Thêm cấu hình mới thì thêm vào `config.py` **và** `.env.example`.
5. Mở trang trên trình duyệt thử lại chức năng (cả cỡ điện thoại nếu có thao tác chạm/vuốt).

## 4. Pull request

- Gộp vào `master`. Tiêu đề giống dòng đầu commit chính.
- Mô tả: làm user story/AC nào, file nào thay đổi, cách thử, có sửa file của module khác không (báo người phụ trách module đó).
- Sửa `app/core/`, `database/schema.sql` hoặc `app/main.py` cần 2 người duyệt vì ảnh hưởng cả nhóm.
- Ai có PR merge vào `master` thì báo nhóm để mọi người `git pull`. Có thay đổi `schema.sql` thì mọi người chạy lại `python scripts/init_db.py`.

## 5. Quy tắc code

Các lưu ý kỹ thuật (khung phản hồi, lớp lỗi, mốc thời gian, link ảnh có chữ ký, chống XSS, một đường dẫn API chỉ khai báo ở một file) ở mục **4. Chia task** trong [README.md](README.md).
