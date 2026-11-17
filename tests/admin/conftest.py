"""Dữ liệu dùng chung cho test module Quản trị (US-ADM-001 → 003)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from app.core.security import create_access_token
from app.modules.accounts.models import User
from app.modules.memories.models import Memory


@dataclass
class AdminContext:
    client: object
    db: object
    admin: User
    owner: User
    other: User
    public_memory: Memory
    private_memory: Memory

    def headers(self, user: User) -> dict:
        self.db.refresh(user)
        return {"Authorization": f"Bearer {create_access_token(user.id, user.token_version)}"}

    @property
    def admin_headers(self) -> dict:
        return self.headers(self.admin)


def _user(email: str, name: str, role: str = "user") -> User:
    return User(email=email, password_hash=None, display_name=name, role=role, status="active", token_version=0)


def _memory(owner: User, title: str, visibility: str) -> Memory:
    return Memory(
        user_id=owner.id,
        title=title,
        content="Nội dung",
        memory_date=date(2025, 5, 10),
        place_name="Hồ Tây, Hà Nội",
        latitude=21.0583,
        longitude=105.8232,
        visibility=visibility,
        status="active",
    )


@pytest.fixture
def ctx(client, db_session) -> AdminContext:
    admin = _user("admin@example.com", "Quản Trị", role="admin")
    owner = _user("owner@example.com", "Chủ Ký Ức")
    other = _user("other@example.com", "Người Khác")
    db_session.add_all([admin, owner, other])
    db_session.flush()
    public_memory = _memory(owner, "Hoàng hôn Hồ Tây", "public")
    private_memory = _memory(owner, "Nhật ký riêng", "private")
    db_session.add_all([public_memory, private_memory])
    db_session.commit()
    return AdminContext(client, db_session, admin, owner, other, public_memory, private_memory)
