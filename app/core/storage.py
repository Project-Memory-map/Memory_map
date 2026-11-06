import uuid
from pathlib import Path

from app.core.config import settings

UPLOAD_SUBDIRS = ("images", "videos", "thumbs", "avatars")


def ensure_upload_dirs() -> None:
    for name in UPLOAD_SUBDIRS:
        (settings.upload_dir / name).mkdir(parents=True, exist_ok=True)


def build_relative_path(subdir: str, extension: str) -> str:
    if subdir not in UPLOAD_SUBDIRS:
        raise ValueError(f"Thư mục lưu trữ không hợp lệ: {subdir}")
    return f"{subdir}/{uuid.uuid4().hex}.{extension.lower().lstrip('.')}"


def resolve_path(relative_path: str) -> Path:
    root = settings.upload_dir.resolve()
    full_path = (root / relative_path).resolve()
    if root not in full_path.parents:
        raise ValueError("Đường dẫn tệp không hợp lệ")
    return full_path


def delete_file(relative_path: str | None) -> None:
    if relative_path:
        resolve_path(relative_path).unlink(missing_ok=True)
