# Kịch bản Thuyết trình Bảo vệ & Live Demo – Dự án "Bản đồ Ký ức" (Sprint 4)

> Tài liệu phục vụ buổi bảo vệ đồ án trước Hội đồng, bám sát **100% mã nguồn thực tế** trong repository `Project-Memory-map/Memory_map` (nhánh `master`, 26 User Stories, 62 API endpoints / 65 route HTTP, 11 bảng & 11 trigger MySQL 8, 238 test `pytest` PASS).

---

## PHẦN 1. CHECKLIST CHUẨN BỊ MÔI TRƯỜNG TRƯỚC GIỜ BẢO VỆ (T-15 PHÚT)

### 1.1. Kiểm tra dịch vụ nền & cấu hình `.env`
- [ ] **MySQL Server 8.0** đang chạy ở cổng `3306` (`DB_HOST=localhost`).
- [ ] File `.env` ở thư mục gốc đã điền đủ các khóa tối thiểu:
  - `APP_ENV=dev`
  - `DB_USER`, `DB_PASSWORD`, `DB_NAME=ban_do_ky_uc`
  - `JWT_SECRET` (chuỗi bí mật >= 32 ký tự) & `MEDIA_SECRET` (chuỗi bí mật >= 32 ký tự)
  - *(Tùy chọn cho demo AI hashtag)*: `GEMINI_API_KEY` (nếu để trống, hệ thống vẫn hoạt động bình thường với cơ chế fallback tách từ khóa cục bộ `engine: "local"`).
- [ ] Máy thuyết trình có **kết nối Internet ổn định** (để tải bản đồ nền OpenStreetMap qua Leaflet và gọi Nominatim Geocoding/Reverse Geocoding).

### 1.2. Nạp lại CSDL sạch & Dữ liệu mẫu chuẩn (`scripts/`)
Mở PowerShell tại thư mục gốc dự án và chạy tuần tự:

```powershell
.venv\Scripts\activate
python scripts/init_db.py --xoa-cu
python scripts/seed_demo.py
python -m pytest -q
```

**Kết quả kỳ vọng trước khi lên bục:**
- `init_db.py --xoa-cu` tạo đủ **11 bảng**, **11 trigger**, **1 view** (`v_public_memories`) và nạp **34 tỉnh/thành** (`regions`).
- `seed_demo.py` tạo **3 tài khoản**, **10 ký ức** (8 công khai, 2 riêng tư ở Hà Nội, Đà Lạt, Hội An, Hạ Long, Sa Pa, Đà Nẵng, Cần Thơ, Sài Gòn), các hashtag và **1 chuyến đi** (`"Đà Lạt tháng 10"`).
- `pytest -q` hiển thị **`238 passed`**.

### 1.3. Khởi chạy Server & Kiểm tra nhanh
```powershell
python -m uvicorn app.main:app --reload
```
Kiểm tra nhanh 3 URL trước khi vào phần trình bày:
1. `http://127.0.0.1:8000/api/health` → trả về `statusCode: 200` và `"database": true`.
2. `http://127.0.0.1:8000/docs` → mở sẵn Swagger UI ở một tab phụ (dự phòng khi Hội đồng muốn xem danh sách API).
3. `http://127.0.0.1:8000/ban-do` → hiển thị bản đồ Leaflet với 8 ghim đỏ công khai.

### 1.4. Tài khoản Demo & Tệp đa phương tiện chuẩn bị sẵn
| Vai trò | Email | Mật khẩu | Mục đích sử dụng khi Demo |
|---|---|---|---|
| **User chính** | `an@example.com` | `Matkhau123` | Đăng nhập, xem hồ sơ, tạo ký ức mới + media + AI hashtag, gom vào chuyến đi *"Đà Lạt tháng 10"* |
| **User phụ** | `binh@example.com` | `Matkhau123` | Kiểm tra khả năng phân quyền sở hữu & tạo ký ức vi phạm để Admin kiểm duyệt/khóa |
| **Quản trị viên** | `admin@example.com` | `Admin12345` | Đăng nhập `/admin/` trong cửa sổ ẩn danh để ẩn/xóa ký ức & khóa tài khoản |

Chuẩn bị sẵn thư mục `demo_assets/` trên Desktop gồm:
- `anh_chup_1.jpg`, `anh_chup_2.png` (mỗi ảnh **< 5 MB**, tốt nhất có sẵn EXIF GPS để chứng minh tính năng xóa EXIF nếu Hội đồng hỏi).
- `anh_qua_lon_6mb.jpg` (**> 5 MB**, dự phòng nếu Hội đồng muốn kiểm chứng thông báo lỗi `BR-06`).
- `video_ky_niem.mp4` (**< 50 MB**, định dạng `.mp4`, dài 5–10 giây để thử phát stream `HTTP 206 Range`).

