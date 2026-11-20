"""US-ACC-003 – Đăng nhập bằng tài khoản Google (Google được giả lập, không gọi mạng)."""
from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs, urlsplit

import pytest

from app.core.config import settings
from app.core.passwords import hash_password
from app.modules.accounts import google_router
from app.modules.accounts.models import OAuthAccount, User
from app.modules.accounts.services.google_auth import GoogleOAuthError, GoogleProfile
from app.modules.memories.models import Memory


@pytest.fixture(autouse=True)
def _google_configured(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "client-secret")


def _fake_profile(monkeypatch, profile: GoogleProfile | None = None, error: Exception | None = None):
    async def fake(code):
        if error:
            raise error
        return profile

    monkeypatch.setattr(google_router.google_auth, "profile_from_code", fake)


def _callback(client, **params):
    client.cookies.set("google_oauth_state", "state-ok")
    return client.get("/api/auth/google/callback", params={"state": "state-ok", "code": "abc", **params}, follow_redirects=False)


def _token(response) -> str:
    fragment = urlsplit(response.headers["location"]).fragment
    return parse_qs(fragment)["token"][0]


def _error(response) -> str:
    return parse_qs(urlsplit(response.headers["location"]).query)["error"][0]


def test_login_chuyen_toi_google_kem_state(client):
    res = client.get("/api/auth/google/login", follow_redirects=False)
    assert res.status_code == 302
    location = res.headers["location"]
    assert location.startswith("https://accounts.google.com/")
    assert parse_qs(urlsplit(location).query)["state"][0] == res.cookies.get("google_oauth_state")


def test_ac1_lan_dau_tao_tai_khoan_ten_tu_google(client, db_session, monkeypatch):
    _fake_profile(monkeypatch, GoogleProfile("g-1", "An Nguyễn", "an@gmail.com", True))
    res = _callback(client)
    assert res.status_code == 302
    assert res.headers["location"].startswith("/accounts/oauth-callback.html#token=")

    user = db_session.query(User).filter_by(email="an@gmail.com").one()
    assert user.display_name == "An Nguyễn" and user.password_hash is None
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {_token(res)}"})
    assert me.json()["data"]["providers"] == ["google"]


def test_ac2_trung_email_lien_ket_vao_tai_khoan_cu(client, db_session, monkeypatch):
    user = User(email="an@gmail.com", password_hash=hash_password("Matkhau123"), display_name="An", role="user",
                status="active", token_version=0)
    db_session.add(user)
    db_session.flush()
    for i in range(3):
        db_session.add(Memory(user_id=user.id, title=f"Ký ức {i}", content="", memory_date=date(2025, 1, 1),
                              place_name="Hà Nội", latitude=21, longitude=105, visibility="private", status="active"))
    db_session.commit()

    _fake_profile(monkeypatch, GoogleProfile("g-2", "Tên Google", "AN@gmail.com", True))
    res = _callback(client)

    assert db_session.query(User).count() == 1  # không tạo tài khoản thứ hai
    mine = client.get("/api/memories/mine", headers={"Authorization": f"Bearer {_token(res)}"})
    assert mine.json()["data"]["total"] == 3
    assert db_session.query(OAuthAccount).filter_by(user_id=user.id, provider="google").count() == 1

    # Lần sau đăng nhập lại vẫn vào đúng tài khoản đó
    assert _callback(client).headers["location"].startswith("/accounts/oauth-callback.html")


def test_email_chua_xac_thuc_khong_tu_lien_ket(client, db_session, monkeypatch):
    db_session.add(User(email="an@gmail.com", password_hash=None, display_name="An", role="user", status="active", token_version=0))
    db_session.commit()
    _fake_profile(monkeypatch, GoogleProfile("g-x", "Kẻ giả mạo", "an@gmail.com", False))
    res = _callback(client)
    assert "chưa được xác thực" in _error(res)
    assert db_session.query(OAuthAccount).count() == 0


@pytest.mark.parametrize("params", [{"error": "access_denied"}, {"code": ""}, {"state": "sai"}])
def test_ac3_tu_choi_hoac_state_sai_ve_trang_dang_nhap(client, db_session, params):
    res = _callback(client, **params)
    assert res.status_code == 302
    assert res.headers["location"].startswith("/accounts/login.html")
    assert _error(res) == "Đăng nhập Google chưa hoàn tất"
    assert db_session.query(User).count() == 0


def test_loi_khi_doi_ma_ve_trang_dang_nhap(client, monkeypatch):
    _fake_profile(monkeypatch, error=GoogleOAuthError(401, "x"))
    assert _error(_callback(client)) == "Đăng nhập Google chưa hoàn tất"


def test_ac4_tai_khoan_bi_khoa(client, db_session, monkeypatch):
    db_session.add(User(email="an@gmail.com", password_hash=None, display_name="An", role="user", status="locked", token_version=0))
    db_session.commit()
    _fake_profile(monkeypatch, GoogleProfile("g-3", "An", "an@gmail.com", True))
    res = _callback(client)
    assert _error(res) == "Tài khoản của bạn đã bị khóa"
    assert db_session.query(OAuthAccount).count() == 0


def test_chua_cau_hinh_thi_nut_google_tat(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_secret", "")
    assert client.get("/api/auth/providers").json()["data"]["google"] is False
    res = client.get("/api/auth/google/login", follow_redirects=False)
    assert _error(res) == "Đăng nhập Google chưa hoàn tất"
