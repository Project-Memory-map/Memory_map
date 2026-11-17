from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import build_response
from app.modules.explore.models import Region
from app.modules.memories.models import Hashtag, Memory, MemoryHashtag

router = APIRouter(tags=["M3 - Khám phá"])


# ----- helper -----
def parse_hashtags(raw_tags: list[str] | None) -> list[str]:
    if not raw_tags:
        return []
    cleaned = []
    for item in raw_tags:
        for part in item.split(","):
            tag = part.strip().lstrip("#").lower()
            if tag and tag not in cleaned:
                cleaned.append(tag)
    return cleaned


def serialize_explore_memory(m: Memory) -> dict:
    return {
        "id": m.id,
        "title": m.title,
        "content": m.content,
        "memory_date": m.memory_date,
        "place_name": m.place_name,
        "latitude": m.latitude,
        "longitude": m.longitude,
        "visibility": m.visibility,
        "region": {"id": m.region.id, "name": m.region.name} if m.region else None,
        "author": {
            "id": m.author.id,
            "display_name": m.author.display_name,
            "avatar_url": m.author.avatar_path,
        },
        "hashtags": sorted([link.hashtag.name for link in m.hashtag_links]),
        "created_at": m.created_at,
    }


# ----- US-EXP-003: danh sách 34 tỉnh/thành -----
@router.get("/api/explore/regions")
def get_explore_regions(
    request: Request,
    db: Session = Depends(get_db),
):
    count_subq = (
        select(
            Memory.region_id.label("region_id"),
            func.count(Memory.id).label("memory_count"),
        )
        .where(
            Memory.deleted_at.is_(None),
            Memory.visibility == "public",
            Memory.status == "active",
            Memory.region_id.is_not(None),
        )
        .group_by(Memory.region_id)
        .subquery()
    )

    rows = db.execute(
        select(
            Region.id,
            Region.name,
            Region.slug,
            Region.level,
            func.coalesce(count_subq.c.memory_count, 0).label("memory_count"),
        )
        .outerjoin(count_subq, count_subq.c.region_id == Region.id)
        .order_by(Region.name.asc())
    ).all()

    data = [
        {
            "id": row.id,
            "name": row.name,
            "slug": row.slug,
            "level": row.level,
            "count": row.memory_count,
        }
        for row in rows
    ]
    return build_response(200, "Thành công", request, data=data)


# ----- US-EXP-003: lọc ký ức công khai theo khu vực -----
@router.get("/api/explore/memories")
def explore_public_memories_by_region(
    request: Request,
    q: str | None = Query(None),
    hashtags: list[str] | None = Query(None),
    region: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    normalized_tags = parse_hashtags(hashtags)

    stmt = select(Memory).where(
        Memory.deleted_at.is_(None),
        Memory.visibility == "public",
        Memory.status == "active",
    )

    if region is not None:
        stmt = stmt.where(Memory.region_id == region)

    if normalized_tags:
        stmt = (
            stmt.join(MemoryHashtag, MemoryHashtag.memory_id == Memory.id)
            .join(Hashtag, Hashtag.id == MemoryHashtag.hashtag_id)
            .where(func.lower(Hashtag.name).in_(normalized_tags))
            .distinct()
        )

    if q and q.strip():
        keyword = f"%{q.strip()}%"
        stmt = stmt.where(
            Memory.title.ilike(keyword)
            | Memory.content.ilike(keyword)
            | Memory.place_name.ilike(keyword)
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    memories = db.scalars(
        stmt.order_by(Memory.created_at.desc(), Memory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [serialize_explore_memory(m) for m in memories]
    return build_response(
        200,
        "Thành công",
        request,
        data={
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    )