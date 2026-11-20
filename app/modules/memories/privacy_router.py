"""US-MEM-008 - Đổi chế độ riêng tư hoặc công khai của ký ức."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ForbiddenException, ValidationException
from app.core.response import build_response
from app.modules.accounts.deps import get_current_user
from app.modules.accounts.models import User

# Dùng chung một nơi định dạng ký ức: GET /api/memories/{id} nằm ở router.py (đăng ký trước trong main.py),
# bản trùng ở file này trước đây không bao giờ chạy nên đã bỏ.
from app.modules.memories.router import load_memory, serialize_memory  # noqa: F401 (hashtags/trips import lại từ đây)

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
    memory.updated_at = func.now()  # giờ của database, cùng chuẩn với created_at (trước đây UTC → lệch 7 giờ)

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
