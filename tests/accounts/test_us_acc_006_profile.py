"""US-ACC-006 – Cập nhật hồ sơ cá nhân (tên, email, giới thiệu, ảnh đại diện) và thống kê trang hồ sơ."""
from __future__ import annotations

import struct
from datetime import date

import pytest

from app.core.config import settings
from app.core.security import create_access_token
from app.modules.accounts.models import User
from app.modules.memories.models import Memory, Trip

MB = 1024 * 1024


def _jpeg(size: int = 2000, with_gps: bool = False) -> bytes:
    body = b"\xff\xd8"
    if with_gps:
        exif = b"Exif\x00\x00GPSLatitude=21.0287"
        body += b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif
    body += b"\xff\xda\x00\x02"
    return body + b"\x00" * (size - len(body))


@pytest.fixture
def ctx(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    user = User(email="an@example.com", password_hash=None, display_name="An", role="user", status="active", token_version=0)
    other = User(email="binh@example.com", password_hash=None, display_name="Bình", role="user", status="active", token_version=0)
    db_session.add_all([user, other])
    db_session.flush()
    memory = Memory(user_id=user.id, title="Hồ Gươm", content="", memory_date=date(2025, 1, 1), place_name="Hà Nội",
                    latitude=21.0287, longitude=105.8524, visibility="public", status="active")
    db_session.add(memory)
    db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user.id, 0)}"}
    return client, db_session, user, memory, headers


def test_ac1_doi_ten_va_ky_uc_cong_khai_hien_ten_moi(ctx):
    client, _, _, memory, headers = ctx
    res = client.patch("/api/users/me", json={"display_name": "Dread", "bio": "Thích đi phượt"}, headers=headers)
    assert res.status_code == 200 and res.json()["data"]["display_name"] == "Dread"
    assert res.json()["data"]["bio"] == "Thích đi phượt"
    assert client.get(f"/api/memories/{memory.id}").json()["data"]["author"]["display_name"] == "Dread"
    items = client.get("/api/explore/memories").json()["data"]["items"]
    assert items[0]["author"]["display_name"] == "Dread"


def test_ac2_ten_dung_100_ky_tu(ctx):
    client, _, _, _, headers = ctx
    res = client.patch("/api/users/me", json={"display_name": "a" * 100}, headers=headers)
    assert res.status_code == 200 and len(res.json()["data"]["display_name"]) == 100


def test_ac3_ten_101_ky_tu(ctx):
    client, db_session, user, _, headers = ctx
    res = client.patch("/api/users/me", json={"display_name": "a" * 101}, headers=headers)
    assert res.status_code == 422 and res.json()["message"] == "Tên hiển thị tối đa 100 ký tự"
    db_session.expire_all()
    assert db_session.get(User, user.id).display_name == "An"


def test_ac4_anh_6mb_bi_tu_choi(ctx):
    client, _, _, _, headers = ctx
    res = client.post("/api/users/me/avatar", files={"avatar": ("big.jpg", _jpeg(6 * MB), "image/jpeg")}, headers=headers)
    assert res.status_code == 400 and res.json()["message"] == "Ảnh không được vượt quá 5 MB"


@pytest.mark.parametrize("name,content", [("baocao.pdf", b"%PDF-1.7 ..."), ("gia.jpg", b"%PDF-1.7 doi duoi")])
def test_ac5_tep_khong_phai_anh(ctx, name, content):
    client, _, _, _, headers = ctx
    res = client.post("/api/users/me/avatar", files={"avatar": (name, content, "application/pdf")}, headers=headers)
    assert res.status_code == 400 and res.json()["message"] == "Định dạng tệp không được hỗ trợ"


def test_anh_dai_dien_luu_xem_go_va_bo_gps(ctx):
    client, db_session, user, memory, headers = ctx
    res = client.post("/api/users/me/avatar", files={"avatar": ("me.jpg", _jpeg(with_gps=True), "image/jpeg")}, headers=headers)
    assert res.status_code == 200
    url = res.json()["data"]["avatar_url"]
    assert url.startswith(f"/api/users/{user.id}/avatar?v=")

    image = client.get(url)
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert b"GPS" not in image.content  # EXIF/GPS bị xóa trước khi lưu

    # Nơi công khai trả link, không lộ đường dẫn lưu trữ
    author = client.get(f"/api/memories/{memory.id}").json()["data"]["author"]
    assert author["avatar_url"] == url and "avatars/" not in author["avatar_url"]

    removed = client.delete("/api/users/me/avatar", headers=headers)
    assert removed.json()["data"]["avatar_url"] is None
    assert client.get(url).status_code == 404


def test_doi_email_trung_bi_chan(ctx):
    client, _, _, _, headers = ctx
    res = client.patch("/api/users/me", json={"email": "BINH@example.com"}, headers=headers)
    assert res.status_code == 409 and res.json()["message"] == "Email này đã được đăng ký"
    ok = client.patch("/api/users/me", json={"email": "an.moi@example.com"}, headers=headers)
    assert ok.json()["data"]["email"] == "an.moi@example.com"


def test_can_dang_nhap(client):
    assert client.patch("/api/users/me", json={"display_name": "X"}).status_code == 401


def test_thong_ke_trang_ho_so(ctx):
    client, db_session, user, _, headers = ctx
    db_session.add(Trip(user_id=user.id, name="Hà Nội"))
    db_session.add(Memory(user_id=user.id, title="Riêng", content="", memory_date=date(2025, 1, 1), place_name="X",
                          latitude=21, longitude=105, visibility="private", status="active"))
    db_session.commit()
    stats = client.get("/api/users/me/stats", headers=headers).json()["data"]
    assert stats == {"memories": 2, "public_memories": 1, "trips": 1, "places": 0}
