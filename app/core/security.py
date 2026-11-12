"""Tạo và đọc JWT (access token) cho mọi API cần đăng nhập."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import time

import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def create_access_token(user_id: int, token_version: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    payload = {"sub": str(user_id), "tv": token_version, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def _media_signature(media_id: int, exp: int) -> str:
    message = f"{media_id}:{exp}".encode("utf-8")
    return hmac.new(settings.media_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def sign_media_url(media_id: int) -> str:
    exp = int(time.time()) + int(settings.media_url_expire_seconds)
    sig = _media_signature(media_id, exp)
    return f"/api/media/{media_id}?exp={exp}&sig={sig}"


def verify_media_signature(media_id: int, exp: int, sig: str) -> bool:
    if exp < time.time():
        return False
    expected = _media_signature(media_id, exp)
    return hmac.compare_digest(expected, sig)
