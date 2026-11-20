"""M2 – Xem chi tiết, sửa và xóa ký ức."""

import math
import re
from datetime import date

from fastapi import APIRouter, Depends, Form, Query, Request
from sqlalchemy import delete, extract, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ForbiddenException, NotFoundException, ValidationException
from app.core.response import build_response
from app.core.security import sign_media_url
from app.modules.accounts.avatar import avatar_url
from app.modules.accounts.deps import get_current_user, get_current_user_optional
from app.modules.accounts.models import User
from app.modules.explore.region_lookup import region_id_for
from app.modules.memories.models import Hashtag, Memory, MemoryHashtag, Trip, TripMemory
from app.modules.memories.services.video_media_service import video_url

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
        "status": memory.status,  # memories.js dùng để chọn phát video/ảnh trực tiếp hay qua blob có đăng nhập
        "hidden_by_admin": memory.status == "hidden",
        "is_owner": is_owner,
        "region": (
            {"id": memory.region.id, "name": memory.region.name}
            if memory.region else None
        ),
        "author": {
            "id": memory.author.id,
            "display_name": memory.author.display_name,
            "avatar_url": avatar_url(memory.author),
        },
        "hashtags": [link.hashtag.name for link in links],
        "hashtag_sources": {
            link.hashtag.name: link.source for link in links
        },
        # Link có chữ ký: /api/media/{id} từ chối link thiếu exp/sig (trước đây trả '/api/media/12' → 422)
        "media": [
            {
                "id": item.id,
                "type": item.media_type,
                "url": video_url(item.id, item.file_path) if item.media_type == "video" else sign_media_url(item.id),
                "thumb_url": None if item.media_type == "video" else sign_media_url(item.id),
            }
            for item in memory.media
        ],
        "trips": trips,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
    }

# ----- US-EXP-005: ký ức của tôi (đặt TRƯỚC /api/memories/{memory_id}, nếu không "mine" bị hiểu là id → 422) -----
def mine_query(
    user: User,
    q: str | None,
    year: int | None,
    month: int | None,
    date_from: date | None,
    date_to: date | None,
    visibility: str | None,
    hashtags: str | None,
):
    if date_from and date_to and date_from > date_to:
        raise ValidationException("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc")
    stmt = select(Memory).where(Memory.user_id == user.id, Memory.deleted_at.is_(None))
    if year:
        stmt = stmt.where(extract("year", Memory.memory_date) == year)
    if month:
        stmt = stmt.where(extract("month", Memory.memory_date) == month)
    if date_from:
        stmt = stmt.where(Memory.memory_date >= date_from)
    if date_to:
        stmt = stmt.where(Memory.memory_date <= date_to)
    if visibility in ("private", "public"):
        stmt = stmt.where(Memory.visibility == visibility)
    tags = [t.lstrip("#").lower() for t in re.split(r"[\s,]+", hashtags or "") if t.lstrip("#")]
    if tags:
        tagged = (
            select(MemoryHashtag.memory_id)
            .join(Hashtag, Hashtag.id == MemoryHashtag.hashtag_id)
            .where(func.lower(Hashtag.name).in_(tags))
        )
        stmt = stmt.where(Memory.id.in_(tagged))
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Memory.title.ilike(like), Memory.place_name.ilike(like), Memory.content.ilike(like)))
    return stmt


def mine_filters(
    q: str | None = Query(None, max_length=100),
    year: int | None = Query(None, ge=1900, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    visibility: str | None = Query(None),
    hashtags: str | None = Query(None),
) -> dict:
    return dict(q=q, year=year, month=month, date_from=date_from, date_to=date_to, visibility=visibility, hashtags=hashtags)


def serialize_mine(memory: Memory) -> dict:
    return {
        "id": memory.id,
        "title": memory.title,
        "memory_date": memory.memory_date,
        "place_name": memory.place_name,
        "latitude": float(memory.latitude),
        "longitude": float(memory.longitude),
        "visibility": memory.visibility,
        "status": memory.status,
        "hashtags": sorted(link.hashtag.name for link in memory.hashtag_links),
        "has_video": any(item.media_type == "video" for item in memory.media),
        "cover_url": None,
        "created_at": memory.created_at,
    }


@router.get("/api/memories/mine")
def list_my_memories(
    request: Request,
    filters: dict = Depends(mine_filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = mine_query(user, **filters)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    if order == "asc":
        stmt = stmt.order_by(Memory.memory_date.asc(), Memory.created_at.asc(), Memory.id.asc())
    else:
        stmt = stmt.order_by(Memory.memory_date.desc(), Memory.created_at.desc(), Memory.id.desc())
    memories = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()

    time_filtered = any(filters[key] for key in ("year", "month", "date_from", "date_to"))
    if total:
        message = "Thành công"
    elif time_filtered:
        message = "Bạn chưa có ký ức nào trong khoảng thời gian này"
    else:
        message = "Không có ký ức nào phù hợp bộ lọc"

    return build_response(
        200,
        message,
        request,
        data={
            "items": [serialize_mine(m) for m in memories],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size)),
        },
    )


@router.get("/api/memories/mine/pins")
def list_my_pins(
    request: Request,
    filters: dict = Depends(mine_filters),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = mine_query(user, **filters).order_by(Memory.memory_date.desc(), Memory.id.desc()).limit(1000)
    data = [
        {
            "id": m.id,
            "title": m.title,
            "place_name": m.place_name,
            "memory_date": m.memory_date,
            "latitude": float(m.latitude),
            "longitude": float(m.longitude),
            "visibility": m.visibility,
            "status": m.status,
        }
        for m in db.scalars(stmt).all()
    ]
    return build_response(200, "Thành công", request, data=data)


@router.get("/api/memories/mine/years")
def list_my_years(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year = extract("year", Memory.memory_date)
    rows = db.scalars(
        select(year)
        .where(Memory.user_id == user.id, Memory.deleted_at.is_(None))
        .distinct()
        .order_by(year.desc())
    ).all()
    return build_response(200, "Thành công", request, data=[int(y) for y in rows])

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
        memory.region_id = region_id_for(db, latitude, longitude)  # US-MEM-006 AC2: khu vực theo vị trí mới

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
        memory.deleted_at = func.now()  # giờ của database, cùng chuẩn với created_at (trước đây UTC → lệch 7 giờ)
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