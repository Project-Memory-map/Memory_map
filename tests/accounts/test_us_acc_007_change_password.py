"""US-ACC-007 – Đổi mật khẩu khi đang đăng nhập (T05B575)."""
from __future__ import annotations

from app.core.passwords import hash_password, verify_password
from app.core.security import create_access_token
from app.modules.accounts.models import OAuthAccount, User

URL = "/api/auth/change-password"
OLD = "matkhau123"
NEW = "matkhaumoi456"


def _user(db_session, *, password: str | None = OLD, email: str = "doimk@example.com") -> tuple[User, str]:
    user = User(
        email=email,
        display_name="Doi Mat Khau",
        password_hash=hash_password(password) if password else None,
        role="user",
        status="active",
        token_version=3,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user, create_access_token(user.id, user.token_version)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_doi_mat_khau_thanh_cong_luu_ban_bam_moi_va_tra_token_moi(client, db_session) -> None:
    user, token = _user(db_session)

    response = client.post(URL, json={"current_password": OLD, "new_password": NEW}, headers=_auth(token))
    body = response.json()

    assert response.status_code == 200
    assert body["message"] == "Đổi mật khẩu thành công"
    assert response.headers["Cache-Control"] == "no-store"
    db_session.refresh(user)
    assert verify_password(NEW, user.password_hash)
    assert not verify_password(OLD, user.password_hash)
    assert body["data"]["access_token"]
    assert body["data"]["user"]["has_password"] is True


def test_sau_khi_doi_token_cu_bi_thu_hoi_token_moi_van_dung_duoc(client, db_session) -> None:
    user, old_token = _user(db_session)

    new_token = client.post(
        URL, json={"current_password": OLD, "new_password": NEW}, headers=_auth(old_token)
    ).json()["data"]["access_token"]

    db_session.refresh(user)
    assert user.token_version == 4  # BR-20
    assert client.get("/api/auth/me", headers=_auth(old_token)).status_code == 401
    assert client.get("/api/auth/me", headers=_auth(new_token)).status_code == 200


def test_dang_nhap_bang_mat_khau_moi_duoc_mat_khau_cu_thi_khong(client, db_session) -> None:
    _, token = _user(db_session)
    client.post(URL, json={"current_password": OLD, "new_password": NEW}, headers=_auth(token))

    old_login = client.post("/api/auth/login", json={"email": "doimk@example.com", "password": OLD})
    new_login = client.post("/api/auth/login", json={"email": "doimk@example.com", "password": NEW})

    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_sai_mat_khau_hien_tai_tra_400_va_khong_doi_gi(client, db_session) -> None:
    user, token = _user(db_session)

    response = client.post(URL, json={"current_password": "saimatkhau1", "new_password": NEW}, headers=_auth(token))

    assert response.status_code == 400
    assert response.json()["message"] == "Mật khẩu hiện tại không đúng"
    db_session.refresh(user)
    assert verify_password(OLD, user.password_hash)
    assert user.token_version == 3


def test_thieu_mat_khau_hien_tai_tra_400(client, db_session) -> None:
    _, token = _user(db_session)

    response = client.post(URL, json={"new_password": NEW}, headers=_auth(token))

    assert response.status_code == 400
    assert response.json()["message"] == "Vui lòng nhập mật khẩu hiện tại"


def test_mat_khau_moi_trung_mat_khau_cu_tra_400(client, db_session) -> None:
    _, token = _user(db_session)

    response = client.post(URL, json={"current_password": OLD, "new_password": OLD}, headers=_auth(token))

    assert response.status_code == 400
    assert response.json()["message"] == "Mật khẩu mới phải khác mật khẩu hiện tại"


def test_mat_khau_moi_yeu_tra_422(client, db_session) -> None:
    user, token = _user(db_session)

    for weak in ["ngan1", "chicochukhongso", "1234567890"]:
        response = client.post(URL, json={"current_password": OLD, "new_password": weak}, headers=_auth(token))
        assert response.status_code == 422, weak

    db_session.refresh(user)
    assert verify_password(OLD, user.password_hash)


def test_chua_dang_nhap_tra_401(client) -> None:
    response = client.post(URL, json={"current_password": OLD, "new_password": NEW})

    assert response.status_code == 401


def test_tai_khoan_mang_xa_hoi_tao_mat_khau_khong_can_mat_khau_cu(client, db_session) -> None:
    user, token = _user(db_session, password=None, email="google@example.com")
    db_session.add(OAuthAccount(user_id=user.id, provider="google", provider_user_id="g-1"))
    db_session.commit()
    db_session.expire_all()  # mỗi request thật dùng session mới; ở test phải nạp lại quan hệ

    me = client.get("/api/auth/me", headers=_auth(token)).json()["data"]
    assert me["has_password"] is False
    assert me["providers"] == ["google"]

    response = client.post(URL, json={"new_password": NEW}, headers=_auth(token))

    assert response.status_code == 200
    assert response.json()["message"] == "Tạo mật khẩu thành công"
    db_session.refresh(user)
    assert verify_password(NEW, user.password_hash)
