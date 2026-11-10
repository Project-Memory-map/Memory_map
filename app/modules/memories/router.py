"""M2 – Ký ức, ảnh/video, chuyến đi, hashtag.

Giao diện đã có sẵn: panel "Của tôi", panel "Chuyến đi" và form ký ức nằm trong
shared/ui/map.html; xử lý ở js/memories.js và js/trips.js. Các API dưới đây là việc cần làm.

| Task           | Phương thức + đường dẫn                               | Gọi từ             |
|----------------|-------------------------------------------------------|--------------------|
| US-MEM-001     | GET    /api/geocode?q=            (tìm địa điểm)      | shell.js, memories.js |
| US-MEM-002     | GET    /api/geocode/reverse?lat=&lng=                 | memories.js        |
| US-MEM-001/002 | POST   /api/memories              (multipart)         | memories.js        |
| US-MEM-003/004 | (ảnh/video gửi kèm POST/PATCH /api/memories)          | memories.js        |
| US-MEM-003/004 | GET    /api/media/{id}?...&exp=&sig=  (URL có chữ ký)  | memories.js        |
| US-MEM-005     | GET    /api/memories/{id}                             | memories.js        |
| US-MEM-006     | PATCH  /api/memories/{id}                             | memories.js        |
| US-MEM-007     | DELETE /api/memories/{id}                             | memories.js        |
| US-MEM-008     | PATCH  /api/memories/{id}/visibility                  | memories.js        |
| US-MEM-010     | POST   /api/memories/suggest-hashtags                 | memories.js        |
| US-EXP-005     | GET    /api/memories/mine  (+ /pins, /hashtags, /years) | memories.js      |
| US-MEM-009     | GET/POST /api/trips · GET/PATCH/DELETE /api/trips/{id} | trips.js          |
| US-MEM-009     | POST /api/trips/{id}/memories · DELETE /api/trips/{id}/memories/{memory_id} | trips.js |

Bảng dùng: memories, media, trips, trip_memories, hashtags, memory_hashtags (models.py).
Trigger trong database/schema.sql đã chặn: ngày tương lai, quá 10 ảnh / 1 video / 10 hashtag,
thêm ký ức người khác vào chuyến đi. Lỗi trigger được core/errors.py trả về mã 422 kèm câu thông báo.
"""
from fastapi import APIRouter

router = APIRouter(tags=["M2 - Ký ức"])

# TODO: thêm các endpoint theo bảng trên
