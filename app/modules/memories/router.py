import math
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import build_response
from app.modules.accounts.deps import get_current_user
from app.modules.accounts.models import User
from app.modules.memories.geocode import EMPTY_MESSAGE, search_places
from app.modules.memories.models import Memory


router = APIRouter(
    prefix="/api/memories",
    tags=["M2 - Ký ức"],
)


def today_vn():
    return datetime.now(timezone(timedelta(hours=7))).date()


def serialize(memory):
    return {
        "id": memory.id,
        "title": memory.title,
        "content": memory.content,
        "place_name": memory.place_name,
        "memory_date": memory.memory_date.isoformat(),
        "latitude": float(memory.latitude),
        "longitude": float(memory.longitude),
        "visibility": memory.visibility,
    }


@router.get("/geocode")
def geocode(
    request: Request,
    q: str = Query("", max_length=200),
    user: User = Depends(get_current_user),
):
    places = search_places(q)

    message = (
        "Tìm địa điểm thành công"
        if places
        else EMPTY_MESSAGE
    )

    return build_response(
        200,
        message,
        request,
        data=places,
    )


@router.get("/mine")
def mine(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(Memory)
        .where(
            Memory.user_id == user.id,
            Memory.deleted_at.is_(None),
        )
        .order_by(
            Memory.memory_date.desc(),
            Memory.id.desc(),
        )
    ).all()

    return build_response(
        200,
        "Ký ức của tôi",
        request,
        data=[serialize(row) for row in rows],
    )


@router.post("", status_code=201)
def create_memory(
    request: Request,
    title: str = Form(""),
    content: str = Form(""),
    place_name: str = Form(""),
    memory_date: str = Form(""),
    latitude: str = Form(""),
    longitude: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    title = title.strip()
    place_name = place_name.strip()

    if not title:
        raise HTTPException(400, "Vui lòng nhập tiêu đề")

    if len(title) > 200:
        raise HTTPException(400, "Tiêu đề tối đa 200 ký tự")

    if not place_name or len(place_name) > 255:
        raise HTTPException(
            400,
            "Tên địa điểm phải có từ 1 đến 255 ký tự",
        )

    # Giữ nguyên nội dung, không trim hoặc cắt ngắn câu chuyện.
    if len(content) > 100000:
        raise HTTPException(400, "Nội dung tối đa 100.000 ký tự")

    try:
        day = date.fromisoformat(memory_date)
    except ValueError:
        raise HTTPException(400, "Vui lòng chọn ngày hợp lệ")

    if day > today_vn():
        raise HTTPException(400, "Ngày không được ở tương lai")

    try:
        lat = float(latitude)
        lng = float(longitude)
    except ValueError:
        raise HTTPException(
            400,
            "Vui lòng chọn vị trí trên bản đồ hoặc tìm địa điểm",
        )

    if not (
        math.isfinite(lat)
        and math.isfinite(lng)
        and -90 <= lat <= 90
        and -180 <= lng <= 180
    ):
        raise HTTPException(400, "Tọa độ không hợp lệ")

    memory = Memory(
        user_id=user.id,
        title=title,
        content=content,
        place_name=place_name,
        memory_date=day,
        latitude=round(lat, 6),
        longitude=round(lng, 6),
        visibility="private",
        status="active",
    )

    try:
        db.add(memory)
        db.commit()
        db.refresh(memory)
    except Exception:
        db.rollback()
        raise

    return build_response(
        201,
        "Đã lưu ký ức",
        request,
        data=serialize(memory),
    )