from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import BASE_DIR, Settings, settings

MAX_IMAGE_COUNT = 10
MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".png": ("image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    ".webp": (
        "image/webp",
        lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
    ),
    ".gif": (
        "image/gif",
        lambda data: data.startswith((b"GIF87a", b"GIF89a")),
    ),
}


class ImageUploadError(Exception):
    pass


@dataclass(frozen=True)
class StagedImage:
    relative_path: str
    mime_type: str
    size_bytes: int


def upload_root(configuration: Settings | None = None) -> Path:
    """Use the configured uploads directory when present, otherwise project uploads/."""
    configuration = configuration or settings
    configured = getattr(configuration, "upload_dir", BASE_DIR / "uploads")
    return Path(configured).expanduser().resolve()


def resolve_upload_path(
    relative_path: str,
    configuration: Settings | None = None,
) -> Path:
    root = upload_root(configuration)
    path = (root / relative_path).resolve()
    if root not in path.parents:
        raise ValueError("Đường dẫn tệp không hợp lệ")
    return path


async def stage_images(
    files: list[UploadFile],
    configuration: Settings | None = None,
) -> list[StagedImage]:
    staged: list[StagedImage] = []
    try:
        for upload in files:
            extension = Path(upload.filename or "").suffix.lower()
            expected = IMAGE_TYPES.get(extension)
            content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
            if expected is None or content_type != expected[0]:
                raise ImageUploadError("Định dạng tệp không được hỗ trợ")
            if upload.size is not None and upload.size > MAX_IMAGE_BYTES:
                raise ImageUploadError("Mỗi ảnh không được vượt quá 5 MB")

            content = await upload.read(MAX_IMAGE_BYTES + 1)
            if len(content) > MAX_IMAGE_BYTES:
                raise ImageUploadError("Mỗi ảnh không được vượt quá 5 MB")
            if not expected[1](content):
                raise ImageUploadError("Định dạng tệp không được hỗ trợ")

            relative_path = f"images/{uuid.uuid4().hex}{extension}"
            target = resolve_upload_path(relative_path, configuration)
            target.parent.mkdir(parents=True, exist_ok=True)
            staged_file = StagedImage(relative_path, expected[0], len(content))
            staged.append(staged_file)
            target.write_bytes(content)
        return staged
    except Exception:
        discard_staged(staged, configuration)
        raise


def discard_staged(
    files: list[StagedImage],
    configuration: Settings | None = None,
) -> None:
    for item in files:
        try:
            resolve_upload_path(item.relative_path, configuration).unlink(missing_ok=True)
        except (OSError, ValueError):
            pass


def delete_media_file(
    relative_path: str | None,
    configuration: Settings | None = None,
) -> None:
    if relative_path:
        try:
            resolve_upload_path(relative_path, configuration).unlink(missing_ok=True)
        except (OSError, ValueError):
            pass


def media_signature(
    media_id: int,
    expires_at: int,
    configuration: Settings | None = None,
) -> str:
    configuration = configuration or settings
    secret = getattr(configuration, "media_secret_key", None) or configuration.jwt_secret_key
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY chưa được cấu hình")
    message = f"{media_id}:{expires_at}".encode("utf-8")
    return hmac.new(str(secret).encode("utf-8"), message, hashlib.sha256).hexdigest()


def signed_media_url(media_id: int, configuration: Settings | None = None) -> str:
    configuration = configuration or settings
    lifetime = int(getattr(configuration, "media_url_expire_seconds", 3600))
    expires_at = int(time.time()) + lifetime
    signature = media_signature(media_id, expires_at, configuration)
    return f"/api/media/{media_id}?exp={expires_at}&sig={signature}"


def verify_media_signature(
    media_id: int,
    expires_at: int,
    signature: str,
    configuration: Settings | None = None,
) -> bool:
    if expires_at <= int(time.time()):
        return False
    try:
        expected = media_signature(media_id, expires_at, configuration)
    except RuntimeError:
        return False
    return hmac.compare_digest(expected, signature)
