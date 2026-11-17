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
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ForbiddenException, NotFoundException, ValidationException
from app.core.response import build_response
from app.modules.accounts.deps import get_current_user, get_current_user_optional
from app.modules.accounts.models import User
from app.modules.memories.models import Memory, Trip, TripMemory

router = APIRouter(tags=["M2 - Ký ức"])


# ----- helper -----
def load_memory(db: Session, memory_id: int) -> Memory:
    memory = db.get(Memory, memory_id)
    if memory is None or memory.deleted_at is not None:
        raise NotFoundException("Không tìm thấy ký ức")
    return memory


def serialize_memory(db: Session, memory: Memory, viewer: User | None) -> dict:
    is_owner = viewer is not None and viewer.id == memory.user_id
    links = sorted(memory.hashtag_links, key=lambda link: link.hashtag.name)
    trips = []
    if is_owner:
        rows = db.execute(
            select(Trip.id, Trip.name)
            .join(TripMemory, TripMemory.trip_id == Trip.id)
            .where(TripMemory.memory_id == memory.id)
            .order_by(Trip.name)
        ).all()
        trips = [{"id": row.id, "name": row.name} for row in rows]
    return {
        "id": memory.id,
        "title": memory.title,
        "content": memory.content,
        "memory_date": memory.memory_date,
        "place_name": memory.place_name,
        "latitude": memory.latitude,
        "longitude": memory.longitude,
        "visibility": memory.visibility,
        "hidden_by_admin": memory.status == "hidden",
        "is_owner": is_owner,
        "region": {"id": memory.region.id, "name": memory.region.name} if memory.region else None,
        "author": {
            "id": memory.author.id,
            "display_name": memory.author.display_name,
            "avatar_url": memory.author.avatar_path,
        },
        "hashtags": [link.hashtag.name for link in links],
        "hashtag_sources": {link.hashtag.name: link.source for link in links},
        "media": [
            {
                "id": item.id,
                "type": item.media_type,
                "url": f"/api/media/{item.id}",
                "thumb_url": f"/api/media/{item.id}?thumb=1" if item.thumb_path else None,
            }
            for item in memory.media
        ],
        "trips": trips,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
    }


# ----- US-MEM-005: xem chi tiết ký ức -----
@router.get("/api/memories/{memory_id}")
def get_memory(
    memory_id: int,
    request: Request,
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_current_user_optional),
):
    memory = load_memory(db, memory_id)
    is_owner = viewer is not None and viewer.id == memory.user_id
    if not is_owner and (memory.visibility != "public" or memory.status == "hidden"):
        raise NotFoundException("Không tìm thấy ký ức")
    return build_response(200, "Thành công", request, data=serialize_memory(db, memory, viewer))


# ----- US-MEM-006: sửa nội dung ký ức -----
@router.patch("/api/memories/{memory_id}")
def update_memory(
    memory_id: int,
    request: Request,
    title: str | None = Form(None),
    content: str | None = Form(None),
    place_name: str | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    memory_date: date | None = Form(None),
    visibility: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    memory = load_memory(db, memory_id)
    if memory.user_id != user.id:
        raise ForbiddenException("Bạn không có quyền sửa ký ức này")

    if title is not None:
        title = title.strip()
        if not title:
            raise ValidationException("Vui lòng nhập tiêu đề")
        if len(title) > 200:
            raise ValidationException("Tiêu đề tối đa 200 ký tự")
        memory.title = title
    if content is not None:
        memory.content = content.strip()
    if place_name is not None:
        place_name = place_name.strip()
        if not place_name:
            raise ValidationException("Vui lòng nhập tên địa điểm")
        memory.place_name = place_name[:255]
    if (latitude is None) != (longitude is None):
        raise ValidationException("Cần gửi đủ cả vĩ độ và kinh độ")
    if latitude is not None:
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValidationException("Tọa độ không hợp lệ")
        memory.latitude, memory.longitude = latitude, longitude
    if memory_date is not None:
        if memory_date > date.today():
            raise ValidationException("Ngày không được ở tương lai")
        memory.memory_date = memory_date
    if visibility is not None:
        if visibility not in ("private", "public"):
            raise ValidationException("Chế độ hiển thị không hợp lệ")
        memory.visibility = visibility

    db.commit()
    db.refresh(memory)
    return build_response(200, "Đã cập nhật ký ức", request, data=serialize_memory(db, memory, user))