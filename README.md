# Bản đồ Ký ức

Ứng dụng web ghim kỷ niệm du lịch lên bản đồ (câu chuyện, ảnh, video, hashtag), gom ký ức thành chuyến đi và khám phá ký ức công khai của cộng đồng.

**Công nghệ:** FastAPI · SQLAlchemy 2 · MySQL 8 · HTML/CSS/JS thuần · Leaflet + OpenStreetMap

## Trạng thái hiện tại

Đã làm đủ 26 user story của Sprint 1–3 (4 module, 108 tiêu chí nghiệm thu).

| Lớp | Trạng thái |
|---|---|
| **Giao diện** (HTML + CSS) | ✅ Đủ tất cả các trang, dùng được trên máy tính và điện thoại |
| **Thao tác trên giao diện** (JS) | ✅ Đủ: tab, form, hộp thoại, bản đồ, gọi đúng API |
| **Lưu trữ** (MySQL + model ORM) | ✅ Đủ: schema, 11 trigger, view, 34 tỉnh/thành, ranh giới tỉnh/thành, model của 11 bảng |
| **API xử lý** (4 module) | ✅ Đủ: mọi đường dẫn giao diện gọi đều đã có API |
| **Kiểm thử** | ✅ 238 test tự động (`pytest`) + kiểm thử tích hợp 108 AC trên MySQL thật, máy tính và điện thoại |

Kết quả kiểm thử tích hợp gần nhất (task T05B58C): **103/108 AC đạt, 0 lỗi**. 5 AC còn lại là đăng nhập Google/Facebook: code và test giả lập đã đạt, chỉ cần điền khóa OAuth thật vào `.env` để thử với tài khoản thật. Chi tiết trong [tests/kiem_thu_tich_hop/](tests/kiem_thu_tich_hop/README.md).

## Các thư mục và file ở gốc

Mỗi thư mục đều có `README.md` riêng mô tả công dụng từng file bên trong.

| Thư mục | Công dụng |
|---|---|
| [`app/`](app/README.md) | Toàn bộ mã nguồn: FastAPI (API) + giao diện + JS |
| [`app/core/`](app/core/README.md) | Lõi dùng chung: cấu hình `.env`, kết nối MySQL, JWT, mật khẩu, khung phản hồi, xử lý lỗi |
| [`app/shared/`](app/shared/README.md) | Giao diện + JS dùng chung: trang mở đầu, trang chủ bản đồ, CSS chung, `api.js`, `ui.js`, `map.js` |
| [`app/modules/`](app/modules/README.md) | 4 module chức năng (accounts, memories, explore, admin), mỗi module có `ui/` (giao diện), `js/` (xử lý trình duyệt) và `.py` (API) |
| [`database/`](database/README.md) | Lược đồ MySQL (bảng, trigger, view) và dữ liệu 34 tỉnh/thành |
| [`scripts/`](scripts/README.md) | Script chạy tay: tạo database, dữ liệu mẫu, gán khu vực, dựng ranh giới tỉnh/thành |
| [`tests/`](tests/README.md) | Test tự động (`pytest`, chạy trên SQLite) và kiểm thử tích hợp 108 AC (MySQL thật + trình duyệt) |

| File | Công dụng |
|---|---|
| `README.md` | File này: giới thiệu dự án, cách chạy, cấu trúc, chia task |
| `requirements.txt` | Thư viện Python cần cài. Chức năng cần thư viện mới thì thêm vào đây |
| `requirements-dev.txt` | Thư viện chỉ dùng khi phát triển/kiểm thử (`pytest`) |
| `.env.example` | Mẫu cấu hình. Copy thành `.env` rồi điền mật khẩu MySQL của máy mình (**không commit `.env`**) |
| `.gitignore` | Các file Git bỏ qua: `.env`, `__pycache__/`, `.venv/`, `uploads/` |
| `CONTRIBUTING.md` | Quy ước làm việc nhóm: đặt tên nhánh, commit, PR, chạy test trước khi gửi |

## 1. Chạy dự án

Yêu cầu: Python 3.11 trở lên (đã chạy trên 3.14), MySQL 8.0.

