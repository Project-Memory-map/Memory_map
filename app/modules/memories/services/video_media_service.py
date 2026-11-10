from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.modules.memories.services.image_media_service import (
    delete_media_file,
    resolve_upload_path,
)

MAX_VIDEO_BYTES = 50 * 1024 * 1024
VIDEO_CHUNK_BYTES = 1024 * 1024
VIDEO_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
}


class VideoUploadError(Exception):
    pass


@dataclass(frozen=True)
class StagedVideo:
    relative_path: str
    mime_type: str
    size_bytes: int


def _has_video_signature(extension: str, header: bytes) -> bool:
    if len(header) < 8:
        return False
    atom = header[4:8]
    if atom == b"ftyp":
        return len(header) >= 12
    # Legacy QuickTime MOV files may start with a top-level media atom.
    return extension == ".mov" and atom in {b"moov", b"mdat", b"wide", b"free"}


async def stage_video(
    upload: UploadFile,
    configuration: Settings | None = None,
) -> StagedVideo:
    """Stream to demo storage behind a service boundary that can be replaced by R2."""
    extension = Path(upload.filename or "").suffix.lower()
    mime_type = VIDEO_TYPES.get(extension)
    content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if mime_type is None or content_type != mime_type:
        raise VideoUploadError("Định dạng tệp không được hỗ trợ")
    if upload.size is not None and upload.size > MAX_VIDEO_BYTES:
        raise VideoUploadError("Video không được vượt quá 50 MB")

    relative_path = f"videos/{uuid.uuid4().hex}{extension}"
    target = resolve_upload_path(relative_path, configuration)
    partial = target.with_name(f"{target.name}.part")
    target.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    header = bytearray()
    try:
        with partial.open("xb") as output:
            while chunk := await upload.read(VIDEO_CHUNK_BYTES):
                total += len(chunk)
                if total > MAX_VIDEO_BYTES:
                    raise VideoUploadError("Video không được vượt quá 50 MB")
                if len(header) < 12:
                    header.extend(chunk[: 12 - len(header)])
                output.write(chunk)

        if not _has_video_signature(extension, bytes(header)):
            raise VideoUploadError("Định dạng tệp không được hỗ trợ")
        partial.replace(target)
        return StagedVideo(relative_path, mime_type, total)
    except Exception:
        partial.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise


def discard_staged_video(
    video: StagedVideo | None,
    configuration: Settings | None = None,
) -> None:
    if video is not None:
        delete_media_file(video.relative_path, configuration)


def _video_signature(
    media_id: int,
    relative_path: str,
    expires_at: int,
    configuration: Settings,
) -> str:
    secret = getattr(configuration, "media_secret_key", None) or configuration.jwt_secret_key
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY chưa được cấu hình")
    message = f"video:{media_id}:{relative_path}:{expires_at}".encode("utf-8")
    return hmac.new(str(secret).encode("utf-8"), message, hashlib.sha256).hexdigest()


def video_url(media_id: int, relative_path: str, configuration: Settings) -> str:
    lifetime = int(getattr(configuration, "media_url_expire_seconds", 3600))
    expires_at = int(time.time()) + lifetime
    signature = _video_signature(media_id, relative_path, expires_at, configuration)
    return f"/api/media/{media_id}/stream?exp={expires_at}&sig={signature}"


def verify_video_signature(
    media_id: int,
    relative_path: str,
    expires_at: int,
    signature: str,
    configuration: Settings,
) -> bool:
    if expires_at <= int(time.time()):
        return False
    try:
        expected = _video_signature(media_id, relative_path, expires_at, configuration)
    except RuntimeError:
        return False
    return hmac.compare_digest(expected, signature)
