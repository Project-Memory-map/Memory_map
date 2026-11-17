from datetime import date

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.modules.accounts.models import User
from app.modules.memories.models import Memory, Trip, TripMemory


@pytest.fixture
def context(db_session):
    owner = User(
        email="owner007@example.com",
        display_name="Owner",
        status="active",
        role="user",
        token_version=0,
    )
    other = User(
        email="other007@example.com",
        display_name="Other",
        status="active",
        role="user",
        token_version=0,
    )
    db_session.add_all([owner, other])
    db_session.flush()

    memories = [
        Memory(
            user_id=owner.id,
            title=f"Memory {i}",
            content="Test",
            place_name="Hà Nội",
            latitude=21,
            longitude=105,
            memory_date=date(2025, 1, i + 1),
            visibility="public",
            status="active",
        )
        for i in range(3)
    ]
    db_session.add_all(memories)
    db_session.commit()

    def headers(user):
        token = create_access_token(user.id, user.token_version)
        return {"Authorization": f"Bearer {token}"}

    return owner, memories, headers(owner), headers(other)


def test_owner_soft_delete_and_detail_404(client, db_session, context):
    _, memories, headers, _ = context
    mid = memories[0].id

    response = client.delete(f"/api/memories/{mid}", headers=headers)

    assert response.status_code == 200
    assert response.json()["message"] == "Đã xóa ký ức"

    db_session.expire_all()
    assert db_session.get(Memory, mid).deleted_at is not None
    assert client.get(
        f"/api/memories/{mid}",
        headers=headers,
    ).status_code == 404


def test_delete_preserves_trip_and_other_memories(client, db_session, context):
    owner, memories, headers, _ = context

    trip = Trip(user_id=owner.id, name="Trip")
    db_session.add(trip)
    db_session.flush()

    trip_id = trip.id
    ids = [m.id for m in memories]

    db_session.add_all([
        TripMemory(trip_id=trip_id, memory_id=mid)
        for mid in ids
    ])
    db_session.commit()

    assert client.delete(
        f"/api/memories/{ids[0]}",
        headers=headers,
    ).status_code == 200

    response = client.get(f"/api/trips/{trip_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["memory_count"] == 2

    remaining = db_session.scalars(
        select(TripMemory.memory_id)
        .where(TripMemory.trip_id == trip_id)
    ).all()

    assert set(remaining) == set(ids[1:])
    assert db_session.get(Trip, trip_id) is not None
    assert all(
        db_session.get(Memory, mid).deleted_at is None
        for mid in ids[1:]
    )


def test_other_user_cannot_delete(client, db_session, context):
    _, memories, _, other_headers = context
    mid = memories[0].id

    response = client.delete(
        f"/api/memories/{mid}",
        headers=other_headers,
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Bạn không có quyền xóa ký ức này"

    db_session.expire_all()
    assert db_session.get(Memory, mid).deleted_at is None
    assert client.get(f"/api/memories/{mid}").status_code == 200


def test_second_delete_returns_404(client, context):
    _, memories, headers, _ = context
    url = f"/api/memories/{memories[0].id}"

    assert client.delete(url, headers=headers).status_code == 200
    assert client.delete(url, headers=headers).status_code == 404


def test_deleted_memory_disappears_from_public_pins(client, context):
    _, memories, headers, _ = context
    mid = memories[0].id

    before = client.get("/api/explore/pins").json()["data"]
    assert mid in {p["id"] for p in before}

    assert client.delete(
        f"/api/memories/{mid}",
        headers=headers,
    ).status_code == 200

    after = client.get("/api/explore/pins").json()["data"]
    assert mid not in {p["id"] for p in after}


def test_anonymous_cannot_delete(client, db_session, context):
    _, memories, _, _ = context
    mid = memories[0].id

    assert client.delete(f"/api/memories/{mid}").status_code == 401
    assert db_session.get(Memory, mid).deleted_at is None