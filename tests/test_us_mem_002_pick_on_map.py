"""US-MEM-002 – Tạo ký ức bằng chọn vị trí trên bản đồ (T05B579)."""
from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.modules.accounts.models import User
from app.modules.memories.models import Memory
from app.modules.memories.services import reverse_geocode_service as geo

LAT, LNG = 16.054407, 108.202167  # Đà Nẵng


@pytest.fixture(autouse=True)
def _fresh_cache():
    geo.clear_cache()
    yield
    geo.clear_cache()


@pytest.fixture
def token(db_session) -> str:
    user = User(email="ghim@example.com", display_name="Nguoi Ghim", role="user", status="active", token_version=0)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return create_access_token(user.id, user.token_version)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _fake_nominatim(monkeypatch, payload=None, error: Exception | None = None) -> list[dict]:
    calls: list[dict] = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append({"url": url, "params": params, "headers": headers})
        if error:
            raise error
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(geo.httpx, "get", fake_get)
    return calls


def _form(**overrides) -> dict[str, str]:
    data = {
        "title": "Chiều ở cầu Rồng",
        "place_name": "Cầu Rồng",
        "latitude": str(LAT),
        "longitude": str(LNG),
        "memory_date": "2025-06-01",
        "content": "Xem cầu phun lửa",
        "visibility": "private",
    }
    data.update(overrides)
    return {key: value for key, value in data.items() if value is not None}


# ----- Lấy tên địa điểm từ tọa độ đã chọn -----

def test_reverse_tra_ten_dia_diem_va_giu_dung_toa_do_da_chon(client, monkeypatch) -> None:
    calls = _fake_nominatim(monkeypatch, {
        "name": "Cầu Rồng",
        "display_name": "Cầu Rồng, Hải Châu, Đà Nẵng, Việt Nam",
        "lat": "16.0610", "lon": "108.2270",
    })

    response = client.get("/api/geocode/reverse", params={"lat": LAT, "lng": LNG})
    data = response.json()["data"]

    assert response.status_code == 200
    assert data == {
        "name": "Cầu Rồng",
        "display_name": "Cầu Rồng, Hải Châu, Đà Nẵng, Việt Nam",
        "latitude": LAT,
        "longitude": LNG,
    }
    assert calls[0]["params"]["lat"] == LAT and calls[0]["params"]["lon"] == LNG
    assert calls[0]["headers"]["User-Agent"]  # chính sách Nominatim bắt buộc


def test_reverse_khong_co_name_thi_lay_ten_tu_dia_chi(client, monkeypatch) -> None:
    _fake_nominatim(monkeypatch, {
        "name": "",
        "display_name": "Đường Bạch Đằng, Hải Châu, Đà Nẵng",
        "address": {"road": "Đường Bạch Đằng", "city": "Đà Nẵng"},
    })

    data = client.get("/api/geocode/reverse", params={"lat": LAT, "lng": LNG}).json()["data"]

    assert data["name"] == "Đường Bạch Đằng"


def test_reverse_giua_bien_khong_co_dia_danh_tra_null(client, monkeypatch) -> None:
    _fake_nominatim(monkeypatch, {"error": "Unable to geocode"})

    response = client.get("/api/geocode/reverse", params={"lat": 10.0, "lng": 115.0})

    assert response.status_code == 200
    assert response.json()["data"] is None


def test_reverse_dich_vu_loi_tra_503_de_giao_dien_tu_dien_toa_do(client, monkeypatch) -> None:
    _fake_nominatim(monkeypatch, error=httpx.ConnectTimeout("timeout"))

    response = client.get("/api/geocode/reverse", params={"lat": LAT, "lng": LNG})

    assert response.status_code == 503


