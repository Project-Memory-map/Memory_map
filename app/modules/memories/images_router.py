from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import BadRequestException, ForbiddenException, NotFoundException
from app.core.response import build_response
from app.core.security import sign_media_url, verify_media_signature
from app.modules.accounts.deps import get_current_user, get_current_user_optional
from app.modules.accounts.models import User
from app.modules.memories.models import Media, Memory
from app.modules.memories.services.image_media_service import (
    MAX_IMAGE_COUNT,
    ImageUploadError,
    StagedImage,
    delete_media_file,
    discard_staged,
    resolve_upload_path,
    stage_images,
)

router = APIRouter(tags=["M2 - Ảnh ký ức"])


def _parse_ids(value: str | None) -> list[int]:
    if not value:
        return []
    try:
        parsed = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise BadRequestException("Danh sách ảnh không hợp lệ") from exc
    if any(item <= 0 for item in parsed) or len(parsed) != len(set(parsed)):
        raise BadRequestException("Danh sách ảnh không hợp lệ")
    return parsed


def _serialize(media: Media) -> dict[str, object]:
    url = sign_media_url(media.id)
    return {
        "id": media.id,
        "type": media.media_type,
        "url": url,
        "thumb_url": url,
        "mime_type": media.mime_type,
        "size_bytes": media.size_bytes,
        "sort_order": media.sort_order,
    }


def _visible_memory(
    db: Session,
    memory_id: int,
    current_user: User | None,
) -> Memory:
    memory = db.scalar(select(Memory).where(Memory.id == memory_id))
    if memory is None or memory.deleted_at is not None:
        raise NotFoundException("Không tìm thấy ký ức")
    is_owner = current_user is not None and current_user.id == memory.user_id
    if not is_owner and (memory.visibility != "public" or memory.status != "active"):
        raise NotFoundException("Không tìm thấy ký ức")
    return memory


@router.get("/api/memories/{memory_id}/images")
def list_memory_images(
    memory_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    memory = _visible_memory(db, memory_id, current_user)
    rows = db.scalars(
        select(Media)
        .where(Media.memory_id == memory.id, Media.media_type == "image")
        .order_by(Media.sort_order, Media.id)
    ).all()
    return build_response(
        200,
        "Đã tải danh sách ảnh",
        request,
        data=[_serialize(row) for row in rows],
    )


@router.post("/api/memories/{memory_id}/images")
async def update_memory_images(
    memory_id: int,
    request: Request,
    images: list[UploadFile] = File(default=[]),
    remove_media_ids: str | None = Form(None),
    image_order: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memory = db.scalar(
        select(Memory).where(Memory.id == memory_id).with_for_update()
    )
    if memory is None or memory.deleted_at is not None:
        raise NotFoundException("Không tìm thấy ký ức")
    if memory.user_id != current_user.id:
        raise ForbiddenException("Bạn không có quyền thêm ảnh vào ký ức này")

    remove_ids = _parse_ids(remove_media_ids)
    existing = db.scalars(
        select(Media)
        .where(Media.memory_id == memory.id, Media.media_type == "image")
        .order_by(Media.sort_order, Media.id)
        .with_for_update()
    ).all()
    by_id = {media.id: media for media in existing}
    if any(media_id not in by_id for media_id in remove_ids):
        raise NotFoundException("Không tìm thấy ảnh của ký ức")

    remaining = [media for media in existing if media.id not in set(remove_ids)]
    if image_order is not None:
        requested_order = _parse_ids(image_order)
        if len(requested_order) != len(remaining) or set(requested_order) != {
            media.id for media in remaining
        }:
            raise BadRequestException("Thứ tự ảnh không hợp lệ")
        remaining_by_id = {media.id: media for media in remaining}
        remaining = [remaining_by_id[media_id] for media_id in requested_order]

    if len(remaining) + len(images) > MAX_IMAGE_COUNT:
        raise BadRequestException("Mỗi ký ức tối đa 10 ảnh")

    staged: list[StagedImage] = []
    old_file_paths = [by_id[media_id].file_path for media_id in remove_ids]
    try:
        staged = await stage_images(images)
        for media_id in remove_ids:
            db.delete(by_id[media_id])
        db.flush()

        new_rows: list[Media] = []
        for item in staged:
            media = Media(
                memory_id=memory.id,
                media_type="image",
                file_path=item.relative_path,
                thumb_path=None,
                mime_type=item.mime_type,
                size_bytes=item.size_bytes,
                sort_order=0,
            )
            db.add(media)
            db.flush()
            new_rows.append(media)

        ordered_rows = remaining + new_rows
        for sort_order, media in enumerate(ordered_rows):
            media.sort_order = sort_order
        db.commit()
    except ImageUploadError as exc:
        db.rollback()
        discard_staged(staged)
        raise BadRequestException(str(exc)) from exc
    except Exception:
        db.rollback()
        discard_staged(staged)
        raise

    for file_path in old_file_paths:
        delete_media_file(file_path)

    rows = db.scalars(
        select(Media)
        .where(Media.memory_id == memory.id, Media.media_type == "image")
        .order_by(Media.sort_order, Media.id)
    ).all()
    return build_response(
        200,
        "Đã cập nhật ảnh của ký ức",
        request,
        data=[_serialize(row) for row in rows],
    )


@router.get("/api/media/{media_id}")
def get_media_file(
    media_id: int,
    exp: int = Query(...),
    sig: str = Query(..., min_length=64, max_length=64),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    if not verify_media_signature(media_id, exp, sig):
        raise NotFoundException("Không tìm thấy tệp")
    media = db.scalar(select(Media).where(Media.id == media_id))
    if media is None:
        raise NotFoundException("Không tìm thấy tệp")
    memory = db.scalar(select(Memory).where(Memory.id == media.memory_id))
    if memory is None:
        raise NotFoundException("Không tìm thấy tệp")
    try:
        _visible_memory(db, memory.id, current_user)
    except NotFoundException as exc:
        raise NotFoundException("Không tìm thấy tệp") from exc
    headers = (
        {"Cache-Control": "private, no-store"}
        if memory.visibility != "public" or memory.status != "active"
        else None
    )
    try:
        path = resolve_upload_path(media.file_path)
    except ValueError as exc:
        raise NotFoundException("Không tìm thấy tệp") from exc
    if not path.is_file():
        raise NotFoundException("Không tìm thấy tệp")
    return FileResponse(path, media_type=media.mime_type, headers=headers)