Mở sẵn **2 cửa sổ trình duyệt** (Microsoft Edge / Chrome):
- **Cửa sổ 1 (Thường):** Mở sẵn `http://127.0.0.1:8000/ban-do` (dành cho Khách / User `an@example.com` và `binh@example.com`).
- **Cửa sổ 2 (Ẩn danh / Incognito):** Mở sẵn `http://127.0.0.1:8000/accounts/login.html` (để đăng nhập `admin@example.com`, tránh đè JWT token của User).

---

## PHẦN 2. PHÂN CÔNG & LỜI DẪN THUYẾT TRÌNH CHI TIẾT (14 SLIDES · ~12–14 PHÚT)

| Thành viên | Slides phụ trách | Trọng tâm trình bày |
|---|---|---|
| **Nguyễn Tấn Du** | Slides **1, 2, 3, 4, 5** & **9** | Mở đầu, bài toán, phạm vi, kiến trúc FastAPI Modular Monolith, CSDL MySQL & Module 4 Admin |
| **Lê Minh Trí** | Slide **6 (nửa đầu)** & **8** | Đăng nhập/chống brute-force, Quên mật khẩu SHA-256, Khám phá bản đồ, GeoJSON & FULLTEXT |
| **Phạm Đình Thương** | Slide **6 (nửa sau)** & **7** | Facebook OAuth, JWT `token_version`, Ghim bản đồ Nominatim, Media HMAC/Range, Chuyến đi & Hashtag |
| **Phương Vy** | Slides **10, 11, 12, 13, 14** | Quy trình Git Flow, Kết quả `pytest` 238 test & 108 AC, Điều phối Live Demo, Hướng phát triển & Kết thúc |

---

### Slide 1 – Trang bìa
- **Người trình bày:** Nguyễn Tấn Du · **Thời lượng:** 30 giây
- **Lời dẫn:**
  > "Kính chào Quý Thầy/Cô trong Hội đồng bảo vệ đồ án. Nhóm em gồm 4 thành viên: Nguyễn Tấn Du, Phạm Đình Thương, Phương Vy và Lê Minh Trí. Hôm nay nhóm xin trình bày kết quả bảo vệ Sprint 4 của dự án **Bản đồ Ký ức (Memory Map)** — ứng dụng web cho phép lưu giữ, gom chuyến đi và khám phá các kỷ niệm du lịch gắn với không gian địa lý và dòng thời gian."
- **Điểm nhấn trên slide:** Chỉ tay vào danh sách 4 thành viên và 5 pill công nghệ thực tế (`FastAPI`, `SQLAlchemy 2.0`, `MySQL 8.0`, `Leaflet + OSM`, `Pytest 238/238 PASS`).

### Slide 2 – Đặt vấn đề & Mục tiêu
- **Người trình bày:** Nguyễn Tấn Du · **Thời lượng:** 45 giây
- **Lời dẫn:**
  > "Trong thực tế, ảnh và câu chuyện du lịch của người dùng thường phân tán trên nhiều nền tảng, không có góc nhìn tổng thể theo tọa độ bản đồ, khó tra cứu lại theo tỉnh thành hay thời gian, và đặc biệt là dễ bị rò rỉ tọa độ GPS trong EXIF ảnh khi chia sẻ công khai. Vì vậy, mục tiêu Giai đoạn 1 của nhóm là xây dựng trọn vẹn **4 phân hệ**, hoàn thành **26 User Stories** và **108 tiêu chí nghiệm thu (AC)** xoay quanh 21 quy tắc nghiệp vụ từ `BR-01` đến `BR-21`."
- **Điểm nhấn:** 3 Big Numbers (`4 Phân hệ`, `26 User Stories`, `108 Tiêu chí AC`) và cột đối chiếu Thực trạng ↔ Giải pháp.

### Slide 3 – Phạm vi hệ thống & Các phân hệ (4 Epics)
- **Người trình bày:** Nguyễn Tấn Du · **Thời lượng:** 45 giây
- **Lời dẫn:**
  > "Về phạm vi triển khai, hệ thống gồm **4 Epics**, tương ứng 4 module độc lập với tổng cộng **62 API endpoints** (65 route HTTP) và **9 trang giao diện** chạy mượt trên cả máy tính và điện thoại:
  > - **M1 Tài khoản (`accounts`)**: 8 User Stories, 18 API.
  > - **M2 Ký ức & Chuyến đi (`memories`)**: 11 User Stories, 29 API.
  > - **M3 Khám phá (`explore`)**: 4 User Stories, 5 API.
  > - **M4 Quản trị (`admin`)**: 3 User Stories, 9 API."
