# database/

Folder chứa lược đồ cơ sở dữ liệu MySQL của dự án **Bản đồ Ký ức**.

| File | Mô tả |
|---|---|
| `schema.sql` | Tạo database `ban_do_ky_uc`, các bảng, trigger và view |
| `seed_regions.sql` | Nạp 34 tỉnh/thành vào bảng `regions` (dùng cho bộ lọc khu vực). Chạy **sau** `schema.sql` |
| `migrations/20261111_add_facebook_id.sql` | Cập nhật database cũ để lưu ID Facebook trên tài khoản; chỉ chạy một lần |

Thiết kế dựa trên `schema.sql` v0.3 và các quy tắc nghiệp vụ BR-xx trong repo đặc tả [Dac_ta_du_an](https://github.com/Project-Memory-map/Dac_ta_du_an) (`srs/08-quy-tac-nghiep-vu.md`).

---

## 1. Yêu cầu

- **MySQL Server 8.0 trở lên** và **MySQL Workbench**.
- Không dùng được MariaDB hay SQLite, vì schema cần trigger, `CHECK`, `FULLTEXT ... WITH PARSER ngram` và collation `utf8mb4_0900_*`, vốn là tính năng riêng của MySQL 8.

## 2. Cách chạy trên MySQL Workbench

Mỗi thành viên tự chạy trên Workbench của mình:

1. Mở Workbench, kết nối vào MySQL Server (Local instance hoặc server của nhóm).
2. **File → Open SQL Script…** rồi chọn `database/schema.sql`.
3. Bấm ⚡ **Execute** (biểu tượng tia sét, *không* phải tia sét có chữ I).
4. Bấm 🔄 Refresh ở khung **Schemas**, sẽ thấy database `ban_do_ky_uc`.
5. Mở tiếp `database/seed_regions.sql` rồi bấm ⚡ để nạp 34 tỉnh/thành. Chỉ chạy 1 lần; chạy lần 2 sẽ báo trùng `slug`.

Kiểm tra lại đã đủ chưa:

```sql
USE ban_do_ky_uc;
SHOW TABLES;      -- 11 bảng + 1 view v_public_memories
SHOW TRIGGERS;    -- 11 trigger
```

Nếu dùng dòng lệnh thay cho Workbench:

```bash
mysql -u root -p --default-character-set=utf8mb4 < database/schema.sql
```

## 3. Lưu ý quan trọng

1. **Chạy lại không mất dữ liệu.** Bảng dùng `CREATE TABLE IF NOT EXISTS`, trigger được `DROP` rồi tạo lại, view dùng `CREATE OR REPLACE`.
2. **Sửa cấu trúc bảng phải dùng `ALTER TABLE`.** Sửa `CREATE TABLE` trong `schema.sql` sẽ không cập nhật bảng đã tồn tại trên máy. Muốn làm lại từ đầu (sẽ **mất hết dữ liệu**):
   ```sql
   DROP DATABASE ban_do_ky_uc;
   ```
   rồi chạy lại `schema.sql`.
3. **Khi có người sửa `schema.sql` và push lên**, các thành viên khác `git pull` về rồi chạy lại file để database trên máy mình giống nhau.
   Với database đã tạo trước US-ACC-004, chạy thêm migration Facebook một lần trong Workbench.
4. **Không chạy file bằng Python `execute()` một lần.** Phần trigger dùng lệnh `DELIMITER`, mà lệnh này chỉ Workbench và mysql CLI hiểu.
5. **Luôn dùng charset `utf8mb4`.** Thiếu nó thì hashtag tiếng Việt bị trigger từ chối và thông báo lỗi bị vỡ font.

## 4. Kết nối từ backend (FastAPI)

Trong file `.env` ở thư mục gốc (copy từ `.env.example`), mỗi người điền user và mật khẩu MySQL của máy mình:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=<mat_khau_mysql_cua_ban>
DB_NAME=ban_do_ky_uc
```

- `app/core/config.py` đọc các biến này, `app/core/database.py` tạo kết nối (charset `utf8mb4`).
- Mỗi bảng đã có model ORM sẵn trong `app/modules/<module>/models.py`; dùng `db: Session = Depends(get_db)` trong router để đọc/ghi.
- Kiểm tra kết nối: chạy server rồi mở http://127.0.0.1:8000/api/health, thấy `"database": true` là được.
- **Không commit file `.env`**, vì nó chứa mật khẩu (đã có trong `.gitignore`).

## 5. Cấu trúc schema

| Phần | Bảng / đối tượng | Module code |
|---|---|---|
| 0 | Tạo database `ban_do_ky_uc` (utf8mb4) | – |
| 1 | `users`, `oauth_accounts`, `password_reset_tokens` | `app/modules/accounts` |
| 2 | `regions` | dùng chung (memories, explore) |
| 3 | `memories`, `media`, `trips`, `trip_memories`, `hashtags`, `memory_hashtags` | `app/modules/memories` |
| 4 | `admin_actions` | `app/modules/admin` |
| 5 | 11 trigger | – |
| 6 | View `v_public_memories` | `app/modules/explore` |

### Quan hệ chính

- `users` 1–n `memories`, `trips`, `oauth_accounts`, `password_reset_tokens`
- `memories` 1–n `media`
- `memories` n–n `trips` (qua `trip_memories`)
- `memories` n–n `hashtags` (qua `memory_hashtags`)
- `regions` 1–n `memories`
- `users` (admin) 1–n `admin_actions`

### Một số cột cần hiểu

| Cột | Ý nghĩa |
|---|---|
| `users.password_hash` | Chỉ lưu bản băm (bcrypt/argon2), không bao giờ lưu mật khẩu gốc (BR-07) |
| `users.token_version` | Tăng 1 thì mọi JWT cũ mất hiệu lực. Backend so sánh giá trị trong JWT với giá trị trong DB ở mỗi request (BR-20) |
| `users.failed_login_count`, `first_failed_at`, `login_locked_until` | Sai mật khẩu 5 lần trong 15 phút thì tạm khóa đăng nhập 15 phút (BR-15) |
| `users.email_verified_at` | `NULL` = email chưa xác thực, khi đó không tự gộp tài khoản OAuth (BR-18) |
| `password_reset_tokens.token_hash` | SHA-256 của token. Token gốc chỉ nằm trong email gửi người dùng (BR-14) |
| `memories.visibility` | Mặc định `private` (BR-01) |
| `memories.status` | `hidden` = bị quản trị viên ẩn |
| `memories.deleted_at` | Xóa mềm: khác `NULL` là đã xóa (BR-13) |
| `media.file_path` | Đường dẫn nội bộ. Frontend chỉ nhận URL có chữ ký do backend cấp (BR-17) |
| `hashtags.name` | Lưu không có `#`, dạng chữ thường. Collation `as_ci` phân biệt dấu nên `đà` khác `da` |
| `memory_hashtags.source` | `manual` = người dùng tự gõ, `ai` = Gemini gợi ý |
| `admin_actions.target_id` | Trỏ tới `memories.id` hoặc `users.id` tùy `target_type`, nên không có khóa ngoại |

### Quy ước đặt tên

- Bảng: số nhiều, `snake_case` (`users`, `trip_memories`)
- Khóa chính `id`, khóa ngoại `<bảng_số_ít>_id` (`user_id`)
- Tiền tố ràng buộc: `pk_` khóa chính, `uq_` unique, `idx_` index, `fk_` khóa ngoại, `ck_` check
- Trigger: `trg_<bảng>_<bi|bu|bd>` = Before Insert / Before Update / Before Delete

## 6. Trigger

**Vì sao cần trigger dù backend đã kiểm tra?** Nếu code của ai đó quên kiểm tra, database vẫn chặn được. Đây là lớp bảo vệ cuối cùng.

Khi vi phạm, trigger báo lỗi `SQLSTATE '45000'` (mã lỗi MySQL **1644**) và hủy lệnh. Backend bắt lỗi này trong `app/core/errors.py` rồi trả về HTTP 400 kèm thông báo.

| Trigger | Bảng | Chức năng | BR |
|---|---|---|---|
| `trg_users_bi` | users | Email về chữ thường, bỏ khoảng trắng | BR-08 |
| `trg_users_bu` | users | Như trên + tăng `token_version` khi đổi mật khẩu hoặc bị khóa | BR-08, BR-20 |
| `trg_memories_bi` | memories | Ngày ký ức không ở tương lai | BR-05 |
| `trg_memories_bu` | memories | Như trên + không đổi chủ sở hữu | BR-05, BR-02 |
| `trg_media_bi` | media | Tối đa 10 ảnh ≤ 5 MB, 1 video ≤ 50 MB | BR-06 |
| `trg_hashtags_bi` | hashtags | Bỏ `#`, chữ thường, chỉ chữ/số/`_` | BR-06 |
| `trg_memory_hashtags_bi` | memory_hashtags | Tối đa 10 hashtag / ký ức | BR-06 |
| `trg_trip_memories_bi` | trip_memories | Chỉ thêm ký ức của chính chủ chuyến đi | BR-09 |
| `trg_admin_actions_bi` | admin_actions | Phải là admin, action khớp target, ẩn/xóa/khóa phải có lý do, không tự khóa mình | BR-10, BR-11 |
| `trg_admin_actions_bu` | admin_actions | Không cho sửa nhật ký | BR-10 |
| `trg_admin_actions_bd` | admin_actions | Không cho xóa nhật ký | BR-10 |

Ghi chú cú pháp:

- `DELIMITER $$` đổi ký tự kết thúc lệnh tạm thời, để dấu `;` bên trong thân trigger không bị hiểu là hết lệnh.
- `a <=> b` là so sánh bằng nhau kể cả khi có `NULL`.
- Ràng buộc `CHECK` không dùng được `CURDATE()`, nên kiểm tra ngày phải làm bằng trigger.

## 7. View `v_public_memories`

Trả về các ký ức hiện trên bản đồ cộng đồng, đủ 4 điều kiện của **BR-03**: công khai, không bị ẩn, chưa xóa, chủ ký ức không bị khóa. View chỉ trả tên hiển thị của tác giả, **không có email** (BR-12).

Module `explore` chỉ cần:

```sql
SELECT * FROM v_public_memories WHERE region_id = ?;
```
