from datetime import date, datetime

import pytest

from app.modules.accounts.models import User
from app.modules.explore.models import Region
from app.modules.memories.models import Hashtag, Memory, MemoryHashtag


@pytest.fixture
def public_data(db_session):
    owner = User(
        email="explore@example.com",
        display_name="An",
        status="active",
        role="user",
    )
    locked = User(
        email="locked@example.com",
        display_name="Locked",
        status="locked",
        role="user",
    )
    region = Region(
        name="Lâm Đồng",
        slug="lam-dong",
        level="province",
    )

    db_session.add_all([owner, locked, region])
    db_session.flush()

    records = []

    for i in range(6):
        memory = Memory(
            user_id=locked.id if i == 4 else owner.id,
            title="Hồ Gươm" if i != 1 else "Dạo chơi",
            content="Nội dung riêng",
            place_name="Hồ Gươm",
            memory_date=date(2025, 1, i + 1),
            latitude=11.94,
            longitude=108.45,
            region_id=region.id if i == 0 else None,
            visibility="private" if i == 2 else "public",
            status="hidden" if i == 3 else "active",
            deleted_at=datetime(2025, 2, 1) if i == 5 else None,
        )
        db_session.add(memory)
        records.append(memory)

    tags = [
        Hashtag(name="dalat"),
        Hashtag(name="phuot"),
    ]
    db_session.add_all(tags)
    db_session.flush()

    db_session.add_all(
        [
            MemoryHashtag(
                memory_id=records[0].id,
                hashtag_id=tags[0].id,
                source="manual",
            ),
            MemoryHashtag(
                memory_id=records[0].id,
                hashtag_id=tags[1].id,
                source="manual",
            ),
            MemoryHashtag(
                memory_id=records[1].id,
                hashtag_id=tags[1].id,
                source="manual",
            ),
        ]
    )
    db_session.commit()

    return records, region, owner


def test_public_visibility_and_no_email(client, public_data):
    records, _, _ = public_data

    response = client.get("/api/explore/pins")
    assert response.status_code == 200
    assert {p["id"] for p in response.json()["data"]} == {
        records[0].id,
        records[1].id,
    }
    assert "email" not in response.text

    listing = client.get("/api/explore/memories")
    assert listing.json()["data"]["total"] == 2
    assert "email" not in listing.text

    overview = client.get("/api/explore/overview")
    assert overview.json()["data"] == {
        "public_memories": 2,
        "regions": 1,
    }


def test_keyword_case_and_date_order(client, public_data):
    records, _, _ = public_data

    for q in ["Hồ Gươm", "hồ gươm"]:
        response = client.get(
            "/api/explore/memories",
            params={"q": q},
        )
        assert response.status_code == 200
        assert [
            m["id"] for m in response.json()["data"]["items"]
        ] == [records[1].id, records[0].id]


@pytest.mark.parametrize(
    "path",
    ["/api/explore/pins", "/api/explore/memories"],
)
def test_short_keyword(client, path):
    response = client.get(path, params={"q": "a"})

    assert response.status_code == 422
    assert response.json()["message"] == "Nhập ít nhất 2 ký tự"


def test_no_results_message(client, public_data):
    response = client.get(
        "/api/explore/memories",
        params={"q": "xyzxyz"},
    )

    assert response.json()["message"] == (
        "Không tìm thấy kết quả cho xyzxyz"
    )
    assert response.json()["data"]["pages"] == 1


def test_tags_or_no_duplicate_and_empty_message(client, public_data):
    for raw in ["dalat phuot", "dalat,phuot", "#DALAT #phuot"]:
        response = client.get(
            "/api/explore/memories",
            params={"hashtags": raw},
        )
        assert response.json()["data"]["total"] == 2

    response = client.get(
        "/api/explore/memories",
        params={"hashtags": "bienxanh"},
    )
    assert response.json()["message"] == (
        "Chưa có ký ức nào với hashtag này"
    )


def test_region_slug_id_and_combined_filters(client, public_data):
    records, region, _ = public_data

    for value in [region.slug, str(region.id)]:
        response = client.get(
            "/api/explore/memories",
            params={"region": value, "hashtags": "phuot"},
        )
        assert response.status_code == 200
        assert [
            m["id"] for m in response.json()["data"]["items"]
        ] == [records[0].id]

    regions = client.get("/api/explore/regions").json()["data"]
    assert regions[0]["public_count"] == regions[0]["count"] == 1


def test_pins_use_same_filters(client, public_data):
    records, _, _ = public_data

    response = client.get(
        "/api/explore/pins",
        params={"hashtags": "phuot"},
    )
    assert len(response.json()["data"]) == 2

    params = {
        "hashtags": "phuot",
        "region": "lam-dong",
        "q": "Hồ Gươm",
    }
    response = client.get("/api/explore/pins", params=params)
    assert [
        p["id"] for p in response.json()["data"]
    ] == [records[0].id]


def test_bbox_and_empty_region(client, public_data):
    params = {
        "south": 20,
        "north": 22,
        "west": 104,
        "east": 106,
    }

    response = client.get("/api/explore/pins", params=params)
    assert response.json()["data"] == []

    response = client.get("/api/explore/memories", params=params)
    assert response.json()["message"] == (
        "Chưa có ký ức công khai trong khu vực này"
    )

    params["south"] = 25
    response = client.get("/api/explore/pins", params=params)
    assert response.status_code == 422


def test_pagination(client, public_data):
    first = client.get(
        "/api/explore/memories",
        params={"page_size": 1},
    ).json()["data"]

    second = client.get(
        "/api/explore/memories",
        params={"page_size": 1, "page": 2},
    ).json()["data"]

    assert first["pages"] == second["pages"] == 2
    assert first["items"][0]["id"] != second["items"][0]["id"]


def test_pin_limit_500(client, db_session, public_data):
    _, _, owner = public_data

    db_session.add_all(
        [
            Memory(
                user_id=owner.id,
                title=f"Extra {i}",
                content="Test",
                place_name="Hà Nội",
                latitude=21,
                longitude=105,
                memory_date=date(2025, 1, 1),
                visibility="public",
                status="active",
            )
            for i in range(505)
        ]
    )
    db_session.commit()

    response = client.get("/api/explore/pins")
    assert len(response.json()["data"]) == 500