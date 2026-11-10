from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from app.modules.accounts.models import User


class AccountLockedError(Exception):
    pass


class AccountLinkConflictError(Exception):
    pass


class UserRepository:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.database_path,
            timeout=10,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    facebook_id TEXT UNIQUE,
                    email TEXT UNIQUE,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    password_hash TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    token_version INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower
                ON users(lower(email))
                WHERE email IS NOT NULL
                """
            )

    def authenticate_facebook(
        self,
        facebook_id: str,
        display_name: str,
        email: str | None,
    ) -> User:
        normalized_email = email.strip().lower() if email and email.strip() else None
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT * FROM users WHERE facebook_id = ?",
                    (facebook_id,),
                ).fetchone()
                if row is not None:
                    user = self._to_user(row)
                    self._ensure_unlocked(user)
                    connection.commit()
                    return user

                if normalized_email is not None:
                    row = connection.execute(
                        "SELECT * FROM users WHERE lower(email) = ?",
                        (normalized_email,),
                    ).fetchone()
                    if row is not None:
                        user = self._to_user(row)
                        self._ensure_unlocked(user)
                        if user.facebook_id not in (None, facebook_id):
                            raise AccountLinkConflictError(
                                "Email này đã được liên kết với một tài khoản Facebook khác"
                            )
                        connection.execute(
                            "UPDATE users SET facebook_id = ? WHERE id = ?",
                            (facebook_id, user.id),
                        )
                        connection.commit()
                        return User(
                            id=user.id,
                            facebook_id=facebook_id,
                            email=user.email,
                            display_name=user.display_name,
                            role=user.role,
                            password_hash=user.password_hash,
                            status=user.status,
                            token_version=user.token_version,
                        )

                cursor = connection.execute(
                    """
                    INSERT INTO users
                        (facebook_id, email, display_name, role, password_hash,
                         status, token_version)
                    VALUES (?, ?, ?, 'user', NULL, 'active', 0)
                    """,
                    (facebook_id, normalized_email, display_name),
                )
                row = connection.execute(
                    "SELECT * FROM users WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
                if row is None:
                    raise RuntimeError("Không thể đọc lại tài khoản vừa tạo")
                user = self._to_user(row)
                connection.commit()
                return user
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _ensure_unlocked(user: User) -> None:
        if user.status == "locked":
            raise AccountLockedError

    @staticmethod
    def _to_user(row: sqlite3.Row) -> User:
        return User(
            id=int(row["id"]),
            facebook_id=row["facebook_id"],
            email=row["email"],
            display_name=str(row["display_name"]),
            role=str(row["role"]),
            password_hash=row["password_hash"],
            status=str(row["status"]),
            token_version=int(row["token_version"]),
        )