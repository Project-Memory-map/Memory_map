"""US-MEM-010 – Gắn hashtag cho ký ức (FR-2.9, BR-06)."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.modules.accounts.models import User
from app.modules.memories.models import Hashtag, Memory, MemoryHashtag


def _create_memory(db_session, user_id: int, title: str = "Ký ức Đà Lạt") -> Memory:
    memory = Memory(
        user_id=user_id,
        title=title,
        content="Hành trình khám phá thành phố ngàn hoa",
        memory_date=date(2025, 10, 10),
        place_name="Đà Lạt, Lâm Đồng",
        latitude=11.940419,
        longitude=108.458313,
        visibility="public",
        status="active",
    )
    db_session.add(memory)
    db_session.flush()
    return memory


@pytest.fixture
def hashtag_context(client: TestClient, db_session):
    owner = User(
        email="hashtag-owner@example.com",
        password_hash=None,
        display_name="Chủ Ký Ức Hashtag",
        role="user",
        status="active",
        token_version=0,
    )
    other = User(
        email="hashtag-other@example.com",
        password_hash=None,
        display_name="Người Khác",
        role="user",
        status="active",
        token_version=0,
    )
    db_session.add_all([owner, other])
    db_session.flush()

    memory = _create_memory(db_session, owner.id)
    db_session.commit()

    owner_token = create_access_token(owner.id, owner.token_version)
    other_token = create_access_token(other.id, other.token_version)
    return client, db_session, owner, other, memory.id, owner_token, other_token


def test_ac1_attach_two_hashtags_and_show_in_detail(hashtag_context):
    client, db_session, _, _, memory_id, owner_token, _ = hashtag_context
    headers = {"Authorization": f"Bearer {owner_token}"}

    # Gắn 2 hashtag "#dalat" và "#phuot"
    res = client.post(
        f"/api/memories/{memory_id}/hashtags",
        headers=headers,
        json={"hashtags": ["#dalat", "#phuot"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["statusCode"] == 200
    assert set(body["data"]["hashtags"]) == {"dalat", "phuot"}

    # Xem chi tiết ký ức (US-MEM-005): hiển thị đủ cả 2 hashtag đã chuẩn hóa
    detail_res = client.get(f"/api/memories/{memory_id}", headers=headers)
    assert detail_res.status_code == 200
    detail_tags = detail_res.json()["data"]["hashtags"]
    assert "dalat" in detail_tags
    assert "phuot" in detail_tags
    assert len(detail_tags) == 2

    # Kiểm tra trong DB lưu chuẩn hóa không có dấu '#'
    rows = db_session.scalars(
        select(Hashtag.name)
        .join(MemoryHashtag, MemoryHashtag.hashtag_id == Hashtag.id)
        .where(MemoryHashtag.memory_id == memory_id)
    ).all()
    assert set(rows) == {"dalat", "phuot"}


def test_ac2_hashtag_case_insensitive_reuses_existing_tag(hashtag_context):
    client, db_session, owner, _, memory_id, owner_token, _ = hashtag_context
    headers = {"Authorization": f"Bearer {owner_token}"}

    memory_2 = _create_memory(db_session, owner.id, "Ký ức Đà Lạt lần 2")
    db_session.commit()

    # Ký ức 1 gắn "#dalat"
    res1 = client.post(
        f"/api/memories/{memory_id}/hashtags",
        headers=headers,
        json={"hashtags": ["#dalat"]},
    )
    assert res1.status_code == 200

    # Ký ức 2 gắn "#DaLat" và truyền trùng "#DALAT" trong cùng 1 lần lưu
    res2 = client.post(
        f"/api/memories/{memory_2.id}/hashtags",
        headers=headers,
        json={"hashtags": ["#DaLat", "DALAT"]},
    )
    assert res2.status_code == 200
    assert res2.json()["data"]["hashtags"] == ["dalat"]

    # Trong bảng hashtags chỉ có duy nhất 1 bản ghi "dalat"
    all_tags = db_session.scalars(select(Hashtag)).all()
    assert len(all_tags) == 1
    assert all_tags[0].name == "dalat"

    # Cả 2 ký ức đều trỏ tới cùng hashtag_id đó
    links = db_session.scalars(
        select(MemoryHashtag).where(MemoryHashtag.hashtag_id == all_tags[0].id)
    ).all()
    assert len(links) == 2


@pytest.mark.parametrize(
    "invalid_tag",
    [
        "#đà lạt!",
        "#dalat!",
        "#da-lat",
        "#",
        "#" + "a" * 31,
    ],
)
def test_ac3_invalid_hashtag_characters_and_max_length(hashtag_context, invalid_tag):
    client, db_session, _, _, memory_id, owner_token, _ = hashtag_context
    headers = {"Authorization": f"Bearer {owner_token}"}

    res = client.post(
        f"/api/memories/{memory_id}/hashtags",
        headers=headers,
        json={"hashtags": [invalid_tag]},
    )
    body = res.json()
    assert res.status_code in (400, 422)
    assert body["message"] == "Hashtag chỉ gồm chữ, số, dấu gạch dưới (tối đa 30 ký tự)"

    links = db_session.scalars(
        select(MemoryHashtag).where(MemoryHashtag.memory_id == memory_id)
    ).all()
    assert links == []


def test_ac4_exceed_max_10_hashtags_per_memory(hashtag_context):
    client, db_session, _, _, memory_id, owner_token, _ = hashtag_context
    headers = {"Authorization": f"Bearer {owner_token}"}

    # Gửi 11 hashtag ngay trong 1 lần -> bị từ chối
    eleven_tags = [f"#tag_{i}" for i in range(1, 12)]
    res_batch = client.post(
        f"/api/memories/{memory_id}/hashtags",
        headers=headers,
        json={"hashtags": eleven_tags},
    )
    assert res_batch.status_code in (400, 422)
    assert res_batch.json()["message"] == "Mỗi ký ức tối đa 10 hashtag"

    # Gắn 10 hashtag hợp lệ trước
    ten_tags = [f"#tag_{i}" for i in range(1, 11)]
    res_ten = client.post(
        f"/api/memories/{memory_id}/hashtags",
        headers=headers,
        json={"hashtags": ten_tags},
    )
    assert res_ten.status_code == 200
    assert len(res_ten.json()["data"]["hashtags"]) == 10

    # Thêm hashtag thứ 11 -> bị từ chối với đúng câu thông báo
    res_eleventh = client.post(
        f"/api/memories/{memory_id}/hashtags",
        headers=headers,
        json={"hashtags": ["#tag_11"]},
    )
    assert res_eleventh.status_code in (400, 422)
    assert res_eleventh.json()["message"] == "Mỗi ký ức tối đa 10 hashtag"

    links = db_session.scalars(
        select(MemoryHashtag).where(MemoryHashtag.memory_id == memory_id)
    ).all()
    assert len(links) == 10


def test_non_owner_cannot_modify_hashtags_and_suggest_works(hashtag_context):
    client, _, _, _, memory_id, owner_token, other_token = hashtag_context

    # Người khác cố gắn hashtag vào ký ức của owner -> 403 Forbidden
    forbidden = client.post(
        f"/api/memories/{memory_id}/hashtags",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"hashtags": ["#dalat"]},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"] == "FORBIDDEN"

    # Gợi ý hashtag (POST /api/memories/suggest-hashtags trong Bảng API)
    suggest = client.post(
        "/api/memories/suggest-hashtags",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "title": "Săn mây Cầu Đất Đà Lạt",
            "content": "Buổi sáng uống cà phê ngắm biển mây tuyệt đẹp",
            "place_name": "Đà Lạt, Lâm Đồng",
            "latitude": 11.940419,
            "longitude": 108.458313,
        },
    )
    assert suggest.status_code == 200
    suggest_data = suggest.json()["data"]
    assert isinstance(suggest_data["hashtags"], list)
    assert len(suggest_data["hashtags"]) > 0
