"""US-EXP-002 - Lọc ký ức công khai theo hashtag (T05B584)."""
from datetime import date

from app.modules.accounts.models import User
from app.modules.memories.models import Hashtag, Memory, MemoryHashtag


def seed_explore_data(db_session):
    user = User(
        email="tester@example.com",
        display_name="Người dùng test",
        password_hash="hashed",
        role="user",
        status="active",
    )
    db_session.add(user)
    db_session.flush()

    t_dalat = Hashtag(name="dalat")
    t_bien = Hashtag(name="bien")
    t_rieng = Hashtag(name="riengtu")
    db_session.add_all([t_dalat, t_bien, t_rieng])
    db_session.flush()

    m1 = Memory(
        user_id=user.id,
        title="Săn mây Đà Lạt",
        content="Sáng sớm lạnh",
        place_name="Đà Lạt",
        latitude=11.94,
        longitude=108.45,
        memory_date=date(2026, 6, 1),
        visibility="public",
        status="active",
    )
    m2 = Memory(
        user_id=user.id,
        title="Biển xanh Vũng Tàu",
        content="Gió mát",
        place_name="Vũng Tàu",
        latitude=10.34,
        longitude=107.08,
        memory_date=date(2026, 6, 2),
        visibility="public",
        status="active",
    )
    m3 = Memory(
        user_id=user.id,
        title="Nhật ký bí mật",
        content="Không công khai",
        place_name="Đà Lạt",
        latitude=11.95,
        longitude=108.46,
        memory_date=date(2026, 6, 3),
        visibility="private",
        status="active",
    )
    db_session.add_all([m1, m2, m3])
    db_session.flush()

    db_session.add_all([
        MemoryHashtag(memory_id=m1.id, hashtag_id=t_dalat.id, source="manual"),
        MemoryHashtag(memory_id=m2.id, hashtag_id=t_bien.id, source="manual"),
        MemoryHashtag(memory_id=m3.id, hashtag_id=t_dalat.id, source="manual"),
        MemoryHashtag(memory_id=m3.id, hashtag_id=t_rieng.id, source="manual"),
    ])
    db_session.commit()


def test_ac1_get_popular_hashtags_public_only(client, db_session):
    seed_explore_data(db_session)
    res = client.get("/api/explore/hashtags")
    assert res.status_code == 200
    tags = res.json()["data"]
    names = [t["name"] for t in tags]
    assert "dalat" in names
    assert "bien" in names
    assert "riengtu" not in names


def test_ac2_filter_single_hashtag_excludes_private(client, db_session):
    seed_explore_data(db_session)
    res = client.get("/api/explore/memories", params={"hashtags": "dalat"})
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Săn mây Đà Lạt"


def test_ac3_filter_multiple_hashtags_or_condition(client, db_session):
    seed_explore_data(db_session)
    res = client.get("/api/explore/memories", params={"hashtags": "dalat,bien"})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 2
    titles = {item["title"] for item in data["items"]}
    assert titles == {"Săn mây Đà Lạt", "Biển xanh Vũng Tàu"}


def test_ac4_case_insensitive_and_hash_symbol(client, db_session):
    seed_explore_data(db_session)
    res = client.get("/api/explore/memories", params={"hashtags": "#DaLat"})
    assert res.status_code == 200
    assert len(res.json()["data"]["items"]) == 1