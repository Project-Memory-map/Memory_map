from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import UnauthorizedException
from app.core.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_token_payload_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict | None:
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise UnauthorizedException("Phiên đăng nhập không hợp lệ hoặc đã hết hạn")
    return payload


def get_token_payload(payload: dict | None = Depends(get_token_payload_optional)) -> dict:
    if payload is None:
        raise UnauthorizedException()
    return payload
