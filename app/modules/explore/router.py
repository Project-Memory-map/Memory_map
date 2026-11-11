from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
)
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import build_response
from app.core.security import sign_media_url
from app.modules.accounts.models import User
from app.modules.explore import repository as repo
from app.modules.explore.models import Region
from app.modules.explore.schemas import BoundingBox
from app.modules.memories.models import Media, Memory


router = APIRouter(
    prefix="/api/explore",
    tags=["M3 - Khám phá"],
)


def respond(
    request,
    data,
    message="Lấy ký ức công khai thành công",
):
    response = build_response(
        200,
        message,
        request,
        data=data,
    )

    response.headers["Cache-Control"] = "no-store"
    return response


def execute_search(db, statement):
    try:
        return [
            dict(row)
            for row in db.execute(statement).mappings()
        ]

    except (ProgrammingError, OperationalError) as exc:
        if exc.orig.args and exc.orig.args[0] == 1191:
            raise HTTPException(
                503,
                "Database thiếu chỉ mục FULLTEXT title, place_name",
            ) from exc

        raise


@router.get("/pins")
def pins(
    request: Request,
    box: Annotated[BoundingBox, Query()],
    q: str = Query("", max_length=100),
    hashtags: str = Query("", max_length=500),
    region: str = Query("", max_length=120),
    db: Session = Depends(get_db),
):
    statement = repo.build_query(
        db,
        box,
        q,
        hashtags,
        region,
    ).limit(500)

    rows = execute_search(db, statement)
    return respond(request, rows)


@router.get("/memories")
def memories(
    request: Request,
    q: str = Query("", max_length=100),
    hashtags: str = Query("", max_length=500),
    region: str = Query("", max_length=120),
    page: int = Query(1, ge=1, le=10000),
    south: float | None = Query(None, ge=-90, le=90),
    west: float | None = Query(None, ge=-180, le=180),
    north: float | None = Query(None, ge=-90, le=90),
    east: float | None = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db),
):
    bounds = (south, west, north, east)
    box = None

    if any(value is not None for value in bounds):
        if (
            any(value is None for value in bounds)
            or south > north
        ):
            raise HTTPException(
                400,
                "Vùng bản đồ không hợp lệ",
            )

        box = BoundingBox(
            south=south,
            west=west,
            north=north,
            east=east,
        )

    q = repo.keyword(q)

    statement = (
        repo.build_query(
            db,
            box,
            q,
            hashtags,
            region,
        )
        .offset((page - 1) * 20)
        .limit(21)
    )

    rows = execute_search(db, statement)

    if rows:
        message = "Tìm kiếm thành công"
    elif q:
        message = f"Không tìm thấy kết quả cho {q}"
    else:
        message = (
            "Chưa có ký ức công khai trong khu vực này"
        )

    return respond(
        request,
        {
            "items": rows[:20],
            "page": page,
            "has_more": len(rows) > 20,
            "message": message,
        },
    )


@router.get("/regions")
def regions(
    request: Request,
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(
            Region.name,
            Region.slug,
        ).order_by(Region.name)
    ).mappings()

    return respond(
        request,
        [dict(row) for row in rows],
    )


@router.get("/memories/{memory_id}")
def detail(
    memory_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(
            Memory,
            User.display_name,
        )
        .join(
            User,
            User.id == Memory.user_id,
        )
        .where(
            Memory.id == memory_id,
            *repo.public_conditions(),
        )
    ).first()

    if row is None:
        raise HTTPException(
            404,
            "Không tìm thấy ký ức",
        )

    memory, author = row

    data = {
        "id": memory.id,
        "title": memory.title,
        "place_name": memory.place_name,
        "memory_date": memory.memory_date,
        "content": memory.content,
        "author_name": author,
        "latitude": float(memory.latitude),
        "longitude": float(memory.longitude),
        "media": [],
    }

    media_rows = db.scalars(
        select(Media)
        .where(Media.memory_id == memory.id)
        .order_by(Media.sort_order)
    )

    for item in media_rows:
        data["media"].append(
            {
                "type": item.media_type,
                "url": sign_media_url(item.id),
            }
        )

    return respond(request, data)