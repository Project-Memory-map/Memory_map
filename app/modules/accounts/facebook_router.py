"""US-ACC-004 – Đăng nhập bằng tài khoản Facebook (T05B572)."""
from __future__ import annotations

from datetime import datetime
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.response import build_response
from app.modules.accounts import service
from app.modules.accounts.models import OAuthAccount, User
from app.modules.accounts.services import facebook_auth
from app.modules.accounts.services.facebook_auth import FacebookOAuthError

router = APIRouter(tags=["M1 - Tài khoản"])

FACEBOOK_CANCELLED = "Đăng nhập Facebook chưa hoàn tất"
FACEBOOK_LOCKED = "Tài khoản của bạn đã bị khóa"
FACEBOOK_CONFLICT = "Không thể liên kết tài khoản Facebook này"
FACEBOOK_STATE_COOKIE = "facebook_oauth_state"


def _cookie_secure() -> bool:
    return not settings.is_dev


def _login_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(
        f"/accounts/login.html?{urlencode({'error': message})}",
        status_code=302,
    )


def _clear_state_cookie(response: RedirectResponse) -> None:
    response.delete_cookie(
        FACEBOOK_STATE_COOKIE,
        path="/",
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
    )


async def _profile_from_callback(request: Request):
    if request.query_params.get("error"):
        raise FacebookOAuthError(400, FACEBOOK_CANCELLED)

    expected_state = request.cookies.get(FACEBOOK_STATE_COOKIE)
    received_state = request.query_params.get("state")
    if (
        not expected_state
        or not received_state
        or not secrets.compare_digest(expected_state, received_state)
    ):
        raise FacebookOAuthError(400, FACEBOOK_CANCELLED)

    code = request.query_params.get("code")
    if not code:
        raise FacebookOAuthError(400, FACEBOOK_CANCELLED)
    return await facebook_auth.profile_from_code(code)


@router.get("/api/auth/facebook/login")
def facebook_login():
    """Bắt đầu Facebook OAuth và gắn state chống giả mạo callback."""
    state = secrets.token_urlsafe(32)
    try:
        auth_url = facebook_auth.authorization_url(state)
    except FacebookOAuthError:
        return _login_redirect(FACEBOOK_CANCELLED)

    response = RedirectResponse(auth_url, status_code=302)
    response.set_cookie(
        FACEBOOK_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )
    return response


@router.get("/api/auth/facebook/callback")
async def facebook_callback(request: Request, db: Session = Depends(get_db)):
    """Đổi mã OAuth lấy hồ sơ, lưu/liên kết OAuthAccount, cấp JWT chuẩn và chuyển hướng."""
    try:
        profile = await _profile_from_callback(request)
    except FacebookOAuthError:
        response = _login_redirect(FACEBOOK_CANCELLED)
        _clear_state_cookie(response)
        return response

    oauth = db.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == "facebook",
            OAuthAccount.provider_user_id == profile.facebook_id,
        )
    )

    if oauth is not None:
        user = db.get(User, oauth.user_id)
        if user is None:
            response = _login_redirect(FACEBOOK_CONFLICT)
            _clear_state_cookie(response)
            return response
    else:
        email_or_none = (
            profile.email.strip().lower()
            if profile.email and profile.email.strip()
            else None
        )
        user = (
            service.find_user_by_email(db, email_or_none)
            if email_or_none is not None
            else None
        )
        if user is not None:
            existing_fb = db.scalar(
                select(OAuthAccount).where(
                    OAuthAccount.user_id == user.id,
                    OAuthAccount.provider == "facebook",
                )
            )
            if (
                existing_fb is not None
                and existing_fb.provider_user_id != profile.facebook_id
            ):
                response = _login_redirect(FACEBOOK_CONFLICT)
                _clear_state_cookie(response)
                return response
            if user.status == "locked":
                response = _login_redirect(FACEBOOK_LOCKED)
                _clear_state_cookie(response)
                return response
            db.add(
                OAuthAccount(
                    user_id=user.id,
                    provider="facebook",
                    provider_user_id=profile.facebook_id,
                )
            )
        else:
            user = User(
                email=email_or_none,
                display_name=profile.display_name,
                password_hash=None,
                role="user",
                status="active",
                token_version=0,
                failed_login_count=0,
            )
            db.add(user)
            db.flush()
            db.add(
                OAuthAccount(
                    user_id=user.id,
                    provider="facebook",
                    provider_user_id=profile.facebook_id,
                )
            )

    if user.status == "locked":
        db.rollback()
        response = _login_redirect(FACEBOOK_LOCKED)
        _clear_state_cookie(response)
        return response

    user.last_login_at = datetime.now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        response = _login_redirect(FACEBOOK_CONFLICT)
        _clear_state_cookie(response)
        return response
    db.refresh(user)

    token = service.issue_token(user).access_token
    notice = "need_email" if user.email is None else "oauth"
    response = RedirectResponse(
        f"/accounts/oauth-callback.html#token={token}&notice={notice}",
        status_code=302,
    )
    _clear_state_cookie(response)
    return response


@router.get("/api/auth/providers")
def get_auth_providers(request: Request):
    return build_response(
        200,
        "OK",
        request,
        data={
            "google": bool(getattr(settings, "google_client_id", "")),
            "facebook": bool(settings.facebook_app_id),
        },
    )
