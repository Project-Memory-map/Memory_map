"""US-ACC-003 – Đăng nhập bằng tài khoản Google (T05B571).

Luồng giống facebook_router.py: /api/auth/google/login → Google → /api/auth/google/callback → cấp JWT
→ /accounts/oauth-callback.html#token=... (oauth-callback.js lưu token rồi vào bản đồ).
- AC1: chưa có tài khoản → tạo mới, tên hiển thị lấy từ Google.
- AC2: đã có tài khoản cùng email → liên kết vào tài khoản đó (chỉ khi Google xác nhận email_verified,
  tránh chiếm tài khoản bằng email chưa xác thực).
- AC3: từ chối cấp quyền → về trang đăng nhập với "Đăng nhập Google chưa hoàn tất".
- AC4: tài khoản bị khóa → "Tài khoản của bạn đã bị khóa".
"""
from __future__ import annotations

import secrets
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.modules.accounts import service
from app.modules.accounts.models import OAuthAccount, User
from app.modules.accounts.services import google_auth
from app.modules.accounts.services.google_auth import GoogleOAuthError

router = APIRouter(tags=["M1 - Tài khoản"])

GOOGLE_CANCELLED = "Đăng nhập Google chưa hoàn tất"
GOOGLE_LOCKED = "Tài khoản của bạn đã bị khóa"
GOOGLE_CONFLICT = "Không thể liên kết tài khoản Google này"
GOOGLE_UNVERIFIED = "Email Google chưa được xác thực, hãy đăng nhập bằng mật khẩu"
STATE_COOKIE = "google_oauth_state"


def _login_redirect(message: str) -> RedirectResponse:
    response = RedirectResponse(f"/accounts/login.html?{urlencode({'error': message})}", status_code=302)
    response.delete_cookie(STATE_COOKIE, path="/", httponly=True, secure=not settings.is_dev, samesite="lax")
    return response


@router.get("/api/auth/google/login")
def google_login():
    state = secrets.token_urlsafe(32)
    try:
        url = google_auth.authorization_url(state)
    except GoogleOAuthError:
        return _login_redirect(GOOGLE_CANCELLED)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(STATE_COOKIE, state, max_age=600, httponly=True, secure=not settings.is_dev, samesite="lax", path="/")
    return response


@router.get("/api/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    params = request.query_params
    expected, received = request.cookies.get(STATE_COOKIE), params.get("state")
    if params.get("error") or not params.get("code") or not expected or not received \
            or not secrets.compare_digest(expected, received):
        return _login_redirect(GOOGLE_CANCELLED)  # AC3: người dùng chọn "Từ chối" (error=access_denied)
    try:
        profile = await google_auth.profile_from_code(params["code"])
    except GoogleOAuthError:
        return _login_redirect(GOOGLE_CANCELLED)

    oauth = db.scalar(select(OAuthAccount).where(
        OAuthAccount.provider == "google", OAuthAccount.provider_user_id == profile.google_id))
    if oauth is not None:
        user = db.get(User, oauth.user_id)
        if user is None:
            return _login_redirect(GOOGLE_CONFLICT)
    else:
        user = service.find_user_by_email(db, profile.email) if profile.email else None
        if user is not None:
            if not profile.email_verified:
                return _login_redirect(GOOGLE_UNVERIFIED)
            linked = db.scalar(select(OAuthAccount).where(
                OAuthAccount.user_id == user.id, OAuthAccount.provider == "google"))
            if linked is not None and linked.provider_user_id != profile.google_id:
                return _login_redirect(GOOGLE_CONFLICT)
        else:
            user = User(email=profile.email, display_name=profile.display_name, password_hash=None,
                        role="user", status="active", token_version=0, failed_login_count=0)
            db.add(user)
            db.flush()
        db.add(OAuthAccount(user_id=user.id, provider="google", provider_user_id=profile.google_id))

    if user.status == "locked":  # AC4
        db.rollback()
        return _login_redirect(GOOGLE_LOCKED)

    user.last_login_at = datetime.now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _login_redirect(GOOGLE_CONFLICT)
    db.refresh(user)

    token = service.issue_token(user).access_token
    notice = "need_email" if user.email is None else "oauth"
    response = RedirectResponse(f"/accounts/oauth-callback.html#token={token}&notice={notice}", status_code=302)
    response.delete_cookie(STATE_COOKIE, path="/", httponly=True, secure=not settings.is_dev, samesite="lax")
    return response
