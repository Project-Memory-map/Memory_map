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
from pydantic import BaseModel
from typing import Optional
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.accounts.models import User
from app.modules.memories.models import Memory
from app.modules.accounts.deps import get_current_user

# Định nghĩa Schema trực tiếp tại đây cho US-MEM-006
class MemoryUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location_name: Optional[str] = None
    is_public: Optional[bool] = None

# API US-MEM-006: Sửa nội dung ký ức theo đúng bảng quy ước của nhóm (PATCH /api/memories/{id})
@router.patch("/api/memories/{id}")
def update_memory_content(
    id: int,
    payload: MemoryUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)  # Hàm lấy user hiện tại đã có sẵn trong file hoặc deps
):
    # 1. Tìm ký ức theo id trong database
    memory = db.query(Memory).filter(Memory.id == id).first()
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy ký ức"
        )

    # 2. Kiểm tra quyền sở hữu (FR-2.5: Chỉ chủ sở hữu được sửa)
    if getattr(memory, "user_id", None) != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền sửa ký ức này"
        )

    # 3. Cập nhật các trường dữ liệu nếu có truyền lên
    if payload.title is not None:
        memory.title = payload.title.strip()
    if payload.description is not None:
        memory.description = payload.description.strip()
    if payload.location_name is not None:
        memory.location_name = payload.location_name.strip()
    if payload.is_public is not None:
        memory.is_public = payload.is_public

    db.commit()
    db.refresh(memory)

    return {
        "message": "Cập nhật ký ức thành công",
        "data": memory
    }