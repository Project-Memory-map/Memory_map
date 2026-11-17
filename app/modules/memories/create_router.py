"""US-MEM-002 – Tạo ký ức bằng chọn vị trí trên bản đồ (T05B579).

Luồng trên giao diện (memories.js): nhấp bản đồ hoặc nút "Chọn trên bản đồ" → ghim tím
(kéo để chỉnh) → GET /api/geocode/reverse điền sẵn tên địa điểm → POST /api/memories.
Ảnh/video gửi sau qua /api/memories/{id}/images và /video (US-MEM-003/004).
"""
from datetime import date

from fastapi import APIRouter, Depends, Form, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ServiceUnavailableException, ValidationException
from app.core.response import build_response
from app.modules.accounts.deps import get_current_user
from app.modules.accounts.models import User
from app.modules.memories.models import Memory
from app.modules.memories.router import serialize_memory
from app.modules.memories.services.reverse_geocode_service import GeocodeUnavailable, reverse_geocode

router = APIRouter(tags=["M2 - Ký ức"])

TITLE_MAX = 200
PLACE_MAX = 255
MSG_CREATED = "Đã lưu ký ức"


def _check_coordinates(latitude: float | None, longitude: float | None) -> tuple[float, float]:
    if latitude is None or longitude is None:
        raise ValidationException("Vui lòng chọn vị trí trên bản đồ hoặc tìm địa điểm")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValidationException("Tọa độ không hợp lệ")
    return round(latitude, 6), round(longitude, 6)


# ----- Đổi tọa độ thành tên địa điểm -----
@router.get("/api/geocode/reverse")
def geocode_reverse(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
):
    try:
        place = reverse_geocode(lat, lng)
    except GeocodeUnavailable:
        raise ServiceUnavailableException("Không lấy được tên địa điểm, vui lòng tự nhập") from None
    message = "Thành công" if place else "Không tìm thấy tên địa điểm cho vị trí này"
    return build_response(200, message, request, data=place)


# ----- Tạo ký ức -----
@router.post("/api/memories", status_code=201)
def create_memory(
    request: Request,
    title: str = Form(""),
    place_name: str = Form(""),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    memory_date: date | None = Form(None),
    content: str = Form(""),
    visibility: str = Form("private"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    latitude, longitude = _check_coordinates(latitude, longitude)

    place_name = place_name.strip()
    if not place_name:
        raise ValidationException("Vui lòng nhập tên địa điểm")

    title = title.strip()
    if not title:
        raise ValidationException("Vui lòng nhập tiêu đề")
    if len(title) > TITLE_MAX:
        raise ValidationException("Tiêu đề tối đa 200 ký tự")

    if memory_date is None:
        raise ValidationException("Vui lòng chọn ngày")
    if memory_date > date.today():
        raise ValidationException("Ngày không được ở tương lai")

    if visibility not in ("private", "public"):
        raise ValidationException("Chế độ hiển thị không hợp lệ")

    memory = Memory(
        user_id=user.id,
        title=title,
        content=content.strip(),
        memory_date=memory_date,
        place_name=place_name[:PLACE_MAX],
        latitude=latitude,
        longitude=longitude,
        visibility=visibility,  # BR-01: mặc định riêng tư
        status="active",
    )
    db.add(memory)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(memory)
    return build_response(201, MSG_CREATED, request, data=serialize_memory(db, memory, user))