- **Điểm nhấn:** 4 KPI ở hàng trên (`4`, `26`, `62`, `9`) và cấu trúc phân chia theo từng phân hệ.

### Slide 4 – Kiến trúc Hệ thống & Tech Stack
- **Người trình bày:** Nguyễn Tấn Du · **Thời lượng:** 1 phút
- **Lời dẫn:**
  > "Nhóm lựa chọn kiến trúc **Modular Monolith** trên **FastAPI**. Như sơ đồ 3 tầng trên màn hình:
  > - Tầng trình duyệt dùng HTML5, CSS3, JavaScript thuần và **Leaflet + OpenStreetMap**, tuân thủ `BR-21` chỉ render văn bản qua `textContent` để chống XSS.
  > - Tầng Backend tập trung cấu hình, DB, bảo mật JWT/HMAC và chuẩn phản hồi `build_response()` + xử lý lỗi `app/core/errors.py` tại `app/core/`, còn 4 module nghiệp vụ tự đóng gói đầy đủ `ui/`, `js/` và các file router riêng.
  > - Tầng dữ liệu kết nối **MySQL 8.0** qua **SQLAlchemy 2.0**, lưu trữ tệp tại `uploads/` và giao tiếp các dịch vụ ngoài qua `httpx`."
- **Điểm nhấn:** Chỉ theo luồng mũi tên trong sơ đồ SVG từ Client → `app/core/` + 4 Modules → MySQL / `uploads/` / External APIs và cây thư mục bên phải.

### Slide 5 – Thiết kế Cơ sở Dữ liệu
- **Người trình bày:** Nguyễn Tấn Du · **Thời lượng:** 1 phút
- **Lời dẫn:**
  > "Cơ sở dữ liệu `ban_do_ky_uc` sử dụng MySQL 8.0 charset `utf8mb4`, gồm **11 bảng InnoDB**, **11 Trigger**, **1 View** `v_public_memories` và danh mục **34 tỉnh/thành** sau sắp xếp 2025.
  > Điểm đặc biệt của nhóm là xem **11 Trigger như lớp bảo vệ cuối cùng** ở tầng CSDL: ví dụ chặn ngày ký ức ở tương lai, giới hạn 10 ảnh / 1 video, tự tăng `token_version` khi đổi mật khẩu hoặc khóa tài khoản, và cấm sửa/xóa bảng nhật ký `admin_actions`. Khi trigger phát tín hiệu `SQLSTATE '45000'` (mã lỗi 1644), `app/core/errors.py` tự động bắt và trả về HTTP 422 kèm thông báo tiếng Việt."
- **Điểm nhấn:** Sơ đồ ERD trung tâm quanh `users` và `memories` (`oauth_accounts`, `password_reset_tokens`, `regions`, `media`, `trip_memories`, `memory_hashtags`, `admin_actions`).

### Slide 6 – Module 1: Tài khoản & Bảo mật (`accounts`)
- **Người trình bày:** Lê Minh Trí *(Ô 1 & Ô 3)* + Phạm Đình Thương *(Ô 2 & Ô 4)* · **Thời lượng:** 1 phút 15 giây
- **Lời dẫn (Lê Minh Trí – Đăng nhập & Đặt lại mật khẩu):**
  > "Tiếp theo em là Minh Trí xin trình bày phần xác thực mật khẩu của Module 1. Khi đăng nhập, mật khẩu được băm bằng `bcrypt` và chống dò mật khẩu theo `BR-15`: sai **5 lần trong 15 phút** sẽ tạm khóa 15 phút (HTTP 429), kết hợp `DUMMY_HASH` để chống tấn công đo thời gian. Với tính năng quên mật khẩu (`US-ACC-005`), bảng `password_reset_tokens` chỉ lưu mã băm **SHA-256**, hạn 30 phút, dùng một lần và trả cùng một thông báo dù email có tồn tại hay không để tránh lộ tài khoản."
- **Lời dẫn (Phạm Đình Thương – OAuth 2.0 & JWT `token_version`):**
  > "Em là Đình Thương xin bổ sung cơ chế OAuth và quản lý phiên. Ở `US-ACC-003` và `004`, khi đăng nhập Google hoặc Facebook, backend sinh chuỗi `state` lưu cookie `HttpOnly` để chống CSRF và chỉ tự gộp tài khoản cùng email khi Google đã xác thực email (`BR-18`). Đặc biệt ở cơ chế phiên (`BR-20`), JWT mang trường `tv` (`token_version`): khi người dùng đổi mật khẩu hoặc bị Admin khóa, `token_version` tăng lên cả ở code Python lẫn trigger `trg_users_bu`, giúp thu hồi toàn bộ JWT cũ ngay lập tức mà không cần thêm Redis."
