from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_media_signature
from app.core.storage import resolve_path
from app.modules.accounts.deps import get_optional_user
from app.modules.accounts.models import User
from app.modules.memories.models import Media, Memory


router = APIRouter(
    prefix="/api/media",
    tags=["M2 - Media"],
)


@router.get("/{media_id}")
def read_media(
    media_id: int,
    exp: int = Query(...),
    sig: str = Query(..., max_length=128),
    viewer: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    item = db.get(Media, media_id)
    memory = db.get(Memory, item.memory_id) if item else None
    author = db.get(User, memory.user_id) if memory else None

    owner = (
        memory
        and viewer
        and memory.user_id == viewer.id
    )

    public = (
        memory
        and author
        and memory.visibility == "public"
        and memory.status == "active"
        and author.status == "active"
    )

    if (
        not memory
        or memory.deleted_at is not None
        or not (owner or public)
        or not verify_media_signature(media_id, exp, sig)
    ):
        raise HTTPException(404, "Không tìm thấy tệp")

    try:
        path = resolve_path(item.file_path)
    except ValueError:
        raise HTTPException(404, "Không tìm thấy tệp")

    if not path.is_file():
        raise HTTPException(404, "Không tìm thấy tệp")

    return FileResponse(
        path,
        media_type=item.mime_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )