"""US-EXP-003 - Lọc ký ức công khai theo khu vực (T05B585)."""
from datetime import date

from app.modules.accounts.models import User
from app.modules.explore.models import Region
from app.modules.memories.models import Memory


def seed_region_data(db_session):
    user = User(
        email="region_tester@example.com",
        display_name="Người dùng test khu vực",
        password_hash="hashed",
        role="user",
        status="active",
    )
    db_session.add(user)
    db_session.flush()

    r_hanoi = Region(name="Hà Nội", slug="ha-noi", level="city")
    r_hcm = Region(name="TP. Hồ Chí Minh", slug="tp-ho-chi-minh", level="city")
    r_danang = Region(name="Đà Nẵng", slug="da-nang", level="city")
    db_session.add_all([r_hanoi, r_hcm, r_danang])
    db_session.flush()

    m1 = Memory(
        user_id=user.id,
        region_id=r_hanoi.id,
        title="Hồ Gươm sáng sớm",
        content="Không khí trong lành",
        place_name="Hoàn Kiếm, Hà Nội",
        latitude=21.0285,
        longitude=105.8542,
        memory_date=date(2026, 7, 1),
        visibility="public",
        status="active",
    )
    m2 = Memory(
        user_id=user.id,
        region_id=r_hcm.id,
        title="Phố đi bộ Nguyễn Huệ",
        content="Nhộn nhịp về đêm",
        place_name="Quận 1, TP.HCM",
        latitude=10.7744,
        longitude=106.7035,
        memory_date=date(2026, 7, 2),
        visibility="public",
        status="active",
    )
    m3 = Memory(
        user_id=user.id,
        region_id=r_hanoi.id,
        title="Ký ức riêng tư Hà Nội",
        content="Không hiển thị công khai",
        place_name="Cầu Giấy, Hà Nội",
        latitude=21.0362,
        longitude=105.7906,
        memory_date=date(2026, 7, 3),
        visibility="private",
        status="active",
    )
    db_session.add_all([m1, m2, m3])
    db_session.commit()
    return r_hanoi, r_hcm, r_danang


def test_ac1_get_regions_list_with_public_count(client, db_session):
    seed_region_data(db_session)
    res = client.get("/api/explore/regions")
    assert res.status_code == 200
    regions = res.json()["data"]
    assert len(regions) >= 3
    by_slug = {r["slug"]: r["count"] for r in regions}
    assert by_slug["ha-noi"] == 1
    assert by_slug["tp-ho-chi-minh"] == 1
    assert by_slug["da-nang"] == 0


def test_ac2_filter_memories_by_region_public_only(client, db_session):
    r_hanoi, _, _ = seed_region_data(db_session)
    res = client.get("/api/explore/memories", params={"region": r_hanoi.id})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Hồ Gươm sáng sớm"
    assert data["items"][0]["region"]["id"] == r_hanoi.id


def test_ac3_filter_region_with_no_memories_returns_empty(client, db_session):
    _, _, r_danang = seed_region_data(db_session)
    res = client.get("/api/explore/memories", params={"region": r_danang.id})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 0
    assert data["items"] == []


def test_ac4_filter_nonexistent_region_returns_empty(client, db_session):
    seed_region_data(db_session)
    res = client.get("/api/explore/memories", params={"region": 999999})
    assert res.status_code == 200
    assert res.json()["data"]["items"] == []