- **Điểm nhấn:** 4 ô vuông chia rõ `BR-15`, `OAuth state + BR-18`, `SHA-256 BR-14`, và `JWT + token_version BR-20`.

### Slide 7 – Module 2: Ký ức, Bản đồ & Media (`memories`)
- **Người trình bày:** Phạm Đình Thương · **Thời lượng:** 1 phút 15 giây
- **Lời dẫn:**
  > "Module 2 là phân hệ lớn nhất với 11 User Stories và 29 API endpoints:
  > - **Về ghim vị trí:** Người dùng có thể tìm địa điểm qua Nominatim (cache 24h) hoặc nhấp trực tiếp lên bản đồ Leaflet để đổi tọa độ sang tên (cache ~11m). Toàn hệ thống đi qua `nominatim_gate.py` điều tiết đúng **1 yêu cầu/giây** (`BR-19`).
  > - **Về Media & Bảo mật:** Mỗi ký ức chứa tối đa **10 ảnh** (≤ 5 MB) và **1 video** `.mp4/.mov` (≤ 50 MB) hỗ trợ phát `HTTP 206 Range`. Trước khi lưu, `image_metadata.py` tự động gỡ bỏ EXIF/GPS/XMP mà không nén lại ảnh; và mọi link trả về trình duyệt đều phải có chữ ký **HMAC-SHA256** kèm hạn dùng (`sign_media_url`, `video_url`).
  > - **Về Chuyến đi & Hashtag AI:** Ký ức mặc định `private`, xóa mềm bằng `deleted_at`, cho phép gom vào Chuyến đi (`trips`) và gợi ý 4–6 hashtag bằng **Gemini 2.5 Flash** (tự fallback tách từ khóa cục bộ khi không có API key)."
- **Điểm nhấn:** Nêu bật con số `1 req/giây`, `10 ảnh / 1 video 206 Range`, `xóa EXIF/GPS`, `HMAC-SHA256`, `Gemini AI`.

### Slide 8 – Module 3: Khám phá, Lọc & Tìm kiếm (`explore`)
- **Người trình bày:** Lê Minh Trí · **Thời lượng:** 1 phút
- **Lời dẫn:**
  > "Module 3 phục vụ màn hình khám phá cộng đồng qua 5 API chính, mọi truy vấn đều đi qua hàm `public_query()` đảm bảo đủ 4 điều kiện `BR-03` (công khai, đang hiển thị, chưa xóa mềm, tác giả không bị khóa) và ẩn email tác giả theo `BR-12`.
  > - Khi tải bản đồ (`GET /api/explore/pins`), hệ thống lọc theo khung nhìn Bounding Box tối đa 500 ghim.
  > - Khi tạo hoặc sửa tọa độ ký ức, `region_lookup.py` tự ánh xạ ký ức vào **1 trong 34 tỉnh/thành** từ `provinces.geojson` bằng khung bao kết hợp thuật toán **Ray-Casting Point-in-Polygon** thuần Python (kể cả ghim sát bờ biển trong phạm vi ~5 km).
  > - Ngoài ra, người dùng có thể lọc nhiều hashtag theo phép **OR** (`BR-16`), tìm kiếm **FULLTEXT ngram** không phân biệt dấu theo điểm khớp, và lọc ký ức cá nhân theo năm/tháng/ngày."
- **Điểm nhấn:** 3 KPI hàng trên (`4 Điều kiện BR-03`, `34 Tỉnh/Thành GeoJSON`, `FULLTEXT ngram`).

### Slide 9 – Module 4: Quản trị & Kiểm duyệt (`admin`)
- **Người trình bày:** Nguyễn Tấn Du · **Thời lượng:** 50 giây
- **Lời dẫn:**
  > "Ở Module 4 Quản trị, mọi route dưới `/api/admin` đều bắt buộc đi qua `get_current_admin()` kiểm tra `role = 'admin'`, và dùng `SELECT ... FOR UPDATE` để tránh 2 quản trị viên xử lý đụng độ cùng một bản ghi.
  > Quản trị viên có thể xem thống kê hệ thống, ẩn/bỏ ẩn hoặc xóa mềm ký ức vi phạm, và khóa/mở khóa tài khoản. Mọi thao tác ẩn, xóa, khóa đều bắt buộc nhập lý do (`BR-10`), hệ thống chặn không cho Admin tự khóa chính mình (`BR-11`), và tự động ghi vết vào bảng nhật ký `admin_actions` — nơi mà 2 trigger `trg_admin_actions_bu` và `_bd` cấm tuyệt đối việc sửa hoặc xóa lịch sử."
