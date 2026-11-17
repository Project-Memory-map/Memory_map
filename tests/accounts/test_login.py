from datetime import timedelta

from sqlalchemy import select

from app.modules.accounts import login_router
from app.modules.accounts.models import User

EMAIL = "an@example.com"
PASSWORD = "Matkhau123"

WRONG = "Email hoặc mật khẩu không đúng"
LOCKED = (
    "Bạn đã nhập sai quá nhiều lần, "
    "vui lòng thử lại sau 15 phút"
)


def register(client):
    response = client.post(
        "/api/auth/register",
        json={
            "display_name": "An",
            "email": EMAIL,
            "password": PASSWORD,
        },
    )

    assert response.status_code == 201
    return response.json()["data"]


def login(
    client,
    email=EMAIL,
    password=PASSWORD,
):
    return client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )


def user_row(db_session):
    return db_session.scalar(
        select(User).where(User.email == EMAIL)
    )


def test_ac1_dang_nhap_thanh_cong(
    client,
    db_session,
):
    register(client)

    response = login(client)

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["user"]["has_password"] is True
    assert "password_hash" not in data["user"]

    me = client.get(
        "/api/auth/me",
        headers={
            "Authorization": (
                f"Bearer {data['access_token']}"
            ),
        },
    )

    assert me.status_code == 200
    assert me.json()["data"]["display_name"] == "An"
    assert user_row(db_session).last_login_at is not None


def test_ac2_email_khong_phan_biet_hoa(client):
    register(client)

    response = login(
        client,
        email="  AN@Example.com  ",
    )

    assert response.status_code == 200


def test_ac3_sai_mat_khau(
    client,
    db_session,
):
    register(client)

    response = login(
        client,
        password="SaiMatkhau123",
    )

    assert response.status_code == 401
    assert response.json()["message"] == WRONG
    assert user_row(db_session).failed_login_count == 1

    missing = login(
        client,
        email="khongco@example.com",
    )

    assert missing.status_code == 401
    assert missing.json()["message"] == WRONG


def test_ac4_tai_khoan_bi_khoa(
    client,
    db_session,
):
    register(client)

    user_row(db_session).status = "locked"
    db_session.commit()

    response = login(client)

    assert response.status_code == 403
    assert response.json()["message"] == (
        "Tài khoản của bạn đã bị khóa"
    )


def test_ac5_sai_5_lan(
    client,
    db_session,
):
    register(client)

    for _ in range(4):
        response = login(
            client,
            password="Sai123456",
        )
        assert response.status_code == 401

    fifth = login(
        client,
        password="Sai123456",
    )

    assert fifth.status_code == 429
    assert fifth.json()["message"] == LOCKED

    sixth = login(client)

    assert sixth.status_code == 429
    assert sixth.json()["message"] == LOCKED
    assert user_row(db_session).failed_login_count == 5


def test_me_chua_dang_nhap(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_dang_nhap_sau_khi_het_khoa(
    client,
    db_session,
    monkeypatch,
):
    register(client)

    for _ in range(5):
        login(
            client,
            password="Sai123456",
        )

    after = (
        user_row(db_session).login_locked_until
        + timedelta(seconds=1)
    )

    monkeypatch.setattr(
        login_router,
        "now_utc",
        lambda: after,
    )

    assert login(client).status_code == 200

    user = user_row(db_session)

    assert user.failed_login_count == 0
    assert user.login_locked_until is None
    assert user.first_failed_at is None


def test_cua_so_15_phut_bat_dau_lai(
    client,
    db_session,
    monkeypatch,
):
    register(client)

    login(
        client,
        password="Sai123456",
    )

    after = (
        user_row(db_session).first_failed_at
        + timedelta(minutes=16)
    )

    monkeypatch.setattr(
        login_router,
        "now_utc",
        lambda: after,
    )

    response = login(
        client,
        password="Sai123456",
    )

    assert response.status_code == 401
    assert user_row(db_session).failed_login_count == 1


def test_me_token_cu_bi_vo_hieu(
    client,
    db_session,
):
    data = register(client)

    user_row(db_session).token_version += 1
    db_session.commit()

    response = client.get(
        "/api/auth/me",
        headers={
            "Authorization": (
                f"Bearer {data['access_token']}"
            ),
        },
    )

    assert response.status_code == 401


def test_me_tai_khoan_bi_khoa(
    client,
    db_session,
):
    data = register(client)

    user_row(db_session).status = "locked"
    db_session.commit()

    response = client.get(
        "/api/auth/me",
        headers={
            "Authorization": (
                f"Bearer {data['access_token']}"
            ),
        },
    )

    assert response.status_code == 403