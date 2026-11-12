"""US-MEM-009 – Tạo chuyến đi và thêm ký ức vào chuyến đi (FR-2.7)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.core.response import build_response
from app.core.security import sign_media_url
from app.modules.accounts.deps import get_current_user
from app.modules.accounts.models import User
from app.modules.memories.models import Memory, Trip, TripMemory
from app.modules.memories.privacy_router import serialize_memory

router = APIRouter(tags=["M2 - Ký ức & Chuyến đi"])

MAX_TRIP_NAME_LENGTH = 150
MAX_TRIP_DESC_LENGTH = 500


def _validate_trip_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Vui lòng nhập tên chuyến đi")
    cleaned = value.strip()
    if len(cleaned) > MAX_TRIP_NAME_LENGTH:
        raise ValueError(f"Tên chuyến đi tối đa {MAX_TRIP_NAME_LENGTH} ký tự")
    return cleaned


def _validate_trip_description(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Mô tả chuyến đi không hợp lệ")
    cleaned = value.strip()
    if len(cleaned) > MAX_TRIP_DESC_LENGTH:
        raise ValueError(f"Mô tả chuyến đi tối đa {MAX_TRIP_DESC_LENGTH} ký tự")
    return cleaned or None


class TripCreateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    memory_ids: list[int] | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _check_name(cls, value: object) -> str:
        return _validate_trip_name(value)

    @field_validator("description", mode="before")
    @classmethod
    def _check_description(cls, value: object) -> str | None:
        return _validate_trip_description(value)


class TripUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _check_name(cls, value: object) -> str:
        return _validate_trip_name(value)

    @field_validator("description", mode="before")
    @classmethod
    def _check_description(cls, value: object) -> str | None:
        return _validate_trip_description(value)


class TripAddMemoriesRequest(BaseModel):
    memory_ids: list[int] | None = None
    memory_id: int | None = None


def _load_owned_trip(db: Session, trip_id: int, current_user: User) -> Trip:
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise NotFoundException("Không tìm thấy chuyến đi")
    if trip.user_id != current_user.id:
        raise ForbiddenException("Bạn không có quyền thao tác trên chuyến đi này")
    return trip


def _load_trip_memories(db: Session, trip_id: int) -> list[Memory]:
    return list(
        db.scalars(
            select(Memory)
            .join(TripMemory, TripMemory.memory_id == Memory.id)
            .where(TripMemory.trip_id == trip_id, Memory.deleted_at.is_(None))
            .order_by(Memory.memory_date.asc(), Memory.created_at.asc(), Memory.id.asc())
        ).all()
    )


def _serialize_trip_memory(db: Session, memory: Memory, viewer: User) -> dict:
    item = serialize_memory(db, memory, viewer)
    first_image = next((m for m in memory.media if m.media_type == "image"), None)
    item["cover_url"] = sign_media_url(first_image.id) if first_image is not None else None
    item["has_video"] = any(m.media_type == "video" for m in memory.media)
    item["status"] = memory.status
    return item


def _serialize_trip_summary(db: Session, trip: Trip) -> dict:
    memories = _load_trip_memories(db, trip.id)
    return {
        "id": trip.id,
        "name": trip.name,
        "description": trip.description,
        "memory_count": len(memories),
        "start_date": memories[0].memory_date if memories else None,
        "end_date": memories[-1].memory_date if memories else None,
        "created_at": trip.created_at,
        "updated_at": trip.updated_at,
    }


def _serialize_trip_detail(db: Session, trip: Trip, viewer: User) -> dict:
    memories = _load_trip_memories(db, trip.id)
    return {
        "id": trip.id,
        "name": trip.name,
        "description": trip.description,
        "memory_count": len(memories),
        "start_date": memories[0].memory_date if memories else None,
        "end_date": memories[-1].memory_date if memories else None,
        "memories": [_serialize_trip_memory(db, mem, viewer) for mem in memories],
        "created_at": trip.created_at,
        "updated_at": trip.updated_at,
    }


def _attach_memories_to_trip(
    db: Session,
    trip: Trip,
    memory_ids: list[int],
    current_user: User,
) -> None:
    seen: list[int] = []
    for raw_id in memory_ids:
        if not isinstance(raw_id, int) or raw_id <= 0:
            raise BadRequestException("Danh sách ký ức không hợp lệ")
        if raw_id not in seen:
            seen.append(raw_id)

    memories_to_link: list[Memory] = []
    for mid in seen:
        memory = db.get(Memory, mid)
        if memory is None or memory.deleted_at is not None:
            raise NotFoundException("Không tìm thấy ký ức")
        if memory.user_id != current_user.id:
            raise ForbiddenException("Chỉ thêm được ký ức của bạn")
        memories_to_link.append(memory)

    existing_ids = set(
        db.scalars(
            select(TripMemory.memory_id).where(TripMemory.trip_id == trip.id)
        ).all()
    )
    for memory in memories_to_link:
        if memory.id not in existing_ids:
            db.add(TripMemory(trip_id=trip.id, memory_id=memory.id))


@router.get("/api/trips")
def list_trips(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trips = db.scalars(
        select(Trip)
        .where(Trip.user_id == current_user.id)
        .order_by(Trip.created_at.desc(), Trip.id.desc())
    ).all()
    return build_response(
        200,
        "Đã tải danh sách chuyến đi",
        request,
        data=[_serialize_trip_summary(db, trip) for trip in trips],
    )


@router.post("/api/trips", status_code=201)
def create_trip(
    payload: TripCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.name or not payload.name.strip():
        raise ValidationException("Vui lòng nhập tên chuyến đi")

    trip = Trip(
        user_id=current_user.id,
        name=payload.name.strip(),
        description=payload.description,
    )
    db.add(trip)
    db.flush()

    if payload.memory_ids:
        _attach_memories_to_trip(db, trip, payload.memory_ids, current_user)

    db.commit()
    db.refresh(trip)
    return build_response(
        201,
        "Đã tạo chuyến đi",
        request,
        data=_serialize_trip_detail(db, trip, current_user),
    )


@router.get("/api/trips/{trip_id}")
def get_trip(
    trip_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trip = _load_owned_trip(db, trip_id, current_user)
    return build_response(
        200,
        "Đã tải chi tiết chuyến đi",
        request,
        data=_serialize_trip_detail(db, trip, current_user),
    )


@router.patch("/api/trips/{trip_id}")
@router.put("/api/trips/{trip_id}")
def update_trip(
    trip_id: int,
    payload: TripUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.name or not payload.name.strip():
        raise ValidationException("Vui lòng nhập tên chuyến đi")

    trip = _load_owned_trip(db, trip_id, current_user)
    trip.name = payload.name.strip()
    if "description" in payload.model_fields_set:
        trip.description = payload.description
    trip.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    db.commit()
    db.refresh(trip)
    return build_response(
        200,
        "Đã cập nhật chuyến đi",
        request,
        data=_serialize_trip_detail(db, trip, current_user),
    )


@router.delete("/api/trips/{trip_id}")
def delete_trip(
    trip_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trip = _load_owned_trip(db, trip_id, current_user)
    db.execute(delete(TripMemory).where(TripMemory.trip_id == trip.id))
    db.delete(trip)
    db.commit()
    return build_response(
        200,
        "Đã xóa chuyến đi",
        request,
        data={"id": trip_id},
    )


@router.post("/api/trips/{trip_id}/memories")
def add_memories_to_trip(
    trip_id: int,
    payload: TripAddMemoriesRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trip = _load_owned_trip(db, trip_id, current_user)

    ids: list[int] = []
    if payload.memory_ids:
        ids.extend(payload.memory_ids)
    if payload.memory_id is not None:
        ids.append(payload.memory_id)
    if not ids:
        raise BadRequestException("Vui lòng chọn ký ức để thêm vào chuyến đi")

    _attach_memories_to_trip(db, trip, ids, current_user)
    trip.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(trip)
    return build_response(
        200,
        "Đã thêm ký ức vào chuyến đi",
        request,
        data=_serialize_trip_detail(db, trip, current_user),
    )


@router.delete("/api/trips/{trip_id}/memories/{memory_id}")
def remove_memory_from_trip(
    trip_id: int,
    memory_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trip = _load_owned_trip(db, trip_id, current_user)
    link = db.scalar(
        select(TripMemory).where(
            TripMemory.trip_id == trip.id,
            TripMemory.memory_id == memory_id,
        )
    )
    if link is None:
        raise NotFoundException("Ký ức không nằm trong chuyến đi này")

    db.delete(link)
    trip.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(trip)
    return build_response(
        200,
        "Đã bỏ ký ức khỏi chuyến đi",
        request,
        data=_serialize_trip_detail(db, trip, current_user),
    )
