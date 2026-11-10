# Bản đồ Ký ức

Ứng dụng web ghim kỷ niệm du lịch lên bản đồ (câu chuyện, ảnh, video, hashtag), gom ký ức thành chuyến đi và khám phá ký ức công khai của cộng đồng.

**Công nghệ:** FastAPI · SQLAlchemy 2 · MySQL 8 · HTML/CSS/JS thuần · Leaflet + OpenStreetMap

## Trạng thái hiện tại

Bộ khung đã có sẵn 3 lớp để mỗi thành viên làm chức năng theo task:

| Lớp | Trạng thái |
|---|---|
| **Giao diện** (HTML + CSS) | ✅ Đủ tất cả các trang |
| **Thao tác trên giao diện** (JS) | ✅ Đủ: tab, form, hộp thoại, bản đồ; đã gọi sẵn đúng đường dẫn API |
| **Lưu trữ** (MySQL + model ORM) | ✅ Đủ: schema, trigger, view, 34 tỉnh/thành, model của 11 bảng |
| **API xử lý** (`router.py` của 4 module) | ⏳ Chưa làm. Đây là phần chia task |

API nào chưa làm thì giao diện hiện thông báo **"Chức năng này chưa được xây dựng"**, không bị trắng trang. Danh sách API cần làm của mỗi module ghi ở đầu file `app/modules/<module>/router.py`.

## Các thư mục và file ở gốc

Mỗi thư mục đều có `README.md` riêng mô tả công dụng từng file bên trong.

| Thư mục | Công dụng |
|---|---|
| [`app/`](app/README.md) | Toàn bộ mã nguồn: FastAPI (API) + giao diện + JS |
| [`app/core/`](app/core/README.md) | Lõi dùng chung: cấu hình `.env`, kết nối MySQL, khung phản hồi, xử lý lỗi |
| [`app/shared/`](app/shared/README.md) | Giao diện + JS dùng chung: trang mở đầu, trang chủ bản đồ, CSS chung, `api.js`, `ui.js`, `map.js` |
| [`app/modules/`](app/modules/README.md) | 4 module chức năng (accounts, memories, explore, admin), mỗi module có `ui/` (giao diện), `js/` (xử lý trình duyệt) và `.py` (API) |
| [`database/`](database/README.md) | Lược đồ MySQL (bảng, trigger, view) và dữ liệu 34 tỉnh/thành |
| [`scripts/`](scripts/README.md) | Script chạy tay (khởi tạo DB, dữ liệu mẫu). Hiện còn trống |

| File | Công dụng |
|---|---|
| `README.md` | File này: giới thiệu dự án, cách chạy, cấu trúc, chia task |
| `requirements.txt` | Thư viện Python cần cài (`pip install -r requirements.txt`). Chức năng cần thư viện mới thì thêm vào đây |
| `.env.example` | Mẫu cấu hình. Copy thành `.env` rồi điền mật khẩu MySQL của máy mình (**không commit `.env`**) |
| `.gitignore` | Các file Git bỏ qua: `.env`, `__pycache__/`, `.venv/`, `uploads/` |
| `CONTRIBUTING.md` | ⚠️ *Chưa có nội dung*: quy ước làm việc nhóm (đặt tên nhánh, commit, PR). Nhóm trưởng/PO bổ sung |

## 1. Chạy dự án

Yêu cầu: Python 3.11 – 3.13, MySQL 8.0.

1. Tạo database: chạy `database/schema.sql` rồi `database/seed_regions.sql` trong MySQL Workbench (xem [database/README.md](database/README.md)).
2. Cài thư viện và cấu hình:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate            # Windows
   pip install -r requirements.txt
   copy .env.example .env            # rồi điền DB_PASSWORD
   ```
3. Chạy server:
   ```bash
   python -m uvicorn app.main:app --reload
   ```
4. Mở http://127.0.0.1:8000. Kiểm tra kết nối DB tại http://127.0.0.1:8000/api/health.

## 2. Cấu trúc

Chia theo **chức năng** (4 module). Bên trong mỗi module tách **2 phần**:

| Phần | Nằm ở | Chứa |
|---|---|---|
| **Giao diện** | `ui/` | Chỉ `.html` + `.css`. Mỗi trang là 1 file HTML hoàn chỉnh |
| **Xử lý** | `js/` + file `.py` | `js/`: thao tác phía trình duyệt. `.py`: API và lưu trữ phía máy chủ |

```
app/
├── main.py              Khởi tạo FastAPI, gắn API + giao diện + JS
├── models.py            Gom model của 4 module
├── core/                config (.env), database (MySQL), response, errors
├── shared/
│   ├── ui/              index.html (trang mở đầu), map.html (trang chủ bản đồ), css/, img/
│   └── js/              api.js, ui.js, map.js, shell.js, landing.js
└── modules/
    ├── accounts/  M1    ui/ (6 trang) · js/ · models.py · router.py
    ├── memories/  M2    ui/memories.css · js/ (memories.js, trips.js) · models.py · router.py
    ├── explore/   M3    ui/explore.css · js/explore.js · models.py · router.py
    └── admin/     M4    ui/index.html · js/admin.js · models.py · router.py
database/                schema.sql (bảng + trigger + view), seed_regions.sql, README.md
```

Panel Khám phá, Của tôi, Chuyến đi và form ký ức nằm trong `shared/ui/map.html` (form ở `<template id="memory-form-template">`).

## 3. Bản đồ trang

| Trang | Địa chỉ | Giao diện | Xử lý (JS) |
|---|---|---|---|
| Trang mở đầu | `/` | `shared/ui/index.html` | `shared/js/landing.js` |
| Trang chủ bản đồ | `/ban-do` | `shared/ui/map.html` | `shared/js/map.js`, `shell.js` + `memories/js/*`, `explore/js/explore.js`, `accounts/js/account-menu.js` |
| Đăng nhập | `/accounts/login.html` | `accounts/ui/login.html` | `accounts/js/accounts.js` |
| Đăng ký | `/accounts/register.html` | `accounts/ui/register.html` | `accounts/js/accounts.js` |
| Quên mật khẩu | `/accounts/forgot-password.html` | `accounts/ui/forgot-password.html` | `accounts/js/accounts.js` |
| Đặt lại mật khẩu | `/accounts/reset-password.html` | `accounts/ui/reset-password.html` | `accounts/js/accounts.js` |
| Hồ sơ cá nhân | `/accounts/profile.html` | `accounts/ui/profile.html` | `accounts/js/profile.js` |
| Đăng nhập Google/Facebook | `/accounts/oauth-callback.html` | `accounts/ui/oauth-callback.html` | `accounts/js/oauth-callback.js` |
| Quản trị | `/admin/` | `admin/ui/index.html` | `admin/js/admin.js` |

## 4. Chia task

| Module | Thư mục | User story |
|---|---|---|
| M1 Tài khoản | `app/modules/accounts/` | US-ACC-001 → 008 |
| M2 Ký ức, chuyến đi | `app/modules/memories/` | US-MEM-001 → 010 |
| M3 Khám phá | `app/modules/explore/` | US-EXP-001 → 005 |
| M4 Quản trị | `app/modules/admin/` | US-ADM-001 → 003 |

Làm một task = viết endpoint trong `router.py` (logic tách ra `service.py`, kiểu dữ liệu vào/ra ở `schemas.py`), dùng model có sẵn trong `models.py`. Giao diện và JS đã gọi sẵn đúng đường dẫn nên không cần sửa.

**Lưu ý:**
- M1 nên làm `POST /api/auth/login` và `GET /api/auth/me` trước, vì các module khác cần đăng nhập mới thử được.
- `data` trả về phải có đúng các trường mà file JS đang đọc. Mở file JS ở cột "Gọi từ" trong `router.py`, tìm đường dẫn API để xem. Bản làm đầy đủ để tham khảo nằm ở repo `Demo_nang_cao`.
- Trả kết quả bằng `build_response()` (`core/response.py`). JS đọc trường `message` và `data` trong khung `{statusCode, message, error, data, path, timestamp}`.
- Báo lỗi bằng các lớp trong `core/errors.py` (`ValidationException`, `NotFoundException`, `ForbiddenException`...). Lỗi do trigger chặn tự trả mã 422 kèm câu thông báo của trigger.
- Hiển thị dữ liệu người dùng chỉ bằng `textContent` / `UI.el()`, không dùng `innerHTML` (BR-21).