def test_reverse_hai_lan_nhap_gan_nhau_chi_goi_dich_vu_mot_lan(client, monkeypatch) -> None:
    calls = _fake_nominatim(monkeypatch, {"name": "Cầu Rồng", "display_name": "Cầu Rồng"})

    first = client.get("/api/geocode/reverse", params={"lat": LAT, "lng": LNG}).json()["data"]
    second = client.get("/api/geocode/reverse", params={"lat": LAT + 0.000001, "lng": LNG}).json()["data"]

    assert len(calls) == 1
    assert first["name"] == second["name"] == "Cầu Rồng"
    assert second["latitude"] == LAT + 0.000001


@pytest.mark.parametrize("params", [{"lat": 91, "lng": 0}, {"lat": 0, "lng": 181}, {"lat": "abc", "lng": 0}, {"lat": 10}])
def test_reverse_toa_do_khong_hop_le_tra_422(client, monkeypatch, params) -> None:
    calls = _fake_nominatim(monkeypatch, {"name": "x"})

    response = client.get("/api/geocode/reverse", params=params)

    assert response.status_code == 422
    assert calls == []


# ----- Lưu ký ức tại vị trí đã chọn -----

def test_tao_ky_uc_tai_vi_tri_da_chon_tra_201(client, db_session, token) -> None:
    response = client.post("/api/memories", data=_form(), headers=_auth(token))
    body = response.json()

    assert response.status_code == 201
    assert body["message"] == "Đã lưu ký ức"
    data = body["data"]
    assert data["id"] > 0
    assert data["title"] == "Chiều ở cầu Rồng"
    assert data["place_name"] == "Cầu Rồng"
    assert data["latitude"] == pytest.approx(LAT)
    assert data["longitude"] == pytest.approx(LNG)
    assert data["is_owner"] is True

    saved = db_session.scalar(select(Memory).where(Memory.id == data["id"]))
    assert saved.latitude == pytest.approx(LAT)
    assert saved.longitude == pytest.approx(LNG)


def test_ky_uc_moi_mac_dinh_rieng_tu(client, token) -> None:
    form = _form()
    del form["visibility"]

    data = client.post("/api/memories", data=form, headers=_auth(token)).json()["data"]

    assert data["visibility"] == "private"  # BR-01


def test_ky_uc_vua_tao_xem_lai_duoc(client, token) -> None:
    memory_id = client.post("/api/memories", data=_form(), headers=_auth(token)).json()["data"]["id"]

    detail = client.get(f"/api/memories/{memory_id}", headers=_auth(token))

    assert detail.status_code == 200
    assert detail.json()["data"]["place_name"] == "Cầu Rồng"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"latitude": None, "longitude": None}, "Vui lòng chọn vị trí trên bản đồ hoặc tìm địa điểm"),
        ({"longitude": None}, "Vui lòng chọn vị trí trên bản đồ hoặc tìm địa điểm"),
        ({"latitude": "95"}, "Tọa độ không hợp lệ"),
        ({"place_name": "   "}, "Vui lòng nhập tên địa điểm"),
        ({"title": ""}, "Vui lòng nhập tiêu đề"),
        ({"title": "a" * 201}, "Tiêu đề tối đa 200 ký tự"),
        ({"memory_date": None}, "Vui lòng chọn ngày"),
        ({"memory_date": (date.today() + timedelta(days=1)).isoformat()}, "Ngày không được ở tương lai"),
        ({"visibility": "friends"}, "Chế độ hiển thị không hợp lệ"),
    ],
)
def test_du_lieu_khong_hop_le_tra_422_va_khong_luu(client, db_session, token, overrides, message) -> None:
    response = client.post("/api/memories", data=_form(**overrides), headers=_auth(token))

    assert response.status_code == 422
    assert response.json()["message"] == message
    assert db_session.scalar(select(Memory)) is None


def test_chua_dang_nhap_khong_tao_duoc_ky_uc(client, db_session) -> None:
    response = client.post("/api/memories", data=_form())

    assert response.status_code == 401
    assert db_session.scalar(select(Memory)) is None
