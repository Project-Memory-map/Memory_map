"""M1 – Tài khoản và người dùng.

Giao diện đã có sẵn (ui/ + js/). Các API dưới đây là việc cần làm, js/ đang gọi đúng các
đường dẫn này. Chưa làm thì giao diện báo "Chức năng này chưa được xây dựng".

| Task        | Phương thức + đường dẫn                         | Gọi từ                          |
|-------------|-------------------------------------------------|---------------------------------|
| US-ACC-001  | POST  /api/auth/register                        | js/accounts.js (register.html)  |
| US-ACC-002  | POST  /api/auth/login                           | js/accounts.js (login.html)     |
| US-ACC-002  | GET   /api/auth/me                              | js/account-menu.js (mọi trang)  |
| US-ACC-003  | GET   /api/auth/google/login  + /callback       | login.html, register.html       |
| US-ACC-004  | GET   /api/auth/facebook/login + /callback      | login.html, register.html       |
| US-ACC-003/4| GET   /api/auth/providers                       | js/accounts.js                  |
| US-ACC-005  | POST  /api/auth/forgot-password                 | forgot-password.html            |
| US-ACC-005  | POST  /api/auth/reset-password                  | reset-password.html             |
| US-ACC-006  | PATCH /api/users/me                             | js/profile.js                   |
| US-ACC-006  | POST / DELETE /api/users/me/avatar              | js/profile.js                   |
| US-ACC-006  | GET   /api/users/me/stats                       | js/profile.js                   |
| US-ACC-007  | POST  /api/auth/change-password                 | js/profile.js                   |
| US-ACC-008  | POST  /api/auth/logout                          | js/account-menu.js              |

Bảng dùng: users, oauth_accounts, password_reset_tokens (models.py).
Mọi API trả về qua core/response.py build_response(), báo lỗi bằng lớp trong core/errors.py.
"""
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError

from app.core.security import MissingJWTSecretError, create_access_token
from app.core.response import build_response
from app.modules.accounts.deps import get_current_user
from app.modules.accounts.models import User
from app.modules.accounts.repository import FacebookAccountConflict
from app.modules.accounts.schemas import FacebookTokenRequest
from app.modules.accounts.services.facebook_auth import FacebookOAuthError

router = APIRouter(tags=["M1 - Tài khoản"])

FACEBOOK_CANCELLED = "Đăng nhập Facebook chưa hoàn tất"
FACEBOOK_LOCKED = "Tài khoản của bạn đã bị khóa"
FACEBOOK_STATE_COOKIE = "facebook_oauth_state"


def _cookie_secure(request: Request) -> bool:
    return not request.app.state.settings.is_dev


def _login_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(
        f"/accounts/login.html?{urlencode({'error': message})}",
        status_code=302,
    )


def _clear_state_cookie(response: RedirectResponse | JSONResponse, request: Request) -> None:
    response.delete_cookie(
        FACEBOOK_STATE_COOKIE,
        path="/",
        httponly=True,
        secure=_cookie_secure(request),
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
    return await request.app.state.facebook_auth.profile_from_code(code)


def _complete_login(request: Request, profile):
    repository = request.app.state.user_repository
    try:
        user = repository.resolve_facebook_profile(profile)
    except FacebookAccountConflict:
        return None, JSONResponse(
            status_code=409,
            content={"detail": "Tài khoản Facebook đã được liên kết với tài khoản khác"},
        )
    except IntegrityError:
        return None, JSONResponse(
            status_code=409,
            content={"detail": "Tài khoản Facebook đã được liên kết với tài khoản khác"},
        )

    if user.status == "locked":
        return None, JSONResponse(
            status_code=403,
            content={"detail": FACEBOOK_LOCKED},
        )
    try:
        token = create_access_token(user, request.app.state.settings)
    except MissingJWTSecretError:
        return None, JSONResponse(
            status_code=503,
            content={"detail": "JWT_SECRET_KEY chưa được cấu hình"},
        )
    return {
        "access_token": token,
        "token_type": "bearer",
        "missing_email": user.email is None,
        "user": {
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
        },
    }, None


@router.get("/api/auth/me")
def current_user_profile(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Return the shared session profile consumed by the existing map and profile UI."""
    data = {
        "user_id": current_user.id,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "role": current_user.role,
        "avatar_url": current_user.avatar_path,
        "bio": current_user.bio,
        "created_at": current_user.created_at,
        "has_password": bool(current_user.password_hash),
        "providers": request.app.state.user_repository.get_providers(current_user.id),
    }
    return build_response(200, "Thông tin người dùng", request, data=data)


@router.get("/api/auth/facebook/login")
@router.get("/api/accounts/facebook/login", include_in_schema=False)
def facebook_login(request: Request):
    """Bắt đầu Facebook OAuth và gắn state chống giả mạo callback."""
    state = secrets.token_urlsafe(32)
    try:
        authorization_url = request.app.state.facebook_auth.authorization_url(state)
    except FacebookOAuthError as exc:
        return _login_redirect(FACEBOOK_CANCELLED)

    response = RedirectResponse(authorization_url, status_code=302)
    response.set_cookie(
        FACEBOOK_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=_cookie_secure(request),
        samesite="lax",
        path="/",
    )
    return response


@router.get("/api/auth/facebook/callback")
async def facebook_callback(request: Request):
    """Đổi mã OAuth lấy hồ sơ, cấp JWT chung rồi chuyển về giao diện có sẵn."""
    try:
        profile = await _profile_from_callback(request)
    except FacebookOAuthError as exc:
        response = _login_redirect(FACEBOOK_CANCELLED)
        _clear_state_cookie(response, request)
        return response

    result, error_response = _complete_login(request, profile)
    if error_response is not None:
        if error_response.status_code == 403:
            response = _login_redirect(FACEBOOK_LOCKED)
        elif error_response.status_code == 409:
            response = _login_redirect("Không thể liên kết tài khoản Facebook này")
        else:
            response = _login_redirect(FACEBOOK_CANCELLED)
        _clear_state_cookie(response, request)
        return response

    notice = "need_email" if result["missing_email"] else "oauth"
    callback_url = "/accounts/oauth-callback.html#" + urlencode(
        {"token": result["access_token"], "notice": notice}
    )
    response = RedirectResponse(callback_url, status_code=302)
    _clear_state_cookie(response, request)
    return response


@router.post("/api/accounts/facebook/token", include_in_schema=False)
async def facebook_token_login(payload: FacebookTokenRequest, request: Request):
    """Exchange a Facebook access token for the application's standard JWT."""
    try:
        profile = await request.app.state.facebook_auth.profile_from_access_token(
            payload.access_token
        )
    except FacebookOAuthError as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    result, error_response = _complete_login(request, profile)
    return error_response or JSONResponse(content=result)


@router.get("/api/accounts/facebook/callback", include_in_schema=False)
async def facebook_callback_result(request: Request):
    """JSON callback endpoint retained for API clients and the Facebook flow tests."""
    try:
        profile = await _profile_from_callback(request)
    except FacebookOAuthError as exc:
        response = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
        _clear_state_cookie(response, request)
        return response
    except Exception:
        response = JSONResponse(
            status_code=502,
            content={"detail": FACEBOOK_CANCELLED},
        )
        _clear_state_cookie(response, request)
        return response

    result, error_response = _complete_login(request, profile)
    response = error_response or JSONResponse(content=result)
    _clear_state_cookie(response, request)
    return response
