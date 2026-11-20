"""FR-3.6 (T05B590) - Gợi ý hashtag bằng Gemini AI và xác nhận lưu với source='ai'."""
from __future__ import annotations

from datetime import date

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.modules.accounts.models import User
from app.modules.memories import hashtag_service
from app.modules.memories.models import Hashtag, Memory, MemoryHashtag


def make_owner_and_memory(db_session):
    user = User(
        email="gemini_tester@example.com",
        display_name="Người dùng test Gemini",
        password_hash="hashed",
        role="user",
        status="active",
    )
    db_session.add(user)
    db_session.flush()

    memory = Memory(
        user_id=user.id,
        title="Săn mây sáng sớm trên đồi Đa Phú",
        content="Trời lạnh se se, biển mây trắng xóa cực đẹp",
        place_name="Đà Lạt, Lâm Đồng",
        latitude=11.9812,
        longitude=108.4314,
        memory_date=date(2026, 11, 15),
        visibility="public",
        status="active",
    )
    db_session.add(memory)
    db_session.commit()

    token = create_access_token(user.id, user.token_version)
    return user, memory, {"Authorization": f"Bearer {token}"}


def test_suggest_hashtags_with_gemini_engine(client, db_session, monkeypatch):
    _, _, headers = make_owner_and_memory(db_session)

    def fake_gemini(title=None, content=None, place_name=None):
        return hashtag_service._clean_ai_candidate_tags(
            ["#ĐàLạt", "săn mây", "Đồi_Đa_Phú", "dulich", "kyniem"]
        )

    monkeypatch.setattr(hashtag_service, "_suggest_with_gemini", fake_gemini)

    res = client.post(
        "/api/memories/suggest-hashtags",
        json={
            "title": "Săn mây sáng sớm trên đồi Đa Phú",
            "content": "Trời lạnh se se, biển mây trắng xóa cực đẹp",
            "place_name": "Đà Lạt, Lâm Đồng",
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["engine"] == "gemini"
    assert data["hashtags"] == ["đàlạt", "sănmây", "đồi_đa_phú", "dulich", "kyniem"]


def test_suggest_hashtags_fallback_local_when_gemini_fails_or_no_key(client, db_session, monkeypatch):
    _, _, headers = make_owner_and_memory(db_session)

    # 1. Không có API key -> lùi về local
    monkeypatch.setattr(settings, "gemini_api_key", "")
    res_no_key = client.post(
        "/api/memories/suggest-hashtags",
        json={"title": "Hoàng hôn Hồ Tây", "place_name": "Hà Nội"},
        headers=headers,
    )
    assert res_no_key.status_code == 200
    assert res_no_key.json()["data"]["engine"] == "local"
    assert len(res_no_key.json()["data"]["hashtags"]) > 0

    # 2. Gemini lỗi mạng/HTTP -> vẫn lùi về local an toàn
    def fake_gemini_error(title=None, content=None, place_name=None):
        raise httpx.ConnectError("Timeout")

    monkeypatch.setattr(hashtag_service, "_suggest_with_gemini", fake_gemini_error)
    res_err = client.post(
        "/api/memories/suggest-hashtags",
        json={"title": "Hoàng hôn Hồ Tây", "place_name": "Hà Nội"},
        headers=headers,
    )
    assert res_err.status_code == 200
    assert res_err.json()["data"]["engine"] == "local"


def test_confirm_ai_suggested_hashtags_saves_with_source_ai(client, db_session):
    _, memory, headers = make_owner_and_memory(db_session)

    res = client.post(
        f"/api/memories/{memory.id}/hashtags",
        json={
            "hashtags": ["đàlạt", "sănmây", "ghichu_rieng"],
            "ai_hashtags": ["đàlạt", "sănmây"],
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["hashtag_sources"]["đàlạt"] == "ai"
    assert data["hashtag_sources"]["sănmây"] == "ai"
    assert data["hashtag_sources"]["ghichu_rieng"] == "manual"

    rows = db_session.execute(
        select(Hashtag.name, MemoryHashtag.source)
        .join(MemoryHashtag, MemoryHashtag.hashtag_id == Hashtag.id)
        .where(MemoryHashtag.memory_id == memory.id)
    ).all()
    db_sources = {name: source for name, source in rows}
    assert db_sources == {
        "đàlạt": "ai",
        "sănmây": "ai",
        "ghichu_rieng": "manual",
    }


def test_suggest_hashtags_requires_authentication(client):
    res = client.post(
        "/api/memories/suggest-hashtags",
        json={"title": "Test chưa đăng nhập"},
    )
    assert res.status_code == 401