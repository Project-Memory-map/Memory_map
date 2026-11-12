"""US-ACC-004 – Đăng nhập bằng tài khoản Facebook (T05B572)."""
from __future__ import annotations

import asyncio
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import select

from app.core.config import Settings, settings
from app.core.security import decode_access_token
from app.modules.accounts.models import OAuthAccount, User
from app.modules.accounts.services import facebook_auth
from app.modules.accounts.services.facebook_auth import (
    FacebookAuthService,
    FacebookOAuthError,
    FacebookProfile,
)


def _mock_facebook(
    monkeypatch: pytest.MonkeyPatch,
    *,
    profile: FacebookProfile | None = None,
    error: FacebookOAuthError | None = None,
) -> None:
    monkeypatch.setattr(settings, "facebook_app_id", "test-app-id")
    monkeypatch.setattr(settings, "facebook_app_secret", "test-app-secret")

    target_profile = profile or FacebookProfile(
        facebook_id="fb-123",
        display_name="Facebook User",
        email="user@example.com",
    )

    async def fake_profile_from_code(code: str) -> FacebookProfile:
        if error is not None:
            raise error
        return target_profile

    monkeypatch.setattr(facebook_auth, "profile_from_code", fake_profile_from_code)


def _start_and_callback(client, code: str = "valid-code"):
    start = client.get("/api/auth/facebook/login", follow_redirects=False)
    state = client.cookies.get("facebook_oauth_state")
    callback = client.get(
        "/api/auth/facebook/callback",
        params={"code": code, "state": state},
        follow_redirects=False,
    )
    return start, callback


def test_ac1_dang_nhap_facebook_lan_dau_tao_user_va_oauth_account(
    client,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_facebook(monkeypatch)

    start, callback = _start_and_callback(client)

    assert start.status_code == 302
    assert "facebook.com/dialog/oauth" in start.headers["location"]
    assert callback.status_code == 302

    destination = urlsplit(callback.headers["location"])
    assert destination.path == "/accounts/oauth-callback.html"
    fragment = parse_qs(destination.fragment)
    assert fragment["notice"] == ["oauth"]

    token = fragment["token"][0]
    user = db_session.scalar(select(User).where(User.email == "user@example.com"))
    assert user is not None
    assert user.display_name == "Facebook User"
    assert user.password_hash is None
    assert user.role == "user"
    assert user.status == "active"

    oauth = db_session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == "facebook",
            OAuthAccount.provider_user_id == "fb-123",
        )
    )
    assert oauth is not None
    assert oauth.user_id == user.id

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == str(user.id)
    assert payload["tv"] == user.token_version


def test_ac2_facebook_khong_tra_ve_email_tao_user_email_none_va_nhac_need_email(
    client,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = FacebookProfile(
        facebook_id="fb-no-email",
        display_name="No Email User",
        email=None,
    )
    _mock_facebook(monkeypatch, profile=profile)

    start, callback = _start_and_callback(client)

    assert start.status_code == 302
    assert callback.status_code == 302

    destination = urlsplit(callback.headers["location"])
    fragment = parse_qs(destination.fragment)
    assert destination.path == "/accounts/oauth-callback.html"
    assert fragment["notice"] == ["need_email"]

    oauth = db_session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == "facebook",
            OAuthAccount.provider_user_id == "fb-no-email",
        )
    )
    assert oauth is not None
    user = db_session.get(User, oauth.user_id)
    assert user is not None
    assert user.email is None
    assert user.password_hash is None


@pytest.mark.parametrize(
    "query",
    [
        {"error": "access_denied"},
        {"state": "wrong-state", "code": "valid-code"},
        {"state": "missing-code"},
    ],
)
def test_ac3_nguoi_dung_huy_hoac_callback_khong_hop_le_redirect_ve_login(
    client,
    monkeypatch: pytest.MonkeyPatch,
    query: dict[str, str],
) -> None:
    _mock_facebook(monkeypatch)
    client.get("/api/auth/facebook/login", follow_redirects=False)

    response = client.get(
        "/api/auth/facebook/callback",
        params=query,
        follow_redirects=False,
    )

    destination = urlsplit(response.headers["location"])
    assert response.status_code == 302
    assert destination.path == "/accounts/login.html"
    assert parse_qs(destination.query)["error"] == ["Đăng nhập Facebook chưa hoàn tất"]


