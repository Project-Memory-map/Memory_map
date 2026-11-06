"""US-ACC-001 / FR-1.1 — Đăng ký tài khoản bằng email (5 AC)."""
from sqlalchemy import func, select

from app.core.security import decode_access_token, verify_password
from app.modules.accounts.models import User

URL = "/api/auth/register"


def register(client, email="an@example.com", password="Matkhau123", display_name="An"):
    return client.post(URL, json={"display_name": display_name, "email": email, "password": password})


def count_users(db) -> int:
    return db.execute(select(func.count()).select_from(User)).scalar_one()


def test_ac1_dang_ky_thanh_cong(client, db_session):
    response = register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "Đăng ký thành công"

    user = db_session.execute(select(User).where(User.email == "an@example.com")).scalar_one()
    assert user.role == "user"
    assert user.display_name == "An"
    assert user.password_hash != "Matkhau123" and verify_password("Matkhau123", user.password_hash)

    # Được đăng nhập ngay: token hợp lệ, dùng gọi /me được.
    token = body["data"]["access_token"]
    assert decode_access_token(token)["sub"] == str(user.id)
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "an@example.com"


def test_ac2_mat_khau_dung_8_ky_tu(client, db_session):
    response = register(client, password="Abcdef12")

    assert response.status_code == 201
    assert count_users(db_session) == 1


def test_ac3_mat_khau_qua_ngan(client, db_session):
    response = register(client, password="Abc12")

    assert response.status_code == 422
    assert response.json()["message"] == "Mật khẩu phải có ít nhất 8 ký tự gồm chữ và số"
    assert count_users(db_session) == 0


def test_ac3_mat_khau_thieu_chu_hoac_so(client, db_session):
    for password in ("12345678", "abcdefgh"):
        response = register(client, password=password)
        assert response.status_code == 422
        assert response.json()["message"] == "Mật khẩu phải có ít nhất 8 ký tự gồm chữ và số"
    assert count_users(db_session) == 0


def test_ac4_email_da_duoc_dang_ky(client, db_session):
    assert register(client).status_code == 201

    response = register(client, display_name="An 2")

    assert response.status_code == 409
    assert response.json()["message"] == "Email này đã được đăng ký"
    assert count_users(db_session) == 1


def test_ac4_email_trung_khong_phan_biet_hoa_thuong(client, db_session):
    assert register(client).status_code == 201

    response = register(client, email="  AN@Example.com ")

    assert response.status_code == 409
    assert response.json()["message"] == "Email này đã được đăng ký"
    assert count_users(db_session) == 1


def test_ac5_email_sai_dinh_dang(client, db_session):
    response = register(client, email="an@")

    assert response.status_code == 422
    assert response.json()["message"] == "Email không hợp lệ"
    assert count_users(db_session) == 0
