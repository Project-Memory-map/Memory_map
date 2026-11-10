"""M3 – Khám phá, lọc, tìm kiếm.

Giao diện đã có sẵn: panel "Khám phá" nằm trong shared/ui/map.html; xử lý ở js/explore.js.
Các API dưới đây là việc cần làm.

| Task       | Phương thức + đường dẫn                                          | Gọi từ      |
|------------|------------------------------------------------------------------|-------------|
| US-EXP-001 | GET /api/explore/pins?south=&west=&north=&east=   (ghim đỏ)      | explore.js  |
| US-EXP-001 | GET /api/explore/overview                                        | explore.js, landing.js |
| US-EXP-002 | GET /api/explore/hashtags         (hashtag phổ biến)             | explore.js  |
| US-EXP-003 | GET /api/explore/regions          (34 tỉnh/thành)                | explore.js  |
| US-EXP-002/003/004 | GET /api/explore/memories?q=&hashtags=&region=&page=     | explore.js, landing.js |

Ký ức công khai lấy từ view v_public_memories (database/schema.sql Phần 6) là đủ điều kiện BR-03.
Danh sách tỉnh/thành: chạy database/seed_regions.sql.
Bảng dùng: regions (models.py) + memories, hashtags của module memories.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/explore", tags=["M3 - Khám phá"])

# TODO: thêm các endpoint theo bảng trên
