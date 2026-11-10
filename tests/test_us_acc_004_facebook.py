from __future__ import annotations

import asyncio
import sqlite3
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.modules.accounts.services.facebook_auth import (
    FacebookAuthService,
    FacebookOAuthError,
    FacebookProfile,
)


class FakeFacebookAuth:
    def __init__(
        self,
        profile: FacebookProfile | None = None,
        error: FacebookOAuthError | None = None,
    ) -> None:
        self.profile = profile or FacebookProfile(
            facebook_id="fb-123",
            display_name="Facebook User",
            email="user@example.com",
        )
        self.error = error
        self.received_code: str | None = None
        self.received_access_token: str | None = None

    def authorization_url(self, state: str) -> str:
        return f"https://facebook.test/oauth?state={state}"

    async def profile_from_code(self, code: str) -> FacebookProfile:
        self.received_code = code
        if self.error:
            raise self.error
        return self.profile

    async def profile_from_access_token(self, access_token: str) -> FacebookProfile:
        self.received_access_token = access_token
        if self.error:
            raise self.error
        return self.profile


def make_client(
    tmp_path,
    *,
    profile: FacebookProfile | None = None,
    error: FacebookOAuthError | None = None,
) -> TestClient:
    settings = Settings(
        facebook_app_id="test-app-id",
        facebook_app_secret="test-app-secret",
        jwt_secret_key="test-signing-secret-with-enough-entropy",
        database_path=str(tmp_path / "test.sqlite3"),
    )
    app = create_app(settings, FakeFacebookAuth(profile, error))
    return TestClient(app)


def _post_token(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/accounts/facebook/token",
        json={"access_token": "valid-facebook-token"},
    )
    assert response.status_code == 200
    return response.json()


def test_ac1_first_facebook_login_creates_user_and_standard_jwt(tmp_path) -> None:
    with make_client(tmp_path) as client:
        result = _post_token(client)
        assert (
            client.app.state.facebook_auth.received_access_token
            == "valid-facebook-token"
        )

    assert result["missing_email"] is False
    assert result["user"]["display_name"] == "Facebook User"
    assert result["user"]["role"] == "user"
    payload = jwt.decode(
        result["access_token"],
        "test-signing-secret-with-enough-entropy",
        algorithms=["HS256"],
    )
    assert payload["user_id"] == result["user"]["user_id"]
    assert payload["role"] == "user"
    assert payload["token_version"] == 0


def test_oauth_callback_uses_state_cookie_and_exchanges_code(tmp_path) -> None:
    with make_client(tmp_path) as client:
        start = client.get(
            "/api/accounts/facebook/login",
            follow_redirects=False,
        )
        state = client.cookies.get("facebook_oauth_state")
        callback = client.get(
            "/api/accounts/facebook/callback",
            params={"code": "valid-code", "state": state},
        )

    assert start.status_code == 302
    assert state
    assert callback.status_code == 200
    assert callback.json()["user"]["display_name"] == "Facebook User"


def test_browser_oauth_callback_uses_existing_ui_and_shared_session_endpoint(
    tmp_path,
) -> None:
    with make_client(tmp_path) as client:
        start = client.get("/api/auth/facebook/login", follow_redirects=False)
        state = client.cookies.get("facebook_oauth_state")
        callback = client.get(
            "/api/auth/facebook/callback",
            params={"code": "valid-code", "state": state},
            follow_redirects=False,
        )
        fragment = parse_qs(urlsplit(callback.headers["location"]).fragment)
        session = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {fragment['token'][0]}"},
        )

    assert start.status_code == 302
    assert callback.status_code == 302
    assert urlsplit(callback.headers["location"]).path == "/accounts/oauth-callback.html"
    assert fragment["notice"] == ["oauth"]
    assert session.status_code == 200
    assert session.json()["data"]["display_name"] == "Facebook User"
    assert session.json()["data"]["providers"] == ["facebook"]


def test_browser_facebook_cancel_returns_to_login_with_exact_message(tmp_path) -> None:
    with make_client(tmp_path) as client:
        response = client.get(
            "/api/auth/facebook/callback",
            params={"error": "access_denied"},
            follow_redirects=False,
        )

    destination = urlsplit(response.headers["location"])
    assert response.status_code == 302
    assert destination.path == "/accounts/login.html"
    assert parse_qs(destination.query)["error"] == ["Đăng nhập Facebook chưa hoàn tất"]


def test_browser_missing_email_redirects_to_profile_notice(tmp_path) -> None:
    profile = FacebookProfile(
        facebook_id="fb-no-email",
        display_name="No Email User",
        email=None,
    )
    with make_client(tmp_path, profile=profile) as client:
        start = client.get("/api/auth/facebook/login", follow_redirects=False)
        callback = client.get(
            "/api/auth/facebook/callback",
            params={"code": "valid-code", "state": client.cookies.get("facebook_oauth_state")},
            follow_redirects=False,
        )

    destination = urlsplit(callback.headers["location"])
    fragment = parse_qs(destination.fragment)
    assert start.status_code == 302
    assert destination.path == "/accounts/oauth-callback.html"
    assert fragment["notice"] == ["need_email"]


