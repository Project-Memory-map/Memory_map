from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import build_response
from app.modules.accounts.models import User
from app.modules.explore.models import Region
from app.modules.memories.models import Memory

router = APIRouter(tags=["M3 - Khám phá"])


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
            Memory.author.has(User.status == "active"),
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
            func.coalesce(
                count_subq.c.memory_count, 0
            ).label("memory_count"),
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
            "public_count": row.memory_count,
        }
        for row in rows
    ]

    return build_response(200, "Thành công", request, data=data)