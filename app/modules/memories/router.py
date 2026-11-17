"""M2 – Xem chi tiết, sửa và xóa ký ức."""

import math
import re
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Form, Query, Request
from sqlalchemy import delete, extract, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ForbiddenException, NotFoundException, ValidationException
from app.core.response import build_response
from app.modules.accounts.deps import get_current_user, get_current_user_optional
from app.modules.accounts.models import User
from app.modules.memories.models import Hashtag, Memory, MemoryHashtag, Trip, TripMemory

router = APIRouter(tags=["M2 - Ký ức"])


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
        "region": (
            {"id": memory.region.id, "name": memory.region.name}
            if memory.region else None
        ),
        "author": {
            "id": memory.author.id,
            "display_name": memory.author.display_name,
            "avatar_url": memory.author.avatar_path,
        },
        "hashtags": [link.hashtag.name for link in links],
        "hashtag_sources": {
            link.hashtag.name: link.source for link in links
        },
        "media": [
            {
                "id": item.id,
                "type": item.media_type,
                "url": f"/api/media/{item.id}",
                "thumb_url": (
                    f"/api/media/{item.id}?thumb=1"
                    if item.thumb_path else None
                ),
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
    author_locked = (
        memory.author is not None
        and memory.author.status == "locked"
    )

    if not is_owner and (
        memory.visibility != "public"
        or memory.status == "hidden"
        or author_locked
    ):
        raise NotFoundException("Không tìm thấy ký ức")

    return build_response(
        200,
        "Thành công",
        request,
        data=serialize_memory(db, memory, viewer),
    )


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

    return build_response(
        200,
        "Đã cập nhật ký ức",
        request,
        data=serialize_memory(db, memory, user),
    )


# ----- US-MEM-007: xóa ký ức -----
@router.delete("/api/memories/{memory_id}")
def delete_memory(
    memory_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memory = load_memory(db, memory_id)

    if memory.user_id != user.id:
        raise ForbiddenException("Bạn không có quyền xóa ký ức này")

    try:
        memory.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.execute(
            delete(TripMemory).where(TripMemory.memory_id == memory.id)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return build_response(
        200,
        "Đã xóa ký ức",
        request,
        data={"id": memory_id},
    )