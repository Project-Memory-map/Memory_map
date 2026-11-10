from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import create_access_token
from app.main import create_app
from app.modules.accounts.deps import get_current_user
from app.modules.accounts.models import User

JWT_SECRET = "test-signing-secret-with-enough-entropy"
CACHE_CONTROL = "no-store, no-cache, must-revalidate, max-age=0"


@pytest.fixture
def authenticated_client(tmp_path):
    settings = Settings(
        jwt_secret_key=JWT_SECRET,
        database_path=str(tmp_path / "logout.sqlite3"),
    )
    app = create_app(settings)

    @app.get("/api/test/private")
    def private_data(
        current_user: User = Depends(get_current_user),
    ) -> dict[str, object]:
        return {
            "user_id": current_user.id,
            "email": current_user.email,
        }

    private_route = app.router.routes.pop()
    fallback_index = next(
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/api/{path:path}"
    )
    app.router.routes.insert(fallback_index, private_route)

    with TestClient(app) as client:
        with sqlite3.connect(settings.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO users
                    (facebook_id, email, display_name, role, password_hash,
                     status, token_version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "logout-test-facebook-id",
                    "logout@example.com",
                    "Logout Test",
                    "user",
                    None,
                    "active",
                    4,
                ),
            )
            user_id = int(cursor.lastrowid)

        user = User(
            id=user_id,
            facebook_id="logout-test-facebook-id",
            email="logout@example.com",
            display_name="Logout Test",
            role="user",
            password_hash=None,
            status="active",
            token_version=4,
        )
        token = create_access_token(user, settings)
        yield client, token, user_id


@pytest.mark.parametrize("logout_path", ["/api/accounts/logout", "/api/auth/logout"])
def test_logout_with_valid_token_returns_json_and_clears_cookie(
    authenticated_client,
    logout_path: str,
) -> None:
    client, token, _ = authenticated_client
    client.cookies.set("access_token", token)

    response = client.post(
        logout_path,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Đăng xuất thành công"}
    assert response.headers["cache-control"] == CACHE_CONTROL
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"
    assert any(
        header.startswith("access_token=") and "Max-Age=0" in header
        for header in response.headers.get_list("set-cookie")
    )


def test_missing_token_is_rejected_for_logout_and_private_api(
    authenticated_client,
) -> None:
    client, _, _ = authenticated_client

    logout_response = client.post("/api/accounts/logout")
    private_response = client.get("/api/test/private")

    assert logout_response.status_code == 401
    assert private_response.status_code == 401
    assert private_response.json() == {
        "detail": "Vui lòng đăng nhập để tiếp tục"
    }
    assert "email" not in private_response.json()
    assert logout_response.headers["cache-control"] == CACHE_CONTROL
    assert private_response.headers["cache-control"] == CACHE_CONTROL


def test_old_token_is_rejected_when_token_version_changes(
    authenticated_client,
) -> None:
    client, old_token, user_id = authenticated_client
    repository = client.app.state.user_repository
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "UPDATE users SET token_version = token_version + 1 WHERE id = ?",
            (user_id,),
        )

    response = client.get(
        "/api/test/private",
        headers={"Authorization": f"Bearer {old_token}"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Vui lòng đăng nhập để tiếp tục"}
    assert "email" not in response.json()


def test_profile_page_is_marked_no_store_for_browser_back(
    authenticated_client,
) -> None:
    client, _, _ = authenticated_client

    response = client.get("/accounts/profile.html")

    assert response.status_code == 200
    assert response.headers["cache-control"] == CACHE_CONTROL
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"


@pytest.mark.parametrize("token", ["not-a-jwt", "expired"])
def test_invalid_or_expired_token_is_rejected(
    authenticated_client,
    token: str,
) -> None:
    client, _, user_id = authenticated_client
    if token == "expired":
        token = jwt.encode(
            {
                "user_id": user_id,
                "role": "user",
                "token_version": 4,
                "iat": datetime.now(timezone.utc) - timedelta(hours=2),
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            },
            JWT_SECRET,
            algorithm="HS256",
        )

    response = client.get(
        "/api/test/private",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Vui lòng đăng nhập để tiếp tục"}
