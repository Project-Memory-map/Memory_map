"""M4 – Quản trị.

Giao diện đã có sẵn: ui/index.html (trang /admin/); xử lý ở js/admin.js.
Các API dưới đây là việc cần làm. Mọi route phải kiểm tra tài khoản có role = 'admin'.

| Task       | Phương thức + đường dẫn                                   | Gọi từ    |
|------------|-----------------------------------------------------------|-----------|
| US-ADM-001 | GET  /api/admin/stats                                     | admin.js  |
| US-ADM-001 | GET  /api/admin/memories?q=                               | admin.js  |
| US-ADM-001 | POST /api/admin/memories/{id}/hide · /unhide              | admin.js  |
| US-ADM-002 | POST /api/admin/memories/{id}/delete                      | admin.js  |
| US-ADM-003 | GET  /api/admin/users?q=                                  | admin.js  |
| US-ADM-003 | POST /api/admin/users/{id}/lock · /unlock                 | admin.js  |
| US-ADM-001→003 | GET /api/admin/actions          (nhật ký thao tác)    | admin.js  |

Bảng dùng: admin_actions (models.py) + memories, users.
Trigger đã chặn: không có lý do (BR-10), admin tự khóa mình (BR-11), sửa/xóa nhật ký.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/admin", tags=["M4 - Quản trị"])

# TODO: thêm các endpoint theo bảng trên
