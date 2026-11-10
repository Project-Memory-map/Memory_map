from __future__ import annotations

import hmac
import secrets
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.core.config import Settings
from app.core.database import (
    AccountLinkConflictError,
    AccountLockedError,
    UserRepository,
)
from app.core.security import MissingJWTSecretError, create_access_token
from app.modules.accounts.deps import get_current_user
from app.modules.accounts.schemas import FacebookTokenRequest
from app.modules.accounts.services.facebook_auth import (
    FacebookAuthService,
    FacebookOAuthError,
    FacebookProfile,
)

router = APIRouter()
STATE_COOKIE = "facebook_oauth_state"
ACCESS_TOKEN_COOKIE = "access_token"
OAUTH_INCOMPLETE_MESSAGE = "Đăng nhập Facebook chưa hoàn tất"
LOCKED_ACCOUNT_MESSAGE = "Tài khoản của bạn đã bị khóa"


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _facebook_service(request: Request) -> FacebookAuthService:
    return request.app.state.facebook_auth


def _repository(request: Request) -> UserRepository:
    return request.app.state.user_repository


def _verify_jwt_configuration(settings: Settings) -> None:
    if not settings.jwt_secret_key:
        raise HTTPException(
            status_code=503,
            detail="JWT_SECRET_KEY chưa được cấu hình",
        )


def _issue_login_response(
    request: Request,
    profile: FacebookProfile,
) -> dict[str, object]:
    settings = _settings(request)
    _verify_jwt_configuration(settings)
    try:
        user = _repository(request).authenticate_facebook(
            facebook_id=profile.facebook_id,
            display_name=profile.display_name,
            email=profile.email,
        )
    except AccountLockedError as exc:
        raise HTTPException(
            status_code=403,
            detail=LOCKED_ACCOUNT_MESSAGE,
        ) from exc
    except AccountLinkConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        token = create_access_token(user, settings)
    except MissingJWTSecretError as exc:
        raise HTTPException(
            status_code=503,
            detail="JWT_SECRET_KEY chưa được cấu hình",
        ) from exc

    return {
        "access_token": token,
        "token_type": "bearer",
        "missing_email": user.email is None,
        "user": {
            "user_id": user.id,
            "display_name": user.display_name,
            "email": user.email,
            "role": user.role,
        },
    }


async def _authenticate_profile(
    request: Request,
    operation: Callable[[], Awaitable[FacebookProfile]],
) -> dict[str, object]:
    _verify_jwt_configuration(_settings(request))
    try:
        profile = await operation()
    except FacebookOAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _issue_login_response(request, profile)


@router.get("/facebook/login")
async def facebook_login(request: Request) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    try:
        authorization_url = _facebook_service(request).authorization_url(state)
    except FacebookOAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    response = RedirectResponse(authorization_url, status_code=302)
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=_settings(request).cookie_secure,
        samesite="lax",
    )
    return response


@router.get("/facebook/callback")
async def facebook_callback(
    request: Request,
    response: Response,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> dict[str, object]:
    if error or not code:
        raise HTTPException(status_code=400, detail=OAUTH_INCOMPLETE_MESSAGE)

    expected_state = request.cookies.get(STATE_COOKIE)
    if not expected_state or not state or not hmac.compare_digest(
        expected_state, state
    ):
        raise HTTPException(status_code=400, detail=OAUTH_INCOMPLETE_MESSAGE)

    result = await _authenticate_profile(
        request,
        lambda: _facebook_service(request).profile_from_code(code),
    )
    response.delete_cookie(STATE_COOKIE, httponly=True, samesite="lax")
    return result


@router.post("/facebook/token")
async def facebook_token_login(
    request: Request,
    body: FacebookTokenRequest,
) -> dict[str, object]:
    return await _authenticate_profile(
        request,
        lambda: _facebook_service(request).profile_from_access_token(
            body.access_token
        ),
    )


@router.post("/logout", dependencies=[Depends(get_current_user)])
def logout(
    request: Request,
    response: Response,
) -> dict[str, str]:
    response.delete_cookie(
        ACCESS_TOKEN_COOKIE,
        httponly=True,
        secure=_settings(request).cookie_secure,
        samesite="lax",
    )
    return {"message": "Đăng xuất thành công"}