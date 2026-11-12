from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import BadRequestException, ForbiddenException, NotFoundException
from app.core.response import build_response
from app.modules.accounts.deps import get_current_user, get_current_user_optional
from app.modules.accounts.models import User
from app.modules.memories.models import Media, Memory
from app.modules.memories.services.image_media_service import (
    delete_media_file,
    resolve_upload_path,
)
from app.modules.memories.services.video_media_service import (
    StagedVideo,
    VideoUploadError,
    discard_staged_video,
    stage_video,
    verify_video_signature,
    video_url,
)

router = APIRouter(tags=["M2 - Video ký ức"])
_STREAM_CHUNK_BYTES = 64 * 1024


def _visible_memory(db: Session, memory_id: int, current_user: User | None) -> Memory:
    memory = db.scalar(select(Memory).where(Memory.id == memory_id))
    if memory is None or memory.deleted_at is not None:
        raise NotFoundException("Không tìm thấy ký ức")
    is_owner = current_user is not None and current_user.id == memory.user_id
    if not is_owner and (memory.visibility != "public" or memory.status != "active"):
        raise NotFoundException("Không tìm thấy ký ức")
    return memory


def _serialize_video(media: Media) -> dict[str, object]:
    return {
        "id": media.id,
        "type": "video",
        "url": video_url(media.id, media.file_path),
        "mime_type": media.mime_type,
        "size_bytes": media.size_bytes,
        "sort_order": media.sort_order,
    }


@router.get("/api/memories/{memory_id}/video")
def get_memory_video(
    memory_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    memory = _visible_memory(db, memory_id, current_user)
    media = db.scalar(
        select(Media).where(Media.memory_id == memory.id, Media.media_type == "video")
    )
    return build_response(
        200,
        "Đã tải video của ký ức",
        request,
        data=_serialize_video(media) if media is not None else None,
    )


@router.post("/api/memories/{memory_id}/video")
async def update_memory_video(
    memory_id: int,
    request: Request,
    video: list[UploadFile] = File(default=[]),
    remove_video: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memory = db.scalar(select(Memory).where(Memory.id == memory_id).with_for_update())
    if memory is None or memory.deleted_at is not None:
        raise NotFoundException("Không tìm thấy ký ức")
    if memory.user_id != current_user.id:
        raise ForbiddenException("Bạn không có quyền thay đổi video của ký ức này")
    if len(video) > 1:
        raise BadRequestException("Mỗi ký ức chỉ có 1 video")

    existing = db.scalars(
        select(Media)
        .where(Media.memory_id == memory.id, Media.media_type == "video")
        .order_by(Media.sort_order, Media.id)
        .with_for_update()
    ).all()
    if video and existing and not remove_video:
        raise BadRequestException("Mỗi ký ức chỉ có 1 video")
    if not video and not remove_video:
        current = existing[0] if existing else None
        return build_response(
            200,
            "Video của ký ức không thay đổi",
            request,
            data=_serialize_video(current) if current is not None else None,
        )

    staged: StagedVideo | None = None
    old_file_paths = [row.file_path for row in existing] if remove_video else []
    try:
        if video:
            staged = await stage_video(video[0])
        if remove_video:
            for row in existing:
                db.delete(row)
            db.flush()
        saved = None
        if staged is not None:
            next_order = db.scalar(
                select(func.coalesce(func.max(Media.sort_order), -1)).where(
                    Media.memory_id == memory.id
                )
            ) + 1
            saved = Media(
                memory_id=memory.id,
                media_type="video",
                file_path=staged.relative_path,
                thumb_path=None,
                mime_type=staged.mime_type,
                size_bytes=staged.size_bytes,
                sort_order=next_order,
            )
            db.add(saved)
            db.flush()
        db.commit()
    except VideoUploadError as exc:
        db.rollback()
        discard_staged_video(staged)
        raise BadRequestException(str(exc)) from exc
    except Exception:
        db.rollback()
        discard_staged_video(staged)
        raise

    for file_path in old_file_paths:
        delete_media_file(file_path)
    return build_response(
        200,
        "Đã cập nhật video của ký ức",
        request,
        data=_serialize_video(saved) if saved is not None else None,
    )


def _byte_range(value: str, size: int) -> tuple[int, int] | None:
    if not value.startswith("bytes=") or "," in value:
        return None
    first, separator, last = value[6:].partition("-")
    if not separator:
        return None
    try:
        if not first:
            suffix_length = int(last)
            if suffix_length <= 0:
                return None
            return max(size - suffix_length, 0), size - 1
        start = int(first)
        end = int(last) if last else size - 1
    except ValueError:
        return None
    if start < 0 or start >= size or end < start:
        return None
    return start, min(end, size - 1)


def _file_chunks(path: Path, start: int, length: int) -> Iterator[bytes]:
    with path.open("rb") as stream:
        stream.seek(start)
        remaining = length
        while remaining:
            chunk = stream.read(min(_STREAM_CHUNK_BYTES, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.get("/api/media/{media_id}/stream")
def stream_video(
    media_id: int,
    request: Request,
    exp: int = Query(...),
    sig: str = Query(..., min_length=64, max_length=64),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    media = db.scalar(
        select(Media).where(Media.id == media_id, Media.media_type == "video")
    )
    if media is None:
        raise NotFoundException("Không tìm thấy tệp")
    if not verify_video_signature(media_id, media.file_path, exp, sig):
        raise NotFoundException("Không tìm thấy tệp")
    try:
        memory = _visible_memory(db, media.memory_id, current_user)
    except NotFoundException as exc:
        raise NotFoundException("Không tìm thấy tệp") from exc
    try:
        path = resolve_upload_path(media.file_path)
    except ValueError as exc:
        raise NotFoundException("Không tìm thấy tệp") from exc
    if not path.is_file():
        raise NotFoundException("Không tìm thấy tệp")

    size = path.stat().st_size
    requested_range = request.headers.get("range")
    selected_range = _byte_range(requested_range, size) if requested_range else None
    if requested_range and selected_range is None:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    start, end = selected_range or (0, size - 1)
    length = end - start + 1
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    }
    if selected_range:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    if memory.visibility != "public" or memory.status != "active":
        headers["Cache-Control"] = "private, no-store"
    return StreamingResponse(
        _file_chunks(path, start, length),
        status_code=206 if selected_range else 200,
        media_type=media.mime_type,
        headers=headers,
    )
