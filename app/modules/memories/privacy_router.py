"""US-MEM-008 – Đổi chế độ riêng tư hoặc công khai của ký ức (FR-2.6)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ForbiddenException, NotFoundException, ValidationException
from app.core.response import build_response
from app.core.security import sign_media_url
from app.modules.accounts.deps import get_current_user, get_current_user_optional
from app.modules.accounts.models import User
from app.modules.memories import router as memories_module_router
from app.modules.memories.models import Memory, Trip, TripMemory
from app.modules.memories.services.video_media_service import video_url

router = APIRouter(tags=["M2 - Ký ức"])

VALID_VISIBILITIES = ("private", "public")


class VisibilityUpdateRequest(BaseModel):
    visibility: str | None = None

    @field_validator("visibility", mode="before")
    @classmethod
    def _validate_visibility(cls, value: object) -> str:
        if not isinstance(value, str) or value not in VALID_VISIBILITIES:
            raise ValueError("Chế độ hiển thị không hợp lệ")
        return value


def load_memory(db: Session, memory_id: int) -> Memory:
    memory = db.get(Memory, memory_id)
    if memory is None or memory.deleted_at is not None:
        raise NotFoundException("Không tìm thấy ký ức")
    return memory


def serialize_memory(db: Session, memory: Memory, viewer: User | None) -> dict:
    shared_serializer = getattr(memories_module_router, "serialize_memory", None)
    if callable(shared_serializer):
        return shared_serializer(db, memory, viewer)

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

    media_items = []
    for item in memory.media:
        if item.media_type == "video":
            url = video_url(item.id, item.file_path)
            thumb_url = None
        else:
            url = sign_media_url(item.id)
            thumb_url = url
        media_items.append(
            {
                "id": item.id,
                "type": item.media_type,
                "url": url,
                "thumb_url": thumb_url,
            }
        )

    return {
        "id": memory.id,
        "title": memory.title,
        "content": memory.content,
        "memory_date": memory.memory_date,
        "place_name": memory.place_name,
        "latitude": float(memory.latitude),
        "longitude": float(memory.longitude),
        "visibility": memory.visibility,
        "hidden_by_admin": memory.status == "hidden",
        "is_owner": is_owner,
        "region": {"id": memory.region.id, "name": memory.region.name} if memory.region else None,
        "author": (
            {
                "id": memory.author.id,
                "display_name": memory.author.display_name,
                "avatar_url": memory.author.avatar_path,
            }
            if memory.author
            else None
        ),
        "hashtags": [link.hashtag.name for link in links],
        "hashtag_sources": {link.hashtag.name: link.source for link in links},
        "media": media_items,
        "trips": trips,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
    }


@router.patch("/api/memories/{memory_id}/visibility")
def update_memory_visibility(
    memory_id: int,
    payload: VisibilityUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.visibility not in VALID_VISIBILITIES:
        raise ValidationException("Chế độ hiển thị không hợp lệ")

    memory = load_memory(db, memory_id)
    if memory.user_id != current_user.id:
        raise ForbiddenException("Bạn không có quyền sửa ký ức này")

    memory.visibility = payload.visibility
    memory.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(memory)

    message = (
        "Ký ức đã chuyển sang công khai"
        if memory.visibility == "public"
        else "Ký ức đã chuyển về riêng tư"
    )
    return build_response(
        200,
        message,
        request,
        data=serialize_memory(db, memory, current_user),
    )


@router.get("/api/memories/{memory_id}")
def get_memory_detail(
    memory_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    memory = load_memory(db, memory_id)
    is_owner = current_user is not None and current_user.id == memory.user_id
    author_active = memory.author is None or memory.author.status == "active"
    if not is_owner and (
        memory.visibility != "public"
        or memory.status != "active"
        or not author_active
    ):
        raise NotFoundException("Không tìm thấy ký ức")
    return build_response(
        200,
        "Thành công",
        request,
        data=serialize_memory(db, memory, current_user),
    )


@router.get("/api/explore/pins")
def list_public_pins(
    request: Request,
    south: float | None = Query(None, ge=-90, le=90),
    west: float | None = Query(None, ge=-180, le=180),
    north: float | None = Query(None, ge=-90, le=90),
    east: float | None = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db),
):
    stmt = (
        select(
            Memory.id,
            Memory.title,
            Memory.place_name,
            Memory.memory_date,
            Memory.latitude,
            Memory.longitude,
            User.display_name.label("author_name"),
        )
        .join(User, User.id == Memory.user_id)
        .where(
            Memory.visibility == "public",
            Memory.status == "active",
            Memory.deleted_at.is_(None),
            User.status == "active",
        )
    )
    if None not in (south, west, north, east):
        lng_cond = (
            Memory.longitude.between(west, east)
            if west <= east
            else or_(Memory.longitude >= west, Memory.longitude <= east)
        )
        stmt = stmt.where(Memory.latitude.between(south, north), lng_cond)

    rows = db.execute(
        stmt.order_by(Memory.memory_date.desc(), Memory.id.desc()).limit(500)
    ).mappings().all()
    data = [
        {
            "id": row["id"],
            "title": row["title"],
            "place_name": row["place_name"],
            "memory_date": row["memory_date"],
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "author_name": row["author_name"],
        }
        for row in rows
    ]
    return build_response(200, "Lấy danh sách ghim công khai thành công", request, data=data)
