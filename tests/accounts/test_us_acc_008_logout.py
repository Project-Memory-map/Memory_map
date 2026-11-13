"""US-ACC-008 – Đăng xuất khỏi hệ thống (T05B576)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token
from app.modules.accounts.models import User


def _create_user_and_token(
    db_session,
    *,
    email: str = "logout@example.com",
    status: str = "active",
    token_version: int = 2,
) -> tuple[User, str]:
    user = User(
        email=email,
        display_name="Logout User",
        password_hash=None,
        role="user",
        status=status,
        token_version=token_version,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(user.id, user.token_version)
    return user, token


def test_ac1_dang_xuat_voi_token_hop_le_tra_ve_200(client, db_session) -> None:
    user, token = _create_user_and_token(db_session)

    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["statusCode"] == 200
    assert body["message"] == "Đăng xuất thành công"
    assert body["data"] is None

    db_session.refresh(user)
    assert user.token_version == 2


def test_ac2_goi_logout_khi_khong_co_token_tra_ve_401(client) -> None:
    response = client.post("/api/auth/logout")
    body = response.json()

    assert response.status_code == 401
    assert body["statusCode"] == 401


@pytest.mark.parametrize("token_kind", ["invalid", "expired", "stale_version"])
def test_ac2_goi_logout_voi_token_khong_hop_le_hoac_het_han_tra_ve_401(
    client,
    db_session,
    token_kind: str,
) -> None:
    user, _ = _create_user_and_token(db_session, token_version=4)

    if token_kind == "invalid":
        token = "not-a-valid-jwt"
    elif token_kind == "expired":
        token = jwt.encode(
            {
                "sub": str(user.id),
                "tv": user.token_version,
                "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
            },
            settings.jwt_secret,
            algorithm=ALGORITHM,
        )
    else:
        token = create_access_token(user.id, user.token_version - 1)

    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = response.json()

    assert response.status_code == 401
    assert body["statusCode"] == 401


def test_ac2_tai_khoan_bi_khoa_tra_ve_403(client, db_session) -> None:
    _, token = _create_user_and_token(
        db_session,
        email="locked_logout@example.com",
        status="locked",
    )

    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = response.json()

    assert response.status_code == 403
    assert body["statusCode"] == 403
    assert body["message"] == "Tài khoản của bạn đã bị khóa"


def test_ac3_logout_response_co_header_chong_cache(client, db_session) -> None:
    _, token = _create_user_and_token(db_session, email="cache@example.com")

    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"

