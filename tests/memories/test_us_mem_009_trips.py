"""US-MEM-009 – Tạo chuyến đi và thêm ký ức vào chuyến đi (FR-2.7)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.modules.accounts.models import User
from app.modules.memories.models import Media, Memory, Trip, TripMemory


def _create_memory(
    db_session,
    user_id: int,
    title: str,
    memory_date: date,
    created_at: datetime | None = None,
) -> Memory:
    now = created_at or datetime.now(timezone.utc).replace(tzinfo=None)
    memory = Memory(
        user_id=user_id,
        title=title,
        content=f"Nội dung {title}",
        memory_date=memory_date,
        place_name="Đà Lạt, Lâm Đồng",
        latitude=11.940419,
        longitude=108.458313,
        visibility="private",
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add(memory)
    db_session.flush()
    return memory


@pytest.fixture
def trips_context(client: TestClient, db_session):
    owner = User(
        email="trip-owner@example.com",
        password_hash=None,
        display_name="Chủ Chuyến Đi",
        role="user",
        status="active",
        token_version=0,
    )
    other = User(
        email="trip-other@example.com",
        password_hash=None,
        display_name="Người Khác",
        role="user",
        status="active",
        token_version=0,
    )
    db_session.add_all([owner, other])
    db_session.commit()

    owner_token = create_access_token(owner.id, owner.token_version)
    other_token = create_access_token(other.id, other.token_version)
    return client, db_session, owner, other, owner_token, other_token


def test_ac1_create_trip_and_add_memories_sorted_by_date(trips_context):
    client, db_session, owner, _, owner_token, _ = trips_context
    headers = {"Authorization": f"Bearer {owner_token}"}

    # Tạo 3 ký ức theo thứ tự lộn xộn: 12/10, 10/10, 11/10/2025
    mem_12 = _create_memory(db_session, owner.id, "Ngày 3 - Chợ đêm", date(2025, 10, 12))
    mem_10 = _create_memory(db_session, owner.id, "Ngày 1 - Hồ Xuân Hương", date(2025, 10, 10))
    mem_11 = _create_memory(db_session, owner.id, "Ngày 2 - Đồi chè Cầu Đất", date(2025, 10, 11))
    db_session.commit()

    # Tạo chuyến đi "Đà Lạt tháng 10"
    create_res = client.post(
        "/api/trips",
        headers=headers,
        json={"name": "Đà Lạt tháng 10", "description": "Hành trình mùa thu"},
    )
    assert create_res.status_code in (200, 201)
    trip_id = create_res.json()["data"]["id"]
    assert create_res.json()["data"]["name"] == "Đà Lạt tháng 10"

    # Thêm cả 3 ký ức vào chuyến đi
    add_res = client.post(
        f"/api/trips/{trip_id}/memories",
        headers=headers,
        json={"memory_ids": [mem_12.id, mem_10.id, mem_11.id]},
    )
    assert add_res.status_code == 200

    # Thêm lại ký ức đã có sẵn trong chuyến đi -> xử lý an toàn (idempotent, không lỗi 500)
    dup_res = client.post(
        f"/api/trips/{trip_id}/memories",
        headers=headers,
        json={"memory_ids": [mem_10.id]},
    )
    assert dup_res.status_code == 200

    # Khi xem chi tiết chuyến đi: hiển thị đủ 3 ký ức theo thứ tự ngày tăng dần
    detail_res = client.get(f"/api/trips/{trip_id}", headers=headers)
    assert detail_res.status_code == 200
    trip_data = detail_res.json()["data"]
    assert trip_data["memory_count"] == 3
    assert trip_data["start_date"] == "2025-10-10"
    assert trip_data["end_date"] == "2025-10-12"

    memories = trip_data["memories"]
    assert [m["id"] for m in memories] == [mem_10.id, mem_11.id, mem_12.id]
    assert [m["memory_date"] for m in memories] == [
        "2025-10-10",
        "2025-10-11",
        "2025-10-12",
    ]


def test_ac2_same_date_memories_sorted_by_creation_order(trips_context):
    client, db_session, owner, _, owner_token, _ = trips_context
    headers = {"Authorization": f"Bearer {owner_token}"}

    base_time = datetime(2025, 10, 11, 8, 0, 0)
    first_mem = _create_memory(
        db_session,
        owner.id,
        "Buổi sáng uống cà phê Tùng",
        date(2025, 10, 11),
        created_at=base_time,
    )
    second_mem = _create_memory(
        db_session,
        owner.id,
        "Buổi chiều ngắm hoàng hôn",
        date(2025, 10, 11),
        created_at=base_time + timedelta(hours=5),
    )
    db_session.commit()

    create_res = client.post(
        "/api/trips",
        headers=headers,
        json={"name": "Một ngày ở Đà Lạt"},
    )
    trip_id = create_res.json()["data"]["id"]

    # Gửi theo thứ tự ngược [second_mem.id, first_mem.id]
    add_res = client.post(
        f"/api/trips/{trip_id}/memories",
        headers=headers,
        json={"memory_ids": [second_mem.id, first_mem.id]},
    )
    assert add_res.status_code == 200

    # Khi mở xem chuyến đi: ký ức tạo trước hiển thị trước
    detail_res = client.get(f"/api/trips/{trip_id}", headers=headers)
    assert detail_res.status_code == 200
    memories = detail_res.json()["data"]["memories"]
    assert [m["id"] for m in memories] == [first_mem.id, second_mem.id]


def test_ac3_cannot_add_other_user_memory_to_trip(trips_context):
    client, db_session, _, other, owner_token, _ = trips_context
    headers = {"Authorization": f"Bearer {owner_token}"}

    # Ký ức số 123 thuộc về người dùng khác
    other_memory = Memory(
        id=123,
        user_id=other.id,
        title="Ký ức của người khác",
        content="Nội dung riêng",
        memory_date=date(2025, 10, 10),
        place_name="Huế",
        latitude=16.4637,
        longitude=107.5909,
        visibility="public",
        status="active",
    )
    db_session.add(other_memory)
    db_session.commit()

    create_res = client.post(
        "/api/trips",
        headers=headers,
        json={"name": "Chuyến đi của tôi"},
    )
    assert create_res.status_code in (200, 201)
    trip_id = create_res.json()["data"]["id"]

    # Cố thêm ký ức số 123 của người khác vào chuyến đi của mình
    add_res = client.post(
        f"/api/trips/{trip_id}/memories",
        headers=headers,
        json={"memory_ids": [123]},
    )
    body = add_res.json()
    assert add_res.status_code in (400, 403)
    assert body["message"] == "Chỉ thêm được ký ức của bạn"

    # Kiểm tra DB không có bản ghi liên kết nào được tạo
    link = db_session.scalar(
        select(TripMemory).where(TripMemory.trip_id == trip_id, TripMemory.memory_id == 123)
    )
    assert link is None


@pytest.mark.parametrize("invalid_name", ["", "   ", None])
def test_ac4_create_trip_missing_name(trips_context, invalid_name):
    client, db_session, owner, _, owner_token, _ = trips_context
    headers = {"Authorization": f"Bearer {owner_token}"}

    res = client.post(
        "/api/trips",
        headers=headers,
        json={"name": invalid_name, "description": "Mô tả"},
    )
    body = res.json()
    assert res.status_code in (400, 422)
    assert body["message"] == "Vui lòng nhập tên chuyến đi"

    trips_in_db = db_session.scalars(select(Trip).where(Trip.user_id == owner.id)).all()
    assert len(trips_in_db) == 0


def test_ac5_update_remove_memory_and_delete_trip_keeps_memories_intact(trips_context):
    client, db_session, owner, _, owner_token, _ = trips_context
    headers = {"Authorization": f"Bearer {owner_token}"}

    m1 = _create_memory(db_session, owner.id, "Ký ức 1", date(2025, 10, 10))
    m2 = _create_memory(db_session, owner.id, "Ký ức 2", date(2025, 10, 11))
    m3 = _create_memory(db_session, owner.id, "Ký ức 3", date(2025, 10, 12))
    db_session.commit()

    create_res = client.post(
        "/api/trips",
        headers=headers,
        json={"name": "Đà Lạt tháng 10"},
    )
    trip_id = create_res.json()["data"]["id"]

    client.post(
        f"/api/trips/{trip_id}/memories",
        headers=headers,
        json={"memory_ids": [m1.id, m2.id, m3.id]},
    )

    # 1. Đổi tên chuyến đi
    patch_res = client.patch(
        f"/api/trips/{trip_id}",
        headers=headers,
        json={"name": "Đà Lạt mùa dã quỳ", "description": "Cập nhật mô tả"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["name"] == "Đà Lạt mùa dã quỳ"
    assert patch_res.json()["data"]["description"] == "Cập nhật mô tả"

    # 2. Bỏ 1 ký ức (m2) khỏi chuyến đi -> m2 không còn trong chuyến đi nhưng vẫn còn trong bảng memories
    remove_res = client.delete(
        f"/api/trips/{trip_id}/memories/{m2.id}",
        headers=headers,
    )
    assert remove_res.status_code == 200

    detail_after_remove = client.get(f"/api/trips/{trip_id}", headers=headers)
    assert [m["id"] for m in detail_after_remove.json()["data"]["memories"]] == [m1.id, m3.id]

    db_session.expire_all()
    assert db_session.get(Memory, m2.id) is not None

    # 3. Xóa chuyến đi -> chuyến đi bị xóa nhưng cả 3 ký ức vẫn còn nguyên vẹn trong bảng memories
    del_res = client.delete(f"/api/trips/{trip_id}", headers=headers)
    assert del_res.status_code == 200

    assert client.get(f"/api/trips/{trip_id}", headers=headers).status_code == 404
    db_session.expire_all()
    assert db_session.get(Trip, trip_id) is None
    assert db_session.scalars(select(TripMemory).where(TripMemory.trip_id == trip_id)).all() == []
    for mid in (m1.id, m2.id, m3.id):
        mem = db_session.get(Memory, mid)
        assert mem is not None
        assert mem.deleted_at is None


def test_memory_in_multiple_trips_and_soft_deleted_memory_filtered(trips_context):
    client, db_session, owner, _, owner_token, other_token = trips_context
    headers = {"Authorization": f"Bearer {owner_token}"}

    m1 = _create_memory(db_session, owner.id, "Ký ức chung", date(2025, 10, 10))
    m2 = _create_memory(db_session, owner.id, "Ký ức sẽ xóa mềm", date(2025, 10, 11))
    db_session.add(
        Media(
            memory_id=m1.id,
            media_type="image",
            file_path="images/cover.jpg",
            thumb_path=None,
            mime_type="image/jpeg",
            size_bytes=512,
            sort_order=0,
        )
    )
    db_session.commit()

    t1 = client.post("/api/trips", headers=headers, json={"name": "Chuyến đi 1"}).json()["data"]["id"]
    t2 = client.post("/api/trips", headers=headers, json={"name": "Chuyến đi 2"}).json()["data"]["id"]

    # Cùng 1 ký ức m1 được thêm vào cả 2 chuyến đi
    assert client.post(f"/api/trips/{t1}/memories", headers=headers, json={"memory_ids": [m1.id, m2.id]}).status_code == 200
    assert client.post(f"/api/trips/{t2}/memories", headers=headers, json={"memory_ids": [m1.id]}).status_code == 200

    t1_detail = client.get(f"/api/trips/{t1}", headers=headers).json()["data"]
    t2_detail = client.get(f"/api/trips/{t2}", headers=headers).json()["data"]
    assert [m["id"] for m in t1_detail["memories"]] == [m1.id, m2.id]
    assert [m["id"] for m in t2_detail["memories"]] == [m1.id]
    # Kiểm tra URL ảnh đính kèm đã được ký (sign_media_url)
    assert "sig=" in t1_detail["memories"][0]["cover_url"]

    # Người khác không được xem/sửa/xóa chuyến đi của owner
    assert client.get(f"/api/trips/{t1}", headers={"Authorization": f"Bearer {other_token}"}).status_code == 403
    assert client.patch(f"/api/trips/{t1}", headers={"Authorization": f"Bearer {other_token}"}, json={"name": "Hack"}).status_code == 403
    assert client.delete(f"/api/trips/{t1}", headers={"Authorization": f"Bearer {other_token}"}).status_code == 403

    # Xóa mềm m2 -> tự động lọc khỏi chuyến đi (US-MEM-007 AC3)
    m2.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.commit()

    t1_after_soft_delete = client.get(f"/api/trips/{t1}", headers=headers).json()["data"]
    assert t1_after_soft_delete["memory_count"] == 1
    assert [m["id"] for m in t1_after_soft_delete["memories"]] == [m1.id]

    list_trips = client.get("/api/trips", headers=headers).json()["data"]
    trip1_summary = next(item for item in list_trips if item["id"] == t1)
    assert trip1_summary["memory_count"] == 1
