# app/shared/js/

Xử lý phía trình duyệt dùng chung, phục vụ ở `/js/...`.

| File | Công dụng |
|---|---|
| `api.js` | Đối tượng `Api`: gọi API backend, tự gắn JWT, đọc khung phản hồi `{statusCode, message, error, data}`. **Mọi trang đều dùng** |
| `ui.js` | Đối tượng `UI`: tạo phần tử an toàn bằng `UI.el()` (chỉ dùng `textContent`, BR-21), toast, hộp thoại xác nhận, định dạng ngày, sự kiện `UI.emit/on`. **Mọi trang đều dùng** |
| `map.js` | Đối tượng `MemoryMap`: bản đồ Leaflet, ghim xanh (của tôi) / đỏ (cộng đồng), nhấp đúp hoặc nhấn giữ để chọn vị trí. Dùng ở `map.html` |
| `shell.js` | Đối tượng `Shell`: khung trang bản đồ, gồm thanh bên + tab, ngăn kéo bên phải, ô tìm địa điểm, bật/tắt lớp bản đồ, liên kết `?memory=` / `?trip=`. Dùng ở `map.html` |
| `landing.js` | Trang mở đầu: đổi nút theo trạng thái đăng nhập, tải ký ức công khai mới nhất. Dùng ở `index.html` |

> Khi thêm, sửa hoặc xóa file trong thư mục này, nhớ cập nhật bảng trên.
