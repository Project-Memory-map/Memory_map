"""US-MEM-010 – Router gắn, sửa, xóa và gợi ý hashtag cho ký ức (FR-2.9, BR-06)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ForbiddenException, NotFoundException
from app.core.response import build_response
from app.modules.accounts.deps import get_current_user, get_current_user_optional
from app.modules.accounts.models import User
from app.modules.memories.hashtag_service import (
    normalize_hashtag,
    suggest_hashtags_from_text,
    sync_memory_hashtags,
)
from app.modules.memories.models import Hashtag, Memory, MemoryHashtag
from app.modules.memories.privacy_router import load_memory, serialize_memory

router = APIRouter(tags=["M2 - Ký ức & Chuyến đi"])


class MemoryHashtagsPayload(BaseModel):
    hashtags: list[str] | str | None = None
    hashtag: str | None = None
    ai_hashtags: list[str] | str | None = None
    replace: bool = False


class SuggestHashtagsRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    place_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None


def _extract_raw_hashtags(payload: MemoryHashtagsPayload) -> list[str] | str | None:
    if payload.hashtags is not None:
        return payload.hashtags
    if payload.hashtag is not None:
        return [payload.hashtag]
    return None


def _load_owned_memory(db: Session, memory_id: int, current_user: User) -> Memory:
    memory = load_memory(db, memory_id)
    if memory.user_id != current_user.id:
        raise ForbiddenException("Bạn không có quyền sửa hashtag của ký ức này")
    return memory


@router.post("/api/memories/suggest-hashtags")
def suggest_hashtags(
    payload: SuggestHashtagsRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    data = suggest_hashtags_from_text(
        title=payload.title,
        content=payload.content,
        place_name=payload.place_name,
    )
    return build_response(200, "Đã gợi ý hashtag", request, data=data)


@router.get("/api/memories/mine/hashtags")
@router.get("/api/hashtags")
def list_my_hashtags(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Hashtag.name, func.count(MemoryHashtag.memory_id).label("count"))
        .join(MemoryHashtag, MemoryHashtag.hashtag_id == Hashtag.id)
        .join(Memory, Memory.id == MemoryHashtag.memory_id)
        .where(Memory.user_id == current_user.id, Memory.deleted_at.is_(None))
        .group_by(Hashtag.id, Hashtag.name)
        .order_by(func.count(MemoryHashtag.memory_id).desc(), Hashtag.name.asc())
    ).all()
    data = [{"name": row.name, "count": row.count} for row in rows]
    return build_response(200, "Đã tải danh sách hashtag", request, data=data)


@router.get("/api/memories/{memory_id}/hashtags")
def get_memory_hashtags(
    memory_id: int,
    request: Request,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    memory = load_memory(db, memory_id)
    is_owner = current_user is not None and current_user.id == memory.user_id
    author_active = memory.author is None or memory.author.status == "active"
    if not is_owner and (
        memory.visibility != "public"
        or memory.status != "active"
        or not author_active
    ):
        raise NotFoundException("Không tìm thấy ký ức")
    serialized = serialize_memory(db, memory, current_user)
    return build_response(
        200,
        "Đã tải hashtag của ký ức",
        request,
        data={
            "memory_id": memory.id,
            "hashtags": serialized["hashtags"],
            "hashtag_sources": serialized["hashtag_sources"],
        },
    )


@router.post("/api/memories/{memory_id}/hashtags")
def attach_hashtags_to_memory(
    memory_id: int,
    payload: MemoryHashtagsPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memory = _load_owned_memory(db, memory_id, current_user)
    raw_hashtags = _extract_raw_hashtags(payload)
    sync_memory_hashtags(
        db,
        memory,
        raw_hashtags,
        payload.ai_hashtags,
        replace=payload.replace,
    )
    memory.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(memory)
    return build_response(
        200,
        "Đã gắn hashtag cho ký ức",
        request,
        data=serialize_memory(db, memory, current_user),
    )


@router.put("/api/memories/{memory_id}/hashtags")
@router.patch("/api/memories/{memory_id}/hashtags")
def replace_memory_hashtags(
    memory_id: int,
    payload: MemoryHashtagsPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memory = _load_owned_memory(db, memory_id, current_user)
    raw_hashtags = _extract_raw_hashtags(payload)
    sync_memory_hashtags(
        db,
        memory,
        raw_hashtags if raw_hashtags is not None else [],
        payload.ai_hashtags,
        replace=True,
    )
    memory.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(memory)
    return build_response(
        200,
        "Đã cập nhật hashtag của ký ức",
        request,
        data=serialize_memory(db, memory, current_user),
    )


@router.delete("/api/memories/{memory_id}/hashtags/{tag_name}")
def remove_hashtag_from_memory(
    memory_id: int,
    tag_name: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memory = _load_owned_memory(db, memory_id, current_user)
    normalized = normalize_hashtag(tag_name)
    hashtag = db.scalar(select(Hashtag).where(func.lower(Hashtag.name) == normalized))
    if hashtag is None:
        raise NotFoundException("Không tìm thấy hashtag trên ký ức này")

    link = db.scalar(
        select(MemoryHashtag).where(
            MemoryHashtag.memory_id == memory.id,
            MemoryHashtag.hashtag_id == hashtag.id,
        )
    )
    if link is None:
        raise NotFoundException("Không tìm thấy hashtag trên ký ức này")

    db.execute(
        delete(MemoryHashtag).where(
            MemoryHashtag.memory_id == memory.id,
            MemoryHashtag.hashtag_id == hashtag.id,
        )
    )
    memory.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(memory)
    return build_response(
        200,
        "Đã gỡ hashtag khỏi ký ức",
        request,
        data=serialize_memory(db, memory, current_user),
    )