def test_browser_locked_account_returns_to_login_with_exact_message(tmp_path) -> None:
    profile = FacebookProfile(
        facebook_id="fb-locked",
        display_name="Locked User",
        email="locked@example.com",
    )
    with make_client(tmp_path, profile=profile) as client:
        repository = client.app.state.user_repository
        with sqlite3.connect(repository.database_path) as connection:
            connection.execute(
                """
                INSERT INTO users
                    (facebook_id, email, display_name, role, status, token_version)
                VALUES (?, ?, ?, 'user', 'locked', 0)
                """,
                ("fb-locked", "locked@example.com", "Locked User"),
            )
        client.get("/api/auth/facebook/login", follow_redirects=False)
        response = client.get(
            "/api/auth/facebook/callback",
            params={"code": "valid-code", "state": client.cookies.get("facebook_oauth_state")},
            follow_redirects=False,
        )

    destination = urlsplit(response.headers["location"])
    assert response.status_code == 302
    assert destination.path == "/accounts/login.html"
    assert parse_qs(destination.query)["error"] == ["Tài khoản của bạn đã bị khóa"]


def test_ac2_missing_facebook_email_creates_account_without_password(tmp_path) -> None:
    profile = FacebookProfile(
        facebook_id="fb-no-email",
        display_name="No Email User",
        email=None,
    )
    with make_client(tmp_path, profile=profile) as client:
        result = _post_token(client)
        repository = client.app.state.user_repository
        connection = sqlite3.connect(repository.database_path)
        row = connection.execute(
            "SELECT email, password_hash FROM users WHERE facebook_id = ?",
            ("fb-no-email",),
        ).fetchone()
        connection.close()

    assert result["missing_email"] is True
    assert result["user"]["email"] is None
    assert row == (None, None)


@pytest.mark.parametrize(
    "query",
    [
        {"error": "access_denied"},
        {"state": "expected-state"},
    ],
)
def test_ac3_cancelled_or_missing_code_is_a_safe_client_error(
    tmp_path,
    query: dict[str, str],
) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/api/accounts/facebook/callback", params=query)

    assert response.status_code == 400
    assert response.json()["detail"] == "Đăng nhập Facebook chưa hoàn tất"


def test_existing_email_is_linked_without_replacing_account_data(tmp_path) -> None:
    profile = FacebookProfile(
        facebook_id="fb-linked",
        display_name="New Facebook Name",
        email="EXISTING@example.com",
    )
    with make_client(tmp_path, profile=profile) as client:
        repository = client.app.state.user_repository
        with sqlite3.connect(repository.database_path) as connection:
            connection.execute(
                """
                INSERT INTO users
                    (email, display_name, role, password_hash, status, token_version)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "existing@example.com",
                    "Original Name",
                    "user",
                    "old-hash",
                    "active",
                    3,
                ),
            )

        result = _post_token(client)
        with sqlite3.connect(repository.database_path) as connection:
            row = connection.execute(
                """
                SELECT id, facebook_id, display_name, password_hash, token_version
                FROM users WHERE email = ?
                """,
                ("existing@example.com",),
            ).fetchone()

    assert result["user"]["user_id"] == row[0]
    assert row[1:] == ("fb-linked", "Original Name", "old-hash", 3)


@pytest.mark.parametrize(
    "facebook_id",
    ["fb-locked", None],
)
def test_locked_account_is_rejected_without_issuing_token(
    tmp_path,
    facebook_id: str | None,
) -> None:
    profile = FacebookProfile(
        facebook_id=facebook_id or "fb-new",
        display_name="Locked",
        email="locked@example.com",
    )
    with make_client(tmp_path, profile=profile) as client:
        repository = client.app.state.user_repository
        with sqlite3.connect(repository.database_path) as connection:
            connection.execute(
                """
                INSERT INTO users
                    (facebook_id, email, display_name, role, status, token_version)
                VALUES (?, ?, ?, 'user', 'locked', 0)
                """,
                (facebook_id, "locked@example.com", "Locked"),
            )
        response = client.post(
            "/api/accounts/facebook/token",
            json={"access_token": "valid-facebook-token"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Tài khoản của bạn đã bị khóa"
    assert "access_token" not in response.json()


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (FacebookOAuthError(502, "Facebook không phản hồi kịp thời"), 502),
        (FacebookOAuthError(401, "Facebook access token không hợp lệ"), 401),
    ],
)
def test_facebook_timeout_and_invalid_token_are_explicit_errors(
    tmp_path,
    error: FacebookOAuthError,
    status_code: int,
) -> None:
    with make_client(tmp_path, error=error) as client:
        response = client.post(
            "/api/accounts/facebook/token",
            json={"access_token": "bad-token"},
        )

    assert response.status_code == status_code
    assert "detail" in response.json()


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

    settings = Settings(
        facebook_app_id="test-app-id",
        facebook_app_secret="test-app-secret",
        jwt_secret_key="test-signing-secret-with-enough-entropy",
    )
    handler = {
        "timeout": timeout_handler,
        "invalid_token": invalid_token_handler,
    }[handler_name]
    service = FacebookAuthService(settings, transport=httpx.MockTransport(handler))

    with pytest.raises(FacebookOAuthError) as error:
        asyncio.run(service.profile_from_access_token("invalid-token"))

    assert error.value.status_code == status_code
