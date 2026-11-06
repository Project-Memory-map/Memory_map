import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int, role: str, token_version: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "tv": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _media_signature(media_id: int, expires_at: int) -> str:
    message = f"{media_id}:{expires_at}".encode("utf-8")
    return hmac.new(settings.media_secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def sign_media_url(media_id: int) -> str:
    expires_at = int(time.time()) + settings.media_url_expire_seconds
    return f"/api/media/{media_id}?exp={expires_at}&sig={_media_signature(media_id, expires_at)}"


def verify_media_signature(media_id: int, expires_at: int, signature: str) -> bool:
    if expires_at < int(time.time()):
        return False
    return hmac.compare_digest(_media_signature(media_id, expires_at), signature)
