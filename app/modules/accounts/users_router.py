"""US-ACC-006 – Cập nhật hồ sơ cá nhân: tên hiển thị, email, giới thiệu, ảnh đại diện; thống kê trang hồ sơ.

Giao diện: accounts/ui/profile.html + js/profile.js (đã gọi sẵn các API dưới đây).
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import BadRequestException, ConflictException, NotFoundException
from app.core.response import build_response
from app.modules.accounts import service
from app.modules.accounts.deps import get_current_user
from app.modules.accounts.models import User
from app.modules.accounts.schemas import DISPLAY_NAME_MAX_LENGTH, normalize_email
from app.modules.memories.models import Memory, Trip
from app.modules.memories.services.image_media_service import (
    IMAGE_TYPES,
    MAX_IMAGE_BYTES,
    delete_media_file,
    resolve_upload_path,
)
from app.modules.memories.services.image_metadata import strip_metadata

router = APIRouter(tags=["M1 - Tài khoản"])

BIO_MAX_LENGTH = 500
MSG_NAME_EMPTY = "Vui lòng nhập tên hiển thị"
MSG_NAME_TOO_LONG = "Tên hiển thị tối đa 100 ký tự"
MSG_BIO_TOO_LONG = "Giới thiệu tối đa 500 ký tự"
MSG_AVATAR_TOO_BIG = "Ảnh không được vượt quá 5 MB"
MSG_AVATAR_TYPE = "Định dạng tệp không được hỗ trợ"


class ProfileUpdateRequest(BaseModel):
    """Chỉ cập nhật trường có gửi lên. email rỗng = giữ nguyên (tài khoản Facebook có thể chưa có email)."""

    display_name: str | None = None
    email: str | None = None
    bio: str | None = None

    @field_validator("display_name")
    @classmethod
    def _display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        name = value.strip()
        if not name:
            raise ValueError(MSG_NAME_EMPTY)
        if len(name) > DISPLAY_NAME_MAX_LENGTH:
            raise ValueError(MSG_NAME_TOO_LONG)
        return name

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return normalize_email(value) if value and value.strip() else None

    @field_validator("bio")
    @classmethod
    def _bio(cls, value: str | None) -> str | None:
        if value is None:
            return None
        bio = value.strip()
        if len(bio) > BIO_MAX_LENGTH:
            raise ValueError(MSG_BIO_TOO_LONG)
        return bio


def _user_data(user: User) -> dict:
    return service.to_user_response(user).model_dump(mode="json")


@router.patch("/api/users/me")
def update_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fields = payload.model_fields_set
    if "display_name" in fields and payload.display_name is not None:
        user.display_name = payload.display_name  # AC1: ký ức công khai đọc tên qua quan hệ author nên đổi theo
    if "bio" in fields:
        user.bio = payload.bio or None
    if payload.email and payload.email != (user.email or "").lower():
        other = service.find_user_by_email(db, payload.email)
        if other is not None and other.id != user.id:
            raise ConflictException(service.MSG_EMAIL_TAKEN)
        user.email = payload.email
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictException(service.MSG_EMAIL_TAKEN) from None
    db.refresh(user)
    return build_response(200, "Đã cập nhật hồ sơ", request, data=_user_data(user))


@router.post("/api/users/me/avatar")
async def upload_avatar(
    request: Request,
    avatar: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    extension = Path(avatar.filename or "").suffix.lower()
    expected = IMAGE_TYPES.get(extension)
    if expected is None:
        raise BadRequestException(MSG_AVATAR_TYPE)  # AC5: baocao.pdf
    if avatar.size is not None and avatar.size > MAX_IMAGE_BYTES:
        raise BadRequestException(MSG_AVATAR_TOO_BIG)  # AC4: ảnh 6 MB
    content = await avatar.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise BadRequestException(MSG_AVATAR_TOO_BIG)
    if not expected[1](content):
        raise BadRequestException(MSG_AVATAR_TYPE)  # đổi đuôi tệp không phải ảnh thành .jpg
    content = strip_metadata(content, extension)  # ảnh đại diện là công khai: bỏ EXIF/GPS

    relative_path = f"avatars/{user.id}_{uuid.uuid4().hex[:12]}{extension}"
    target = resolve_upload_path(relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)

    old_path = user.avatar_path
    user.avatar_path = relative_path
    try:
        db.commit()
    except Exception:
        db.rollback()
        delete_media_file(relative_path)
        raise
    delete_media_file(old_path)
    db.refresh(user)
    return build_response(200, "Đã cập nhật ảnh đại diện", request, data=_user_data(user))


@router.delete("/api/users/me/avatar")
def remove_avatar(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    old_path = user.avatar_path
    user.avatar_path = None
    db.commit()
    delete_media_file(old_path)
    db.refresh(user)
    return build_response(200, "Đã gỡ ảnh đại diện", request, data=_user_data(user))


@router.get("/api/users/{user_id}/avatar", include_in_schema=False)
def get_avatar(user_id: int, db: Session = Depends(get_db)):
    """Ảnh đại diện là thông tin công khai (hiện cạnh ký ức công khai, BR-12)."""
    user = db.get(User, user_id)
    if user is None or not user.avatar_path:
        raise NotFoundException("Không tìm thấy ảnh đại diện")
    try:
        path = resolve_upload_path(user.avatar_path)
    except ValueError:
        raise NotFoundException("Không tìm thấy ảnh đại diện") from None
    if not path.is_file():
        raise NotFoundException("Không tìm thấy ảnh đại diện")
    media_type = IMAGE_TYPES.get(path.suffix.lower(), ("application/octet-stream",))[0]
    # Đường dẫn có ?v= đổi theo mỗi lần đổi ảnh nên cho trình duyệt cache lâu
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/api/users/me/stats")
def my_stats(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alive = (Memory.user_id == user.id, Memory.deleted_at.is_(None))
    data = {
        "memories": db.scalar(select(func.count(Memory.id)).where(*alive)) or 0,
        "public_memories": db.scalar(select(func.count(Memory.id)).where(*alive, Memory.visibility == "public")) or 0,
        "trips": db.scalar(select(func.count(Trip.id)).where(Trip.user_id == user.id)) or 0,
        "places": db.scalar(
            select(func.count(func.distinct(Memory.region_id))).where(*alive, Memory.region_id.is_not(None))
        ) or 0,
    }
    return build_response(200, "Thành công", request, data=data)
