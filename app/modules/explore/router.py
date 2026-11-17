"""M3 - Khám phá bản đồ và tìm kiếm ký ức công khai."""

import math
import re
import unicodedata

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.mysql import match
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ValidationException
from app.core.response import build_response
from app.modules.accounts.models import User
from app.modules.explore.models import Region
from app.modules.memories.models import Hashtag, Memory, MemoryHashtag

router = APIRouter(prefix="/api/explore", tags=["M3 - Khám phá"])

PIN_LIMIT = 500


def clean_keyword(q: str | None) -> str:
    q = unicodedata.normalize("NFC", (q or "").strip())

    if q and len(q) < 2:
        raise ValidationException("Nhập ít nhất 2 ký tự")

    if len(q) > 100:
        raise ValidationException("Từ khóa tối đa 100 ký tự")

    return q


def parse_tags(raw: str | None) -> list[str]:
    tags = []

    for part in re.split(r"[\s,]+", raw or ""):
        tag = unicodedata.normalize(
            "NFC", part.strip().lstrip("#")
        ).lower()

        if tag and tag not in tags:
            tags.append(tag)

    return tags


def public_query(
    db: Session,
    columns,
    q="",
    tags=None,
    region=None,
    box=None,
):
    stmt = (
        select(*columns)
        .join(User, User.id == Memory.user_id)
        .where(
            Memory.visibility == "public",
            Memory.status == "active",
            Memory.deleted_at.is_(None),
            User.status == "active",
        )
    )

    if tags:
        tagged = (
            select(MemoryHashtag.memory_id)
            .join(Hashtag, Hashtag.id == MemoryHashtag.hashtag_id)
            .where(func.lower(Hashtag.name).in_(tags))
        )
        stmt = stmt.where(Memory.id.in_(tagged))

    if region:
        stmt = stmt.join(Region, Region.id == Memory.region_id)

        if str(region).isdigit():
            stmt = stmt.where(Region.id == int(region))
        else:
            stmt = stmt.where(Region.slug == region)

    if box and None not in box:
        south, west, north, east = box

        if south > north:
            raise ValidationException("Vùng bản đồ không hợp lệ")

        if west <= east:
            longitude_filter = Memory.longitude.between(west, east)
        else:
            longitude_filter = or_(
                Memory.longitude >= west,
                Memory.longitude <= east,
            )

        stmt = stmt.where(
            Memory.latitude.between(south, north),
            longitude_filter,
        )

    score = None

    if q:
        if db.get_bind().dialect.name == "mysql":
            phrase = " ".join(re.findall(r"\w+", q))
            score = match(
                Memory.title,
                Memory.place_name,
                against=f'"{phrase}"',
            ).in_boolean_mode()

            stmt = stmt.where(score > 0)
        else:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Memory.title.ilike(like),
                    Memory.place_name.ilike(like),
                )
            )

    order = [Memory.memory_date.desc(), Memory.id.desc()]

    if score is not None:
        order.insert(0, score.desc())

    return stmt.order_by(*order)


def serialize(m: Memory) -> dict:
    return {
        "id": m.id,
        "title": m.title,
        "content": m.content,
        "memory_date": m.memory_date,
        "place_name": m.place_name,
        "latitude": float(m.latitude),
        "longitude": float(m.longitude),
        "visibility": m.visibility,
        "region": (
            {
                "id": m.region.id,
                "name": m.region.name,
                "slug": m.region.slug,
            }
            if m.region
            else None
        ),
        "author": {
            "id": m.author.id,
            "display_name": m.author.display_name,
            "avatar_url": m.author.avatar_path,
        },
        "hashtags": sorted(
            link.hashtag.name for link in m.hashtag_links
        ),
        "created_at": m.created_at,
    }


@router.get("/pins")
def list_public_pins(
    request: Request,
    south: float | None = Query(None, ge=-90, le=90),
    west: float | None = Query(None, ge=-180, le=180),
    north: float | None = Query(None, ge=-90, le=90),
    east: float | None = Query(None, ge=-180, le=180),
    q: str | None = Query(None),
    hashtags: str | None = Query(None),
    region: str | None = Query(None),
    db: Session = Depends(get_db),
):
    columns = (
        Memory.id,
        Memory.title,
        Memory.place_name,
        Memory.memory_date,
        Memory.latitude,
        Memory.longitude,
        User.display_name.label("author_name"),
    )

    stmt = public_query(
        db,
        columns,
        clean_keyword(q),
        parse_tags(hashtags),
        region,
        (south, west, north, east),
    )

    rows = db.execute(stmt.limit(PIN_LIMIT)).mappings().all()

    data = [
        {
            **row,
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
        }
        for row in rows
    ]

    return build_response(
        200,
        "Lấy danh sách ghim công khai thành công",
        request,
        data=data,
    )


@router.get("/overview")
def overview(
    request: Request,
    db: Session = Depends(get_db),
):
    base = (
        public_query(db, (Memory.id, Memory.region_id))
        .order_by(None)
        .subquery()
    )

    public_memories = (
        db.scalar(select(func.count()).select_from(base)) or 0
    )

    regions = (
        db.scalar(select(func.count(func.distinct(base.c.region_id))))
        or 0
    )

    return build_response(
        200,
        "Thành công",
        request,
        data={
            "public_memories": public_memories,
            "regions": regions,
        },
    )


@router.get("/memories")
def list_public_memories(
    request: Request,
    q: str | None = Query(None),
    hashtags: str | None = Query(None),
    region: str | None = Query(None),
    south: float | None = Query(None, ge=-90, le=90),
    west: float | None = Query(None, ge=-180, le=180),
    north: float | None = Query(None, ge=-90, le=90),
    east: float | None = Query(None, ge=-180, le=180),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    q = clean_keyword(q)
    tags = parse_tags(hashtags)

    stmt = public_query(
        db,
        (Memory,),
        q,
        tags,
        region,
        (south, west, north, east),
    )

    total = (
        db.scalar(
            select(func.count()).select_from(
                stmt.order_by(None).subquery()
            )
        )
        or 0
    )

    memories = db.scalars(
        stmt.offset((page - 1) * page_size).limit(page_size)
    ).all()

    if total:
        message = "Thành công"
    elif q:
        message = f"Không tìm thấy kết quả cho {q}"
    elif tags:
        message = "Chưa có ký ức nào với hashtag này"
    else:
        message = "Chưa có ký ức công khai trong khu vực này"

    return build_response(
        200,
        message,
        request,
        data={
            "items": [serialize(m) for m in memories],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size)),
        },
    )