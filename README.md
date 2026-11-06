# Bản đồ Ký ức

Ứng dụng web ghim kỷ niệm du lịch lên bản đồ (câu chuyện, ảnh, video, hashtag), gom ký ức thành chuyến đi và khám phá ký ức công khai của cộng đồng.

**Công nghệ:** FastAPI · SQLAlchemy 2 · MySQL 8 · HTML/CSS/JS thuần · Leaflet + OpenStreetMap

Tài liệu đặc tả: [docs/](docs/README.md) · Quy ước làm việc nhóm: [CONTRIBUTING.md](CONTRIBUTING.md)

## Cấu trúc thư mục

Dự án chia theo **chức năng**: mỗi module chứa trọn phần của mình, cả API lẫn giao diện. Người phụ trách module nào chỉ làm việc trong thư mục module đó.

```
ban-do-ky-uc/
├── app/
│   ├── main.py                    Khởi tạo FastAPI, tự gắn API và giao diện của 4 module
│   ├── models.py                  Gom model của 4 module
│   ├── core/                      Backend dùng chung
│   │   ├── config.py              Đọc cấu hình từ .env
│   │   ├── database.py            Engine, SessionLocal, Base, get_db
│   │   ├── security.py            bcrypt, JWT (có token_version), ký URL media (BR-17)
│   │   ├── deps.py                Đọc Bearer token
│   │   ├── errors.py              AppException và bộ xử lý lỗi chung
│   │   ├── response.py            build_response() — khung phản hồi 6 trường
│   │   └── storage.py             Thư mục uploads/, tạo tên tệp duy nhất
│   ├── shared/                    Giao diện dùng chung (phục vụ ở /)
│   │   ├── index.html             Trang bản đồ — khung chứa giao diện các module
│   │   ├── css/base.css           Màu, bố cục, nút, form, thanh bên, ngăn kéo
│   │   └── js/
│   │       ├── api.js             Gọi API, gắn JWT
│   │       ├── ui.js              Thông báo, nạp giao diện con, đọc form
│   │       ├── map.js             Leaflet: bản đồ, ghim, nhấp đúp / nhấn giữ
│   │       └── shell.js           Khởi tạo bản đồ và thanh bên
│   └── modules/
│       ├── accounts/              M1 — Tài khoản và người dùng
│       │   ├── models.py  schemas.py  router.py  deps.py
│       │   └── ui/                (phục vụ ở /accounts/)
│       │       ├── login.html  register.html  forgot-password.html
│       │       ├── reset-password.html  profile.html
│       │       ├── account-menu.js   Menu góc trên: tên, Hồ sơ, Quản trị, Đăng xuất
│       │       ├── accounts.js       Xử lý chung cho mọi form tài khoản
│       │       ├── profile.js
│       │       └── accounts.css
│       ├── memories/              M2 — Ký ức, ảnh/video, chuyến đi, hashtag
│       │   ├── models.py  router.py
│       │   └── ui/                (phục vụ ở /memories/)
│       │       ├── panel.html        Mục "Ký ức của tôi", "Chuyến đi" trên thanh bên
│       │       ├── memory-form.html  Form ghim ký ức (mở khi nhấp đúp bản đồ)
│       │       ├── memories.js  memories.css
│       ├── explore/               M3 — Khám phá, lọc, tìm kiếm
│       │   ├── models.py  schemas.py  repository.py  service.py  router.py
│       │   └── ui/                (phục vụ ở /explore/)
│       │       ├── panel.html        Bộ lọc từ khóa, hashtag, khu vực
│       │       ├── explore.js        Tải và vẽ ghim công khai
│       │       └── explore.css
│       └── admin/                 M4 — Quản trị
│           ├── models.py  router.py
│           └── ui/                (phục vụ ở /admin/)
│               ├── index.html        Trang quản trị: ký ức, tài khoản, nhật ký
│               ├── admin.js  admin.css
├── database/schema.sql            Lược đồ MySQL v0.3 — nguồn chuẩn của cơ sở dữ liệu
├── scripts/
│   ├── init_db.py                 Chạy schema.sql và kiểm tra bảng khớp model
│   └── seed_demo.py               Tạo tài khoản và ký ức mẫu
└── docs/                          SRS và sơ đồ dạng Markdown
```

**Backend của module** tách theo lớp `router.py → service.py → repository.py`, kèm `models.py`, `schemas.py`. Module `explore/` đã có đủ các lớp, xem làm mẫu.

**Giao diện của module** nằm trong `ui/`; chỉ thư mục này được phục vụ ra trình duyệt, file `.py` không lộ ra ngoài. Có hai kiểu:

- **Trang riêng** (đăng nhập, hồ sơ, quản trị): file `.html` đầy đủ, nạp `/css/base.css`, `/js/api.js`, `/js/ui.js` dùng chung.
- **Mảnh gắn vào trang bản đồ** (thanh bên, form ghim): file `.html` không có `<html>`, được `UI.loadPartial()` nạp vào ô tương ứng của `shared/index.html` (`#explore-panel`, `#memories-panel`, `#drawer`). Script của module gắn vào `shared/index.html` một lần, sau đó tự xử lý.

Thêm module thứ 5: tạo `app/modules/<ten>/` có `router.py` và `ui/`, rồi thêm một dòng vào `MODULE_ROUTERS` trong `app/main.py`.

## Chạy dự án

Yêu cầu: Python 3.11 trở lên, MySQL 8.0.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt

cp .env.example .env              # Windows: copy .env.example .env — rồi sửa DB_USER, DB_PASSWORD, hai khóa bí mật
python scripts/init_db.py --reset
python scripts/seed_demo.py

uvicorn app.main:app --reload
```

Chạy lệnh ở thư mục gốc của repo. Mở:

- http://127.0.0.1:8000 — trang bản đồ
- http://127.0.0.1:8000/accounts/login.html — đăng nhập (M1)
- http://127.0.0.1:8000/admin/ — quản trị (M4, cần tài khoản admin)
- http://127.0.0.1:8000/docs — Swagger
- http://127.0.0.1:8000/api/health — kiểm tra kết nối cơ sở dữ liệu

Tài khoản mẫu (mật khẩu `Matkhau123`): `admin@bandokyuc.local` (quản trị viên), `an@example.com` (người dùng, có 3 ký ức công khai và 1 ký ức riêng tư).

## API

### Đã chạy

| Phương thức | Đường dẫn | Module | Ghi chú |
|---|---|---|---|
| GET | `/api/health` | Core | Kiểm tra kết nối cơ sở dữ liệu |
| GET | `/api/auth/me` | M1 | Cần Bearer token; JWT sai `token_version` hoặc tài khoản bị khóa đều bị từ chối |
| GET | `/api/explore/pins?south=&west=&north=&east=` | M3 | Ghim công khai trong vùng đang xem, theo BR-03 |

### Giao diện đã gọi sẵn — module cần xây API khớp

| Phương thức | Đường dẫn | Module | Gửi lên | Trả về `data` |
|---|---|---|---|---|
| POST | `/api/auth/register` | M1 | JSON `display_name, email, password` | `access_token`, `user` |
| POST | `/api/auth/login` | M1 | JSON `email, password` | `access_token`, `user` |
| GET | `/api/auth/google/login`, `/api/auth/facebook/login` | M1 | — | chuyển hướng sang nhà cung cấp |
| POST | `/api/auth/forgot-password` | M1 | JSON `email` | — |
| POST | `/api/auth/reset-password` | M1 | JSON `token, new_password` | — |
| POST | `/api/auth/change-password` | M1 | JSON `current_password, new_password` | `access_token` mới |
| PATCH | `/api/users/me` | M1 | JSON `display_name, bio` | `user` |
| POST | `/api/users/me/avatar` | M1 | multipart `avatar` | `user` |
| POST | `/api/memories` | M2 | multipart `title, place_name, latitude, longitude, memory_date, content, hashtags, visibility, images[], video` | ký ức vừa tạo |
| GET | `/api/explore/pins` | M3 | thêm query `q, hashtags, region` | như trên, đã lọc |

API chưa xây sẽ trả 404 với thông báo "Chức năng này chưa được xây dựng...". Đổi tên trường hay đường dẫn thì sửa cả bảng này và file giao diện tương ứng.

Mọi phản hồi dùng chung một khung:

```json
{"statusCode": 200, "message": "...", "error": null, "data": {}, "path": "/api/...", "timestamp": "..."}
```

## Quy tắc bắt buộc với mọi module

- Thay đổi cấu trúc bảng: sửa `database/schema.sql` trước, rồi sửa model tương ứng. Chạy `python scripts/init_db.py --reset` để kiểm tra.
- Lấy người dùng hiện tại bằng `Depends(get_current_user)`; route quản trị dùng `Depends(require_admin)`. Cả hai nằm trong `modules/accounts/deps.py`.
- Báo lỗi bằng các lớp trong `core/errors.py` (`NotFoundException`, `ForbiddenException`...), không trả `HTTPException` trực tiếp.
- Giao diện chỉ gán dữ liệu người dùng bằng `textContent`, không dùng `innerHTML` (BR-21). `UI.loadPartial()` chỉ dùng để nạp file `.html` tĩnh trong `ui/` của module.
- Ảnh/video chỉ trả về qua `sign_media_url()`; không mở thư mục `uploads/` dạng tĩnh (BR-17).