def test_trung_email_voi_tai_khoan_co_san_tu_dong_lien_ket(
    client,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = User(
        email="existing@example.com",
        display_name="Original Name",
        password_hash="hashed-password",
        role="user",
        status="active",
        token_version=3,
    )
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    profile = FacebookProfile(
        facebook_id="fb-linked",
        display_name="New Facebook Name",
        email="EXISTING@example.com",
    )
    _mock_facebook(monkeypatch, profile=profile)

    _, callback = _start_and_callback(client)

    destination = urlsplit(callback.headers["location"])
    fragment = parse_qs(destination.fragment)
    assert destination.path == "/accounts/oauth-callback.html"
    assert fragment["notice"] == ["oauth"]

    payload = decode_access_token(fragment["token"][0])
    assert payload is not None
    assert payload["sub"] == str(existing.id)
    assert payload["tv"] == 3

    db_session.refresh(existing)
    assert existing.display_name == "Original Name"
    assert existing.password_hash == "hashed-password"

    oauth = db_session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.user_id == existing.id,
            OAuthAccount.provider == "facebook",
        )
    )
    assert oauth is not None
    assert oauth.provider_user_id == "fb-linked"


def test_xung_dot_lien_ket_facebook_id_khac_redirect_loi(
    client,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = User(
        email="conflict@example.com",
        display_name="Conflict User",
        password_hash=None,
        role="user",
        status="active",
        token_version=0,
    )
    db_session.add(existing)
    db_session.flush()
    db_session.add(
        OAuthAccount(
            user_id=existing.id,
            provider="facebook",
            provider_user_id="fb-old",
        )
    )
    db_session.commit()

    profile = FacebookProfile(
        facebook_id="fb-other",
        display_name="Conflict User",
        email="conflict@example.com",
    )
    _mock_facebook(monkeypatch, profile=profile)

    _, callback = _start_and_callback(client)

    destination = urlsplit(callback.headers["location"])
    assert callback.status_code == 302
    assert destination.path == "/accounts/login.html"
    assert parse_qs(destination.query)["error"] == [
        "Không thể liên kết tài khoản Facebook này"
    ]


def test_tai_khoan_bi_khoa_chan_dang_nhap_facebook(
    client,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    locked_user = User(
        email="locked@example.com",
        display_name="Locked User",
        password_hash=None,
        role="user",
        status="locked",
        token_version=0,
    )
    db_session.add(locked_user)
    db_session.commit()

    profile = FacebookProfile(
        facebook_id="fb-locked",
        display_name="Locked User",
        email="locked@example.com",
    )
    _mock_facebook(monkeypatch, profile=profile)

    _, callback = _start_and_callback(client)

    destination = urlsplit(callback.headers["location"])
    assert callback.status_code == 302
    assert destination.path == "/accounts/login.html"
    assert parse_qs(destination.query)["error"] == ["Tài khoản của bạn đã bị khóa"]


def test_get_auth_providers_tra_ve_trang_thai_cau_hinh(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "facebook_app_id", "fb-app-123")
    res_enabled = client.get("/api/auth/providers")
    body_enabled = res_enabled.json()

    assert res_enabled.status_code == 200
    assert body_enabled["statusCode"] == 200
    assert body_enabled["message"] == "OK"
    assert body_enabled["data"]["facebook"] is True
    assert "google" in body_enabled["data"]

    monkeypatch.setattr(settings, "facebook_app_id", "")
    res_disabled = client.get("/api/auth/providers")
    assert res_disabled.json()["data"]["facebook"] is False


@pytest.mark.parametrize(
    ("handler_name", "status_code"),
    [
        ("timeout", 502),
        ("invalid_token", 401),
    ],
)
def test_facebook_graph_timeout_and_invalid_token_mapping(
    handler_name: str,
    status_code: int,
) -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("request timed out", request=request)

    def invalid_token_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"code": 190, "message": "Invalid OAuth access token"}},
            request=request,
        )

    custom_settings = Settings(
        facebook_app_id="test-app-id",
        facebook_app_secret="test-app-secret",
    )
    handler = {
        "timeout": timeout_handler,
        "invalid_token": invalid_token_handler,
    }[handler_name]
    service = FacebookAuthService(custom_settings, transport=httpx.MockTransport(handler))

    with pytest.raises(FacebookOAuthError) as error:
        asyncio.run(service.profile_from_access_token("invalid-token"))

    assert error.value.status_code == status_code

