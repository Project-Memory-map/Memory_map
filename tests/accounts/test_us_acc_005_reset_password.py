"""US-ACC-005 – Quên mật khẩu và đặt lại mật khẩu."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from app.core.config import settings
from app.core.passwords import hash_password, verify_password
from app.modules.accounts import password_reset_router
from app.modules.accounts.models import PasswordResetToken, User

SENT = "Nếu email tồn tại, chúng tôi đã gửi hướng dẫn đặt lại mật khẩu"


@pytest.fixture
def user(db_session) -> User:
    account = User(email="an@example.com", password_hash=hash_password("Matkhau123"), display_name="An",
                   role="user", status="active", token_version=0)
    db_session.add(account)
    db_session.commit()
    return account


@pytest.fixture(autouse=True)
def _dev_khong_smtp(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "dev")
    monkeypatch.setattr(settings, "smtp_host", "")


def _token_from(response) -> str:
    return parse_qs(urlsplit(response.json()["data"]["dev_reset_url"]).query)["token"][0]


def _login(client, password):
    return client.post("/api/auth/login", json={"email": "an@example.com", "password": password})


def test_ac1_email_da_dang_ky_tao_link_30_phut(client, db_session, user):
    res = client.post("/api/auth/forgot-password", json={"email": "AN@example.com"})
    assert res.status_code == 200 and res.json()["message"] == SENT

    record = db_session.query(PasswordResetToken).one()
    token = _token_from(res)
    assert record.token_hash == password_reset_router.hash_token(token) and token not in record.token_hash
    minutes = (record.expires_at - record.created_at).total_seconds() / 60
    assert minutes == 30


def test_ac1_co_smtp_thi_gui_email_khong_tra_link(client, db_session, user, monkeypatch):
    sent = []
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(password_reset_router, "send_reset_email", lambda to, token: sent.append((to, token)))
    res = client.post("/api/auth/forgot-password", json={"email": "an@example.com"})
    assert res.json()["data"] is None
    assert len(sent) == 1 and sent[0][0] == "an@example.com"


def test_ac2_email_chua_dang_ky_cung_thong_bao_va_khong_gui(client, db_session, user, monkeypatch):
    sent = []
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(password_reset_router, "send_reset_email", lambda to, token: sent.append(to))
    res = client.post("/api/auth/forgot-password", json={"email": "khong.co@example.com"})
    assert res.status_code == 200 and res.json()["message"] == SENT and res.json()["data"] is None
    assert sent == [] and db_session.query(PasswordResetToken).count() == 0


def test_ac3_dat_lai_thanh_cong_mk_cu_het_hieu_luc_link_khong_dung_lai(client, user):
    token = _token_from(client.post("/api/auth/forgot-password", json={"email": "an@example.com"}))
    old_jwt = _login(client, "Matkhau123").json()["data"]["access_token"]

    assert client.post("/api/auth/validate-reset-token", json={"token": token}).status_code == 200
    res = client.post("/api/auth/reset-password", json={"token": token, "new_password": "Matkhaumoi9"})
    assert res.status_code == 200

    assert _login(client, "Matkhaumoi9").status_code == 200
    assert _login(client, "Matkhau123").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_jwt}"}).status_code == 401
    again = client.post("/api/auth/reset-password", json={"token": token, "new_password": "Matkhaumoi10"})
    assert again.status_code == 400 and again.json()["message"] == "Liên kết không hợp lệ hoặc đã được sử dụng"


def test_ac4_link_het_han(client, db_session, user):
    token = _token_from(client.post("/api/auth/forgot-password", json={"email": "an@example.com"}))
    record = db_session.query(PasswordResetToken).one()
    record.created_at = record.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    db_session.commit()

    for path, body in [("/api/auth/validate-reset-token", {"token": token}),
                       ("/api/auth/reset-password", {"token": token, "new_password": "Matkhaumoi9"})]:
        res = client.post(path, json=body)
        assert res.status_code == 400 and res.json()["message"] == "Liên kết đã hết hạn, vui lòng yêu cầu lại"
    db_session.expire_all()
    assert verify_password("Matkhau123", db_session.get(User, user.id).password_hash)


def test_mat_khau_moi_yeu_bi_tu_choi(client, user):
    token = _token_from(client.post("/api/auth/forgot-password", json={"email": "an@example.com"}))
    res = client.post("/api/auth/reset-password", json={"token": token, "new_password": "abc"})
    assert res.status_code == 422 and res.json()["message"] == "Mật khẩu phải có ít nhất 8 ký tự gồm chữ và số"


def test_tai_khoan_bi_khoa_khong_duoc_cap_link(client, db_session, user):
    user.status = "locked"
    db_session.commit()
    res = client.post("/api/auth/forgot-password", json={"email": "an@example.com"})
    assert res.json()["message"] == SENT and res.json()["data"] is None


def test_gioi_han_1_lan_moi_60_giay(client, db_session, user):
    client.post("/api/auth/forgot-password", json={"email": "an@example.com"})
    second = client.post("/api/auth/forgot-password", json={"email": "an@example.com"})
    assert second.json()["message"] == SENT
    assert db_session.query(PasswordResetToken).count() == 1


def test_moi_truong_that_khong_bao_gio_tra_link(client, user, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    res = client.post("/api/auth/forgot-password", json={"email": "an@example.com"})
    assert res.json()["data"] is None


def test_token_sai(client):
    res = client.post("/api/auth/validate-reset-token", json={"token": "khong-ton-tai"})
    assert res.status_code == 400 and res.json()["message"] == "Liên kết không hợp lệ hoặc đã được sử dụng"