1. Cài thư viện và cấu hình:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate            # Windows (macOS/Linux: source .venv/bin/activate)
   pip install -r requirements.txt -r requirements-dev.txt
   copy .env.example .env            # rồi điền DB_PASSWORD, JWT_SECRET, MEDIA_SECRET
   ```
2. Tạo database (bảng, trigger, view, 34 tỉnh/thành):
   ```bash
   python scripts/init_db.py         # chạy lại an toàn; thêm --xoa-cu để xóa và tạo lại từ đầu
   python scripts/seed_demo.py       # (tùy chọn) tài khoản + ký ức mẫu để thử giao diện
   ```
   Vẫn có thể chạy tay `database/schema.sql` rồi `seed_regions.sql` trong MySQL Workbench, xem [database/README.md](database/README.md).
3. Chạy server:
   ```bash
   python -m uvicorn app.main:app --reload
   ```
4. Mở http://127.0.0.1:8000. Kiểm tra kết nối DB tại http://127.0.0.1:8000/api/health. Danh sách API: http://127.0.0.1:8000/docs.

Tài khoản mẫu (sau khi chạy `seed_demo.py`): `admin@example.com / Admin12345` (quản trị), `an@example.com / Matkhau123`, `binh@example.com / Matkhau123`.

### Cấu hình tùy chọn trong `.env`

Không điền thì ứng dụng vẫn chạy, chỉ tắt chức năng tương ứng. Hướng dẫn lấy từng khóa ghi ngay trong `.env.example`.

| Chức năng | Biến | Khi để trống |
|---|---|---|
| Đăng nhập Google (US-ACC-003) | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Nút Google bị làm mờ |
| Đăng nhập Facebook (US-ACC-004) | `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI` | Nút Facebook bị làm mờ |
| Email đặt lại mật khẩu (US-ACC-005) | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | Ở `APP_ENV=dev`, trang quên mật khẩu hiện thẳng liên kết đặt lại để thử; môi trường thật thì không gửi được |
| Gợi ý hashtag bằng AI (FR-3.6) | `GEMINI_API_KEY` | Gợi ý theo từ khóa trong tiêu đề/nội dung, không gọi AI |
| Liên kết trong email | `APP_BASE_URL` | Mặc định `http://127.0.0.1:8000` |

Dịch vụ bên ngoài luôn dùng: OpenStreetMap (nền bản đồ) và Nominatim (tìm địa điểm, đổi tọa độ thành tên). Hai dịch vụ này cần Internet nhưng không cần khóa.

### Chạy test

```bash
python -m pytest -q                              # 238 test, khoảng 20 giây, không cần MySQL
```

Kiểm thử tích hợp 108 AC trên MySQL thật và trình duyệt (máy tính + điện thoại) xem [tests/kiem_thu_tich_hop/README.md](tests/kiem_thu_tich_hop/README.md).

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
├── core/                config (.env), database (MySQL), security (JWT, ký URL), passwords, response, errors
├── shared/
│   ├── ui/              index.html (trang mở đầu), map.html (trang chủ bản đồ), css/, img/
│   └── js/              api.js, ui.js, map.js, shell.js, landing.js
└── modules/
    ├── accounts/  M1    ui/ (6 trang) · js/ · router theo từng chức năng · services/ (Google, Facebook)
    ├── memories/  M2    ui/memories.css · js/ (memories.js, trips.js) · router theo từng chức năng · services/
    ├── explore/   M3    ui/explore.css · js/explore.js · router.py · region_lookup.py · data/provinces.geojson
    └── admin/     M4    ui/index.html · js/admin.js · models.py · router.py
database/                schema.sql (bảng + trigger + view), seed_regions.sql, README.md
scripts/                 init_db.py, seed_demo.py, gan_khu_vuc.py, tao_ranh_gioi_tinh.py
tests/                   test pytest theo module + kiem_thu_tich_hop/ (108 AC)
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
| M2 Ký ức, chuyến đi | `app/modules/memories/` | US-MEM-001 → 010, US-EXP-005 |
| M3 Khám phá | `app/modules/explore/` | US-EXP-001 → 004 |
| M4 Quản trị | `app/modules/admin/` | US-ADM-001 → 003 |

Bảng API của từng module (đường dẫn, mã task, file JS gọi) nằm trong README của module đó.

**Lưu ý khi sửa hoặc thêm chức năng:**
- `data` trả về phải có đúng các trường mà file JS đang đọc. Mở file JS gọi API đó để xem.
- Trả kết quả bằng `build_response()` (`core/response.py`). JS đọc trường `message` và `data` trong khung `{statusCode, message, error, data, path, timestamp}`.
- Báo lỗi bằng các lớp trong `core/errors.py` (`ValidationException`, `NotFoundException`, `ForbiddenException`...). Lỗi do trigger chặn tự trả mã 422 kèm câu thông báo của trigger.
- Mốc thời gian của bản ghi (`updated_at`, `deleted_at`) gán bằng `func.now()` (giờ của database, cùng chuẩn với `created_at`). Không gán `datetime.now(timezone.utc)` vì sẽ lệch 7 giờ so với cột do MySQL tự ghi.
- Link ảnh/video trả cho trình duyệt phải có chữ ký (`sign_media_url`, `video_url`); ảnh đại diện dùng `avatar_url(user)`, không trả thẳng đường dẫn lưu trữ.
- Hiển thị dữ liệu người dùng chỉ bằng `textContent` / `UI.el()`, không dùng `innerHTML` (BR-21).
- Một đường dẫn API chỉ khai báo ở **một** file. Hai file cùng khai báo thì chỉ hàm đăng ký trước trong `main.py` chạy, hàm kia thành code chết.