- **Điểm nhấn:** Sơ đồ luồng 4 bước ngang ở nửa trên slide.

### Slide 10 – Quy trình Làm việc nhóm & Quản lý Chất lượng
- **Người trình bày:** Phương Vy · **Thời lượng:** 50 giây
- **Lời dẫn:**
  > "Em là Phương Vy xin trình bày quy trình phối hợp của nhóm. Nhóm tuân thủ chặt chẽ quy ước trong `CONTRIBUTING.md`: mỗi User Story tách một nhánh riêng từ `master` (như `du/us_adm_003`, `thuong/sprint3`, `vy/t05b590_ai_hashtags`, `tri/us_exp_001_004`), chạy pass toàn bộ `pytest` trước khi tạo Pull Request, và mọi thay đổi ở `app/core/`, `main.py` hay `schema.sql` phải có 2 thành viên duyệt. Nhờ quy ước tách router theo tính năng, dùng chung `build_response()`, `errors.py` và đồng bộ giờ `func.now()`, nhóm đã tích hợp trơn tru 75 commits và hơn 20 PR của 4 thành viên."
- **Điểm nhấn:** Bảng phân công 4 thành viên kèm số commits thực tế (`35`, `23`, `10`, `7`) và phạm vi code tương ứng.

### Slide 11 – Kết quả Kiểm thử Tự động (`pytest`) & Tích hợp 108 AC
- **Người trình bày:** Phương Vy · **Thời lượng:** 50 giây
- **Lời dẫn:**
  > "Về đảm bảo chất lượng, nhóm kiểm thử ở 2 tầng:
  > - Ở tầng tự động (`pytest`), toàn bộ **238/238 test case đều PASS (100%)** chỉ trong ~22 giây nhờ cấu hình `tests/conftest.py` chạy SQLite in-memory (`StaticPool`), ghi đè `get_db` và dùng `monkeypatch` tắt độ trễ Nominatim cũng như giả lập các API bên thứ ba theo đúng cấu trúc Given-When-Then của từng AC.
  > - Ở tầng kiểm thử tích hợp trên **MySQL 8 thật + trình duyệt Edge** (cả Desktop 1366×800 và Mobile giả lập Pixel 7), nhóm đạt **103/108 AC với 0 lỗi** và **46/46 ca giao diện đạt**. 5 AC còn lại là đăng nhập OAuth Google/Facebook thật cần khóa ứng dụng trong `.env`, phần logic và test giả lập đã đạt 100%."
- **Điểm nhấn:** 3 con số lớn `238 / 238`, `103 / 108 AC (0 lỗi)`, `46 / 46`.

### Slide 12 – Kịch bản Demo Trực tiếp (Live Demo Flow)
- **Người trình bày:** Phương Vy *(dẫn vào Demo)* · **Thời lượng:** 30 giây giới thiệu + 4–5 phút thực hành
- **Lời dẫn:**
  > "Sau đây nhóm xin phép chuyển sang phần trình diễn trực tiếp ứng dụng theo 6 bước từ góc nhìn Khách vãng lai → Người dùng đăng nhập (tạo ký ức kèm media, AI hashtag, chuyến đi) → đến Quản trị viên kiểm duyệt và thu hồi phiên đăng nhập."
- **Điểm nhấn:** Thực hiện ngay theo **Phần 3** bên dưới.

### Slide 13 – Hạn chế & Hướng phát triển (Giai đoạn 2)
- **Người trình bày:** Phương Vy *(sau khi kết thúc Demo)* · **Thời lượng:** 45 giây
- **Lời dẫn:**
  > "Sau Giai đoạn 1, nhóm nhìn nhận 4 điểm có thể nâng cấp ngay ở Giai đoạn 2 mà không phải viết lại kiến trúc lõi:
  > 1. Chuyển lưu trữ cục bộ `uploads/` sang **Cloudflare R2 / S3** kết hợp CDN dựa trên biên dịch vụ đã tách sẵn ở `image_media_service.py` và `video_media_service.py`.
  > 2. Mở rộng **Gemini Multimodal** đọc trực tiếp ảnh/video để gợi ý hashtag và tóm tắt nhật ký chuyến đi.
  > 3. Bổ sung tính năng **người dùng báo cáo vi phạm (User Report)** đưa vào hàng đợi kiểm duyệt.
  > 4. Thêm chế độ chia sẻ **nhóm bạn bè (`friends`)** cho phép cùng đóng góp ký ức vào một chuyến đi chung."

