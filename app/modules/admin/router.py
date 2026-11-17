"""M4 – Quản trị.

Giao diện đã có sẵn: ui/index.html (trang /admin/); xử lý ở js/admin.js.
Mọi route đều qua get_current_admin (đăng nhập + role = 'admin').

| Task       | Phương thức + đường dẫn                                   | Gọi từ    | Trạng thái |
|------------|-----------------------------------------------------------|-----------|------------|
| US-ADM-001 | GET  /api/admin/stats                                     | admin.js  | ✅ |
| US-ADM-001 | GET  /api/admin/memories?q=&status=                       | admin.js  | ✅ |
| US-ADM-001 | POST /api/admin/memories/{id}/hide · /unhide              | admin.js  | ✅ |
| US-ADM-001→003 | GET /api/admin/actions?action=  (nhật ký thao tác)    | admin.js  | ✅ |
| US-ADM-002 | POST /api/admin/memories/{id}/delete                      | admin.js  | ⏳ |
| US-ADM-003 | GET  /api/admin/users?q=                                  | admin.js  | ⏳ |
| US-ADM-003 | POST /api/admin/users/{id}/lock · /unlock                 | admin.js  | ⏳ |

Bảng dùng: admin_actions (models.py) + memories, users.
Trigger trong MySQL cũng chặn: không có lý do (BR-10), admin tự khóa mình (BR-11), sửa/xóa nhật ký.
Router kiểm tra lại các quy tắc này để trả lỗi rõ ràng trước khi chạm DB.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.core.response import build_response
from app.core.security import sign_media_url
from app.modules.accounts.deps import get_current_user
from app.modules.accounts.models import User
from app.modules.admin.models import AdminAction
from app.modules.memories.models import Media, Memory

router = APIRouter(prefix="/api/admin", tags=["M4 - Quản trị"])

REASON_MAX = 500
ACTION_LABELS = {
    "hide_memory": "Ẩn ký ức",
    "unhide_memory": "Bỏ ẩn ký ức",
    "delete_memory": "Xóa ký ức",
    "lock_user": "Khóa tài khoản",
    "unlock_user": "Mở khóa tài khoản",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ----- Quyền quản trị

def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise ForbiddenException("Chỉ quản trị viên mới được thực hiện thao tác này")
    return user


# ----- Dữ liệu gửi lên

class ReasonRequest(BaseModel):
    """Lý do bắt buộc cho thao tác ẩn (BR-10)."""

    reason: str | None = Field(default=None, validate_default=True)  # thiếu trường cũng phải báo lỗi

    @field_validator("reason", mode="before")
    @classmethod
    def _validate_reason(cls, value: object) -> str:
        text = value.strip() if isinstance(value, str) else ""
        if not text:
            raise ValueError("Vui lòng nhập lý do")
        if len(text) > REASON_MAX:
            raise ValueError(f"Lý do tối đa {REASON_MAX} ký tự")
        return text


class OptionalReasonRequest(BaseModel):
    """Bỏ ẩn: lý do không bắt buộc."""

    reason: str | None = None

    @field_validator("reason", mode="before")
    @classmethod
    def _validate_reason(cls, value: object) -> str | None:
        text = value.strip() if isinstance(value, str) else ""
        if len(text) > REASON_MAX:
            raise ValueError(f"Lý do tối đa {REASON_MAX} ký tự")
        return text or None


# ----- Hàm dùng chung

def _page_data(items: list, total: int, page: int, page_size: int) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size),
    }


def _keyword(q: str | None) -> str | None:
    """Chuỗi LIKE an toàn: "%" và "_" người dùng gõ được hiểu là ký tự thường (escape bằng "!")."""
    text = (q or "").strip()[:100]
    if not text:
        return None
    escaped = text.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"%{escaped}%"


def _log(db: Session, admin: User, action: str, target_type: str, target_id: int, reason: str | None) -> None:
    db.add(
        AdminAction(
            admin_id=admin.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
        )
    )


def _load_public_memory(db: Session, memory_id: int) -> Memory:
    """Ký ức admin được thao tác: công khai và chưa bị xóa (khóa dòng để tránh 2 admin cùng sửa)."""
    memory = db.scalar(
        select(Memory)
        .where(Memory.id == memory_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if memory is None or memory.deleted_at is not None or memory.visibility != "public":
        raise NotFoundException("Không tìm thấy ký ức công khai")
    return memory


def _serialize_memory(memory: Memory, cover_id: int | None) -> dict:
    author = memory.author
    return {
        "id": memory.id,
        "title": memory.title,
        "place_name": memory.place_name,
        "memory_date": memory.memory_date,
        "visibility": memory.visibility,
        "status": memory.status,
        "cover_url": sign_media_url(cover_id) if cover_id else None,
        "author": {
            "id": author.id,
            "display_name": author.display_name,
            "status": author.status,
        },
        "created_at": memory.created_at,
    }


# ----- US-ADM-001: thống kê nhanh

@router.get("/stats")
def admin_stats(
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    alive = Memory.deleted_at.is_(None)
    week_ago = _now() - timedelta(days=7)
    data = {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "locked_users": db.scalar(select(func.count(User.id)).where(User.status == "locked")) or 0,
        "memories": db.scalar(select(func.count(Memory.id)).where(alive)) or 0,
        "public_memories": db.scalar(
            select(func.count(Memory.id)).where(alive, Memory.visibility == "public")
        ) or 0,
        "hidden_memories": db.scalar(
            select(func.count(Memory.id)).where(alive, Memory.status == "hidden")
        ) or 0,
        "new_memories_7d": db.scalar(
            select(func.count(Memory.id)).where(alive, Memory.created_at >= week_ago)
        ) or 0,
    }
    return build_response(200, "Thành công", request, data=data)


# ----- US-ADM-001: danh sách ký ức công khai

@router.get("/memories")
def admin_list_memories(
    request: Request,
    q: str | None = Query(None, max_length=100),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Memory)
        .join(User, User.id == Memory.user_id)
        .where(Memory.visibility == "public", Memory.deleted_at.is_(None))
    )
    if status in ("active", "hidden"):
        stmt = stmt.where(Memory.status == status)
    elif status:
        raise ValidationException("Trạng thái không hợp lệ")
    keyword = _keyword(q)
    if keyword:
        stmt = stmt.where(
            or_(
                Memory.title.ilike(keyword, escape="!"),
                Memory.place_name.ilike(keyword, escape="!"),
                User.display_name.ilike(keyword, escape="!"),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    memories = db.scalars(
        stmt.order_by(Memory.created_at.desc(), Memory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()

    covers: dict[int, int] = {}
    ids = [m.id for m in memories]
    if ids:
        rows = db.execute(
            select(Media.memory_id, func.min(Media.id))
            .where(Media.memory_id.in_(ids), Media.media_type == "image")
            .group_by(Media.memory_id)
        ).all()
        covers = {memory_id: media_id for memory_id, media_id in rows}

    items = [_serialize_memory(m, covers.get(m.id)) for m in memories]
    return build_response(200, "Thành công", request, data=_page_data(items, total, page, page_size))


# ----- US-ADM-001: ẩn / bỏ ẩn ký ức công khai vi phạm

@router.post("/memories/{memory_id}/hide")
def admin_hide_memory(
    memory_id: int,
    payload: ReasonRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        memory = _load_public_memory(db, memory_id)
        if memory.status == "hidden":
            raise ConflictException("Ký ức này đã bị ẩn")
        memory.status = "hidden"
        _log(db, admin, "hide_memory", "memory", memory.id, payload.reason)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return build_response(200, "Đã ẩn ký ức", request, data={"id": memory.id, "status": memory.status})


@router.post("/memories/{memory_id}/unhide")
def admin_unhide_memory(
    memory_id: int,
    request: Request,
    payload: OptionalReasonRequest | None = None,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        memory = _load_public_memory(db, memory_id)
        if memory.status != "hidden":
            raise ConflictException("Ký ức này đang hiển thị, không cần bỏ ẩn")
        memory.status = "active"
        _log(db, admin, "unhide_memory", "memory", memory.id, payload.reason if payload else None)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return build_response(200, "Đã bỏ ẩn ký ức", request, data={"id": memory.id, "status": memory.status})


# ----- US-ADM-001→003: nhật ký thao tác

@router.get("/actions")
def admin_list_actions(
    request: Request,
    action: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    stmt = select(AdminAction)
    if action in ACTION_LABELS:
        stmt = stmt.where(AdminAction.action == action)
    elif action:
        raise ValidationException("Loại thao tác không hợp lệ")

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AdminAction.created_at.desc(), AdminAction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()

    memory_ids = {r.target_id for r in rows if r.target_type == "memory"}
    user_ids = {r.target_id for r in rows if r.target_type == "user"}
    memory_titles = (
        dict(db.execute(select(Memory.id, Memory.title).where(Memory.id.in_(memory_ids))).all())
        if memory_ids else {}
    )
    user_names = (
        dict(db.execute(select(User.id, User.display_name).where(User.id.in_(user_ids))).all())
        if user_ids else {}
    )

    def target_label(row: AdminAction) -> str:
        names = memory_titles if row.target_type == "memory" else user_names
        return names.get(row.target_id) or f"#{row.target_id}"

    items = [
        {
            "id": row.id,
            "created_at": row.created_at,
            "admin": {"id": row.admin.id, "display_name": row.admin.display_name},
            "action": row.action,
            "action_label": ACTION_LABELS[row.action],
            "target_type": row.target_type,
            "target_id": row.target_id,
            "target_label": target_label(row),
            "reason": row.reason,
        }
        for row in rows
    ]
    return build_response(200, "Thành công", request, data=_page_data(items, total, page, page_size))
