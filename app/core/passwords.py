"""Băm và kiểm tra mật khẩu bằng bcrypt (BR-07). JWT nằm ở security.py."""
import bcrypt

PASSWORD_MAX_BYTES = 72  # bcrypt chỉ nhận tối đa 72 byte


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    raw = password.encode("utf-8")
    if not password_hash or len(raw) > PASSWORD_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode("utf-8"))
    except ValueError:
        return False