### Slide 14 – Tổng kết & Q&A
- **Người trình bày:** Phương Vy · **Thời lượng:** 20 giây
- **Lời dẫn:**
  > "Tóm lại, dự án **Bản đồ Ký ức** đã hoàn thiện trọn vẹn 26 User Stories, 62 API endpoints, bảo mật nhiều tầng cùng 238 test tự động pass 100%. Nhóm xin chân thành cảm ơn Quý Thầy/Cô đã lắng nghe và kính mời Hội đồng đặt câu hỏi phản biện ạ."

---

## PHẦN 3. KỊCH BẢN CHẠY LIVE DEMO CHI TIẾT (6 BƯỚC · ~4–5 PHÚT)

### Bước 1: Khách vãng lai khám phá bản đồ công khai (`http://127.0.0.1:8000/ban-do`)
- **Thao tác:**
  1. Ở cửa sổ trình duyệt 1 (chưa đăng nhập), chỉ vào các ghim đỏ đang hiển thị trên bản đồ Việt Nam (dữ liệu từ `seed_demo.py`: Hà Nội, Hạ Long, Sa Pa, Đà Nẵng, Hội An, Đà Lạt, Cần Thơ).
  2. Mở panel **Khám phá**, chọn bộ lọc **Tỉnh/Thành = Lâm Đồng** → Bản đồ thu hẹp chỉ còn ghim ở Đà Lạt (*Sương sớm Đà Lạt*, *Đồi chè Cầu Đất*; ký ức riêng tư *Chợ đêm Đà Lạt* không hiển thị theo `BR-03`).
  3. Nhấn chọn hashtag `#dalat` và `#phuot` → Kết hợp bộ lọc theo phép OR (`BR-16`).
  4. Xóa lọc tỉnh, gõ từ khóa không dấu **`ho guom`** vào ô tìm kiếm → Hiển thị ký ức *Chiều thu Hà Nội* tại *Hồ Gươm, Hà Nội* (tìm FULLTEXT ngram không dấu).
- **Câu chốt:** *"Khi chưa đăng nhập, khách chỉ xem được ký ức công khai, không xem được email tác giả (BR-12) và không thấy ký ức riêng tư."*

### Bước 2: Đăng nhập & Xem hồ sơ cá nhân (`/accounts/login.html` → `/accounts/profile.html`)
- **Thao tác:**
  1. Bấm **Đăng nhập**, nhập `an@example.com` / `Matkhau123`.
  2. Mở trang **Hồ sơ cá nhân**, cho Hội đồng xem 4 chỉ số thống kê từ `GET /api/users/me/stats` (số ký ức, công khai, chuyến đi, số tỉnh đã đi qua).
  3. *(Tùy chọn nhanh)* Cập nhật một đoạn giới thiệu ngắn hoặc tải thử ảnh đại diện (`anh_chup_1.jpg`) → Lưu thành công.
- **Câu chốt:** *"Mọi ảnh đại diện và ảnh ký ức tải lên đều được xóa sạch siêu dữ liệu EXIF/GPS bằng `strip_metadata()` để bảo vệ vị trí chụp gốc của người dùng."*

### Bước 3: Ghim Ký ức mới & Đính kèm Ảnh / Video có chữ ký HMAC
- **Thao tác:**
  1. Quay lại `/ban-do`, bấm **Tạo ký ức** → Nhấp trực tiếp một điểm trên bản đồ (ví dụ khu vực **Hồ Tuyền Lâm, Đà Lạt**).
  2. Hệ thống tự động gọi `GET /api/geocode/reverse` điền sẵn tên địa điểm (nhờ `nominatim_gate.py` giữ nhịp 1 req/giây) và khi lưu sẽ tự gán `region_id = Lâm Đồng` nhờ `region_lookup.py` (`provinces.geojson`).
  3. Nhập Tiêu đề: **`Hoàng hôn Hồ Tuyền Lâm`**, Ngày: chọn ngày hôm nay (chú ý ngày tương lai sẽ bị chặn theo `BR-05`), Nội dung ngắn. Để mặc định **Riêng tư** và bấm Lưu.
  4. Trong phần chi tiết ký ức vừa tạo, tải lên 2 ảnh (`anh_chup_1.jpg`, `anh_chup_2.png`) và 1 video (`video_ky_niem.mp4`).
  5. Bấm phát video (tua nhanh thanh thời gian để chứng minh hỗ trợ `HTTP 206 Range`) và mở nhanh DevTools (hoặc rê chuột vào ảnh) cho Hội đồng thấy đường dẫn `/api/media/{id}?exp=...&sig=...` có chữ ký HMAC, không lộ thư mục lưu trữ `uploads/`.

