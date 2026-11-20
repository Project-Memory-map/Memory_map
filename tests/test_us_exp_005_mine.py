"""US-EXP-005 - Lọc ký ức cá nhân theo thời gian (T05B587)."""
from datetime import date, datetime, timezone

from app.core.security import create_access_token
from app.modules.accounts.models import User
from app.modules.memories.models import Memory


def make_user_headers(db_session, email: str, name: str):
    user = User(
        email=email,
        display_name=name,
        password_hash="hashed",
        role="user",
        status="active",
    )
    db_session.add(user)
    db_session.flush()
    token = create_access_token(user.id, user.token_version)
    return user, {"Authorization": f"Bearer {token}"}


def seed_mine_data(db_session):
    user_a, headers_a = make_user_headers(db_session, "user_a@example.com", "User A")
    user_b, _ = make_user_headers(db_session, "user_b@example.com", "User B")

    specs = [
        ("Ký ức 05/01/2024", date(2024, 1, 5), "private", None),
        ("Ký ức 01/06/2024", date(2024, 6, 1), "public", None),
        ("Ký ức 02/06/2024", date(2024, 6, 2), "private", None),
        ("Ký ức 01/12/2024", date(2024, 12, 1), "public", None),
        ("Ký ức 01/03/2025", date(2025, 3, 1), "private", None),
        ("Ký ức 31/03/2025", date(2025, 3, 31), "public", None),
        ("Ký ức 07/07/2025", date(2025, 7, 7), "private", None),
        ("Ký ức đã xóa", date(2023, 5, 5), "public", datetime.now(timezone.utc)),
    ]

    for title, m_date, vis, deleted_at in specs:
        db_session.add(
            Memory(
                user_id=user_a.id,
                title=title,
                content="Nội dung",
                place_name="Việt Nam",
                latitude=10.77,
                longitude=106.70,
                memory_date=m_date,
                visibility=vis,
                status="active",
                deleted_at=deleted_at,
            )
        )

    db_session.add(
        Memory(
            user_id=user_b.id,
            title="Ký ức của User B",
            content="Không được lộ",
            place_name="Hà Nội",
            latitude=21.02,
            longitude=105.85,
            memory_date=date(2024, 6, 1),
            visibility="public",
            status="active",
        )
    )
    db_session.commit()
    return headers_a


def test_mine_all_and_isolates_other_user_and_deleted(client, db_session):
    headers_a = seed_mine_data(db_session)
    res = client.get("/api/memories/mine", headers=headers_a)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 7
    titles = [item["title"] for item in data["items"]]
    assert "Ký ức của User B" not in titles
    assert "Ký ức đã xóa" not in titles


def test_ac1_filter_year_2024_asc_includes_private_and_public(client, db_session):
    headers_a = seed_mine_data(db_session)
    res = client.get("/api/memories/mine", params={"year": 2024, "order": "asc"}, headers=headers_a)
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) == 4
    assert [i["title"] for i in items] == [
        "Ký ức 05/01/2024",
        "Ký ức 01/06/2024",
        "Ký ức 02/06/2024",
        "Ký ức 01/12/2024",
    ]


def test_ac2_filter_date_range_inclusive(client, db_session):
    headers_a = seed_mine_data(db_session)
    res = client.get(
        "/api/memories/mine",
        params={"date_from": "2025-03-01", "date_to": "2025-03-31"},
        headers=headers_a,
    )
    assert res.status_code == 200
    titles = {item["title"] for item in res.json()["data"]["items"]}
    assert titles == {"Ký ức 01/03/2025", "Ký ức 31/03/2025"}


def test_ac3_invalid_date_range_returns_422(client, db_session):
    headers_a = seed_mine_data(db_session)
    res = client.get(
        "/api/memories/mine",
        params={"date_from": "2025-03-31", "date_to": "2025-03-01"},
        headers=headers_a,
    )
    assert res.status_code == 422
    assert "Ngày bắt đầu phải trước hoặc bằng ngày kết thúc" in res.json()["message"]


def test_ac4_empty_year_returns_exact_message(client, db_session):
    headers_a = seed_mine_data(db_session)
    res = client.get("/api/memories/mine", params={"year": 2020}, headers=headers_a)
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["total"] == 0
    assert body["message"] == "Bạn chưa có ký ức nào trong khoảng thời gian này"


def test_filter_year_and_month(client, db_session):
    headers_a = seed_mine_data(db_session)
    res = client.get("/api/memories/mine", params={"year": 2024, "month": 6}, headers=headers_a)
    assert res.status_code == 200
    assert res.json()["data"]["total"] == 2


def test_mine_years_and_pins_and_unauthorized(client, db_session):
    headers_a = seed_mine_data(db_session)

    res_years = client.get("/api/memories/mine/years", headers=headers_a)
    assert res_years.status_code == 200
    assert res_years.json()["data"] == [2025, 2024]

    res_pins = client.get("/api/memories/mine/pins", params={"year": 2025}, headers=headers_a)
    assert res_pins.status_code == 200
    assert len(res_pins.json()["data"]) == 3

    res_unauth = client.get("/api/memories/mine")
    assert res_unauth.status_code == 401