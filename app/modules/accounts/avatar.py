"""Đường dẫn công khai của ảnh đại diện (US-ACC-006).

users.avatar_path là đường dẫn lưu trữ nội bộ (vd 'avatars/12_ab3f.png'), không được trả thẳng ra API.
Mọi nơi trả tác giả/người dùng gọi avatar_url(user) để có link /api/users/{id}/avatar?v=... (v đổi khi đổi ảnh,
trình duyệt không dùng lại ảnh cũ trong cache).
"""
from __future__ import annotations

from pathlib import PurePosixPath


def avatar_url(user) -> str | None:
    if user is None or not user.avatar_path:
        return None
    version = PurePosixPath(user.avatar_path).stem.rsplit("_", 1)[-1]
    return f"/api/users/{user.id}/avatar?v={version}"
