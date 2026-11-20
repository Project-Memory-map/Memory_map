"""US-MEM-001 – Tìm địa điểm theo tên để tạo ký ức (Nominatim được giả lập, không gọi mạng)."""
from __future__ import annotations

import httpx
import pytest

from app.core.security import create_access_token
from app.modules.accounts.models import User
from app.modules.memories.services import place_search_service as search


@pytest.fixture(autouse=True)
def _fresh_cache():
    search.clear_cache()
    yield
    search.clear_cache()


def _fake(monkeypatch, payload=None, status=200, error=None):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append({"url": url, "params": params, "headers": headers})
        if error:
            raise error
        return httpx.Response(status, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(search.httpx, "get", fake_get)
    return calls


HO_GUOM = [{"lat": "21.0287", "lon": "105.8524", "name": "Hồ Gươm",
            "display_name": "Hồ Gươm, Hoàn Kiếm, Hà Nội, Việt Nam"},
           {"lat": "abc", "lon": "105", "name": "Hỏng"}]


def test_ac1_tim_ho_guom_tra_ten_va_toa_do(client, monkeypatch):
    calls = _fake(monkeypatch, HO_GUOM)
    res = client.get("/api/geocode", params={"q": "  Hồ   Gươm "})
    assert res.status_code == 200
    assert res.json()["data"] == [{"name": "Hồ Gươm", "display_name": "Hồ Gươm, Hoàn Kiếm, Hà Nội, Việt Nam",
                                   "latitude": 21.0287, "longitude": 105.8524}]
    assert calls[0]["url"].endswith("/search") and calls[0]["params"]["q"] == "Hồ Gươm"
    assert calls[0]["headers"]["User-Agent"]  # chính sách Nominatim bắt buộc User-Agent


def test_ac1_tao_ky_uc_tu_ket_qua_tim_mac_dinh_rieng_tu(client, db_session, monkeypatch):
    _fake(monkeypatch, HO_GUOM)
    place = client.get("/api/geocode", params={"q": "Hồ Gươm"}).json()["data"][0]
    user = User(email="a@example.com", password_hash=None, display_name="A", role="user", status="active", token_version=0)
    db_session.add(user)
    db_session.commit()
    res = client.post("/api/memories", headers={"Authorization": f"Bearer {create_access_token(user.id, 0)}"}, data={
        "title": "Chiều thu Hà Nội", "content": "...", "memory_date": "2025-10-12", "place_name": place["name"],
        "latitude": str(place["latitude"]), "longitude": str(place["longitude"])})
    data = res.json()["data"]
    assert res.status_code == 201 and data["visibility"] == "private" and str(data["memory_date"]) == "2025-10-12"
    assert (data["latitude"], data["longitude"]) == (21.0287, 105.8524)


def test_ac3_khong_tim_thay(client, monkeypatch):
    _fake(monkeypatch, [])
    res = client.get("/api/geocode", params={"q": "xyzxyz"})
    assert res.status_code == 200 and res.json()["data"] == []
    assert res.json()["message"] == "Không tìm thấy địa điểm. Hãy thử tên khác hoặc chọn trực tiếp trên bản đồ"


@pytest.mark.parametrize("q", ["", "a", "x" * 201])
def test_tu_khoa_khong_hop_le(client, monkeypatch, q):
    calls = _fake(monkeypatch, [])
    res = client.get("/api/geocode", params={"q": q})
    assert res.status_code == 422 and calls == []


def test_dich_vu_loi_tra_503(client, monkeypatch):
    _fake(monkeypatch, error=httpx.ConnectTimeout("timeout"))
    res = client.get("/api/geocode", params={"q": "Hồ Gươm"})
    assert res.status_code == 503 and "chọn trực tiếp trên bản đồ" in res.json()["message"]


def test_cache_khong_goi_lai_khi_tim_lai(client, monkeypatch):
    calls = _fake(monkeypatch, HO_GUOM)
    client.get("/api/geocode", params={"q": "Hồ Gươm"})
    client.get("/api/geocode", params={"q": "hồ gươm"})
    assert len(calls) == 1
