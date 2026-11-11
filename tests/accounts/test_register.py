"""US-ACC-001 – Đăng ký tài khoản bằng email (FR-1.1), mỗi test ứng với một AC trên Trello."""
from sqlalchemy import func, select

from app.core.passwords import verify_password
from app.core.security import decode_access_token
from app.modules.accounts.models import User

URL = "/api/auth/register"


def register(client, email="an@example.com", password="Matkhau123", display_name="An"):
    return client.post(URL, json={"display_name": display_name, "email": email, "password": password})


def count_users(db):
    return db.scalar(select(func.count()).select_from(User))


def test_ac1_dang_ky_thanh_cong(client, db_session):
    response = register(client)
    body = response.json()

    assert response.status_code == 201
    assert body["message"] == "Đăng ký thành công"
    user = db_session.scalar(select(User).where(User.email == "an@example.com"))
    assert user.role == "user" and user.status == "active" and user.display_name == "An"
    assert user.password_hash != "Matkhau123" and verify_password("Matkhau123", user.password_hash)
    payload = decode_access_token(body["data"]["access_token"])
    assert payload["sub"] == str(user.id) and payload["tv"] == user.token_version
    assert body["data"]["user"]["email"] == "an@example.com"
    assert "password_hash" not in body["data"]["user"]


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
        assert response.json()["message"] == "Mật khẩu phải có ít nhất 8 ký tự gồm chữ và số"
    assert count_users(db_session) == 0


def test_ac4_email_da_dang_ky(client, db_session):
    register(client)
    response = register(client, display_name="An 2")
    assert response.status_code == 409
    assert response.json()["message"] == "Email này đã được đăng ký"
    assert count_users(db_session) == 1


def test_ac4_email_trung_khong_phan_biet_hoa_thuong(client, db_session):
    register(client)
    response = register(client, email="  AN@Example.com ")
    assert response.json()["message"] == "Email này đã được đăng ký"
    assert count_users(db_session) == 1


def test_ac5_email_sai_dinh_dang(client, db_session):
    response = register(client, email="an@")
    assert response.status_code == 422
    assert response.json()["message"] == "Email không hợp lệ"
    assert count_users(db_session) == 0


def test_ten_hien_thi_trong(client, db_session):
    response = register(client, display_name="   ")
    assert response.status_code == 422
    assert count_users(db_session) == 0


def test_mat_khau_qua_72_byte(client, db_session):
    response = register(client, password="a1" * 40)
    assert response.status_code == 422
    assert count_users(db_session) == 0
