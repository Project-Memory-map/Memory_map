from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import build_response
from app.modules.accounts.models import User
from app.modules.memories.models import Hashtag, Memory, MemoryHashtag

router = APIRouter(tags=["M3 - Khám phá"])


@router.get("/api/explore/hashtags")
def get_popular_hashtags(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(
            Hashtag.id,
            Hashtag.name,
            func.count(func.distinct(Memory.id)).label("memory_count"),
        )
        .join(MemoryHashtag, MemoryHashtag.hashtag_id == Hashtag.id)
        .join(Memory, Memory.id == MemoryHashtag.memory_id)
        .where(
            Memory.deleted_at.is_(None),
            Memory.visibility == "public",
            Memory.status == "active",
            Memory.author.has(User.status == "active"),
        )
        .group_by(Hashtag.id, Hashtag.name)
        .order_by(
            func.count(func.distinct(Memory.id)).desc(),
            Hashtag.name.asc(),
        )
        .limit(limit)
    ).all()

    data = [
        {
            "id": row.id,
            "name": row.name,
            "count": row.memory_count,
        }
        for row in rows
    ]

    return build_response(200, "Thành công", request, data=data)