### Bước 4: Gợi ý Hashtag AI & Chuyển sang Công khai
- **Thao tác:**
  1. Trên form chi tiết/chỉnh sửa ký ức vừa tạo, bấm nút **Gợi ý Hashtag** (`POST /api/memories/suggest-hashtags`).
  2. Chọn 2–3 hashtag gợi ý (ví dụ `#dalat`, `#hotuyenlam`, `#hoanghon`) + gõ thêm 1 hashtag thủ công `#kyniem2026` rồi lưu.
  3. Bấm chuyển trạng thái từ **Riêng tư** sang **Công khai** (`PATCH /api/memories/{id}/visibility`).
- **Câu chốt:** *"Chỉ sau khi người dùng chủ động chuyển sang Công khai, ghim mới xuất hiện trên bản đồ cộng đồng."*

### Bước 5: Gom vào Chuyến đi & Lọc ký ức cá nhân theo Thời gian
- **Thao tác:**
  1. Chuyển sang tab **Chuyến đi**, mở chuyến đi có sẵn **`Đà Lạt tháng 10`**.
  2. Thêm ký ức *Hoàng hôn Hồ Tuyền Lâm* vừa tạo vào chuyến đi → Danh sách tự sắp xếp tăng dần theo ngày (`memory_date`) và thời điểm tạo.
  3. Chuyển sang tab **Của tôi**, thử bộ lọc theo năm (`2025` hoặc `2026`) để thấy hệ thống lọc ký ức cá nhân kèm cả ký ức riêng tư.

### Bước 6: Quản trị, Kiểm duyệt & Thu hồi Phiên tức thì (`BR-20`)
- **Thao tác:**
  1. Chuyển sang **Cửa sổ 2 (Ẩn danh)**, đăng nhập quản trị viên: `admin@example.com` / `Admin12345`, mở trang **`/admin/`**.
  2. Chỉ nhanh 6 thẻ thống kê tổng quan ở đầu trang (`GET /api/admin/stats`).
  3. Ở tab **Ký ức**, tìm ký ức vừa công khai (*Hoàng hôn Hồ Tuyền Lâm*) → Bấm **Ẩn**, nhập lý do: **`Kiểm thử ẩn nội dung vi phạm quy định`**.
  4. Quay lại Cửa sổ 1 (của User An), reload trang: ký ức đó biến mất khỏi bản đồ công khai, nhưng trong tab **Của tôi** của An vẫn thấy kèm nhãn *"Đã bị quản trị viên ẩn"*.
  5. Quay lại Cửa sổ 2 (Admin), chuyển sang tab **Tài khoản**, tìm tài khoản **`an@example.com`**, bấm **Khóa**, nhập lý do: **`Demo thu hồi phiên tức thì BR-20`**.
  6. Quay lại Cửa sổ 1 (User An), thử bấm vào **Hồ sơ** hoặc tạo ký ức → API lập tức trả lỗi tài khoản bị khóa và đăng xuất ngay lập tức do `token_version` đã tăng!
  7. Cuối cùng, tại trang Admin mở tab **Nhật ký thao tác** (`admin_actions`) để cho Hội đồng thấy toàn bộ lịch sử ẩn bài, khóa tài khoản kèm tên admin, thời gian và lý do đã được ghi nhận bất biến. *(Sau demo có thể bấm **Mở khóa** lại cho An nếu Hội đồng muốn kiểm tra thêm).*

---

## PHẦN 4. BỘ CÂU HỎI PHẢN BIỆN HỘI ĐỒNG THƯỜNG GẶP (FAQ)

### Câu 1: Vì sao dùng JWT (stateless) mà khi Admin khóa tài khoản hoặc User đổi mật khẩu lại thu hồi được phiên ngay lập tức?
- **Trả lời theo code thực tế:** Trong `users` có cột `token_version` (`BR-20`). Khi cấp token (`app/core/security.py:create_access_token`), backend nhúng `tv = user.token_version` vào payload JWT. Ở mỗi request cần xác thực, `app/modules/accounts/deps.py:get_current_user_optional` truy vấn User và so sánh `user.token_version != payload.get("tv")`, đồng thời `get_current_user` chặn `user.status == "locked"`. Khi đổi/đặt lại mật khẩu hoặc khóa tài khoản, cả Python và trigger MySQL `trg_users_bu` đều tăng `token_version` lên +1 nên mọi JWT cũ bị vô hiệu ngay.

### Câu 2: Làm thế nào đảm bảo ảnh của ký ức Riêng tư không bị người lạ đoán ID (`/api/media/12`) để xem trộm?
- **Trả lời theo code thực tế:** Toàn bộ ảnh và video trả về qua `sign_media_url()` (`app/core/security.py`) và `video_url()` (`video_media_service.py`) đều gắn thêm timestamp hết hạn `exp` và chữ ký **HMAC-SHA256** (`sig`). Khi nhận request `GET /api/media/{id}` hoặc `/stream`, backend kiểm tra chữ ký `hmac.compare_digest` trước, sau đó tiếp tục kiểm tra quyền xem ký ức (chỉ chủ sở hữu mới xem được ký ức `private` hoặc `hidden`). Ngoài ra ảnh riêng tư gắn header `Cache-Control: private, no-store`.

### Câu 3: Hệ thống xử lý thế nào để ảnh người dùng tải lên không làm lộ vị trí chụp (EXIF/GPS)?
- **Trả lời theo code thực tế:** Trong `app/modules/memories/services/image_metadata.py`, hàm `strip_metadata()` đọc cấu trúc byte nhị phân của file **JPEG** (loại bỏ segment `APP1` EXIF/XMP, `APP3..APP15`, `COM`, giữ lại `APP2` ICC profile), **PNG** (bỏ chunk `eXIf`, `tEXt`, `zTXt`, `iTXt`, `tIME`) và **WebP** (bỏ chunk `EXIF`, `XMP ` và xóa cờ tương ứng trong `VP8X`). Nhờ xử lý trực tiếp theo cấu trúc container, ảnh được sạch GPS mà **không phải nén lại**, không làm giảm chất lượng ảnh và không cần phụ thuộc Pillow.

### Câu 4: Tại sao đã validate bằng Pydantic/FastAPI ở Backend mà nhóm vẫn viết thêm 11 Trigger trong MySQL?
- **Trả lời theo code thực tế:** Đây là nguyên tắc **phòng thủ theo chiều sâu (Defense in Depth)**. Nếu một router mới viết quên kiểm tra quy tắc nghiệp vụ (ví dụ thêm ký ức của người khác vào chuyến đi, gán quá 10 ảnh, ngày ký ức ở tương lai, hoặc xóa nhật ký `admin_actions`), trigger MySQL sẽ phát `SIGNAL SQLSTATE '45000'` (mã 1644). Handler `DBAPIError` trong `app/core/errors.py` tự động bắt mã `1644` và trả về HTTP `422` cùng thông báo tiếng Việt chuẩn của trigger.

### Câu 5: Nhóm ánh xạ tọa độ `(lat, lng)` sang 34 tỉnh/thành bằng cách nào? Nếu ghim sát biển thì sao?
- **Trả lời theo code thực tế:** Trong `app/modules/explore/region_lookup.py`, nhóm nạp ranh giới 34 tỉnh/thành từ `provinces.geojson` (~200 KB) vào cache bộ nhớ (`@lru_cache`). Khi có tọa độ mới, hàm `province_slug()` lọc sơ bộ theo khung bao (Bounding Box) rồi kiểm tra **Ray-Casting Point-in-Polygon** (`_in_polygon`, có xét đa giác lỗ). Nếu điểm nằm sát bờ biển hoặc biên giới bị lệch nhẹ ra ngoài đa giác rút gọn, hàm tính khoảng cách tới từng đoạn biên (`_segment_distance`) để gán tỉnh gần nhất trong bán kính `NEAR_DEGREES = 0.05` (~5 km); ở nước ngoài thì trả `None` (`region_id = NULL`). Thuật toán viết bằng Python thuần nên không cần cài thư viện C nặng như `shapely`/`GDAL`.

### Câu 6: Vì sao schema dùng tính năng riêng của MySQL 8 (Trigger, `FULLTEXT ngram`, `utf8mb4_0900`) nhưng 238 test `pytest` vẫn chạy được trên SQLite chỉ trong ~22 giây?
- **Trả lời theo code thực tế:** Trong `tests/conftest.py`, nhóm dùng SQLite in-memory (`StaticPool`) và đăng ký `@compiles(BigInteger, "sqlite")` để biên dịch khóa chính tự tăng sang `INTEGER`. Với truy vấn tìm kiếm `FULLTEXT` trong `app/modules/explore/router.py`, hàm `public_query()` kiểm tra `db.get_bind().dialect.name == "mysql"` để chạy `MATCH ... AGAINST` trên MySQL thật và tự chuyển sang `ILIKE` khi chạy trên SQLite. Riêng các tính năng đặc thù MySQL (11 Trigger, `FULLTEXT ngram`, lệch múi giờ DB) được kiểm thử lại đầy đủ trong bộ kiểm thử tích hợp 108 AC tại `tests/kiem_thu_tich_hop/` trên MySQL 8 thật.
