"""Sửa lỗi kiểm thử tích hợp T05B58C:
- L05: ký ức được gán tỉnh/thành theo tọa độ khi tạo và khi sửa (US-EXP-003 AC1, US-MEM-006 AC2, US-MEM-002 AC2).
- L06: API chi tiết trả link ảnh/video có chữ ký, mở được (US-MEM-003/004/005).
- L13: ảnh tải lên bị xóa EXIF/GPS.
"""
from __future__ import annotations

import struct

import pytest

from app.core.config import settings
from app.core.security import create_access_token
from app.modules.accounts.models import User
from app.modules.explore.models import Region
from app.modules.explore.region_lookup import province_slug
from app.modules.memories.services.image_metadata import strip_metadata


@pytest.mark.parametrize("lat,lng,slug", [
    (21.0287, 105.8524, "ha-noi"), (11.9404, 108.4583, "lam-dong"), (10.7725, 106.6980, "tp-ho-chi-minh"),
    (10.2270, 103.9640, "an-giang"), (13.7765, 109.2237, "gia-lai"), (16.0610, 108.2470, "da-nang"),
    (48.8584, 2.2945, None), (14.0, 112.0, None),
])
def test_tra_tinh_thanh_theo_toa_do(lat, lng, slug):
    assert province_slug(lat, lng) == slug


@pytest.fixture
def ctx(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    db_session.add_all([Region(name="Hà Nội", slug="ha-noi"), Region(name="Lâm Đồng", slug="lam-dong")])
    user = User(email="a@example.com", password_hash=None, display_name="A", role="user", status="active", token_version=0)
    db_session.add(user)
    db_session.commit()
    return client, db_session, {"Authorization": f"Bearer {create_access_token(user.id, 0)}"}


def _create(client, headers, lat, lng, visibility="public"):
    res = client.post("/api/memories", headers=headers, data={
        "title": "Ký ức", "memory_date": "2025-10-12", "place_name": "Nơi nào đó",
        "latitude": str(lat), "longitude": str(lng), "visibility": visibility})
    assert res.status_code == 201
    return res.json()["data"]


def test_tao_ky_uc_gan_khu_vuc_va_loc_duoc(ctx):
    client, _, headers = ctx
    memory = _create(client, headers, 11.9404, 108.4583)
    assert memory["region"]["name"] == "Lâm Đồng"
    lam_dong = client.get("/api/explore/regions").json()["data"]
    region_id = next(r["id"] for r in lam_dong if r["slug"] == "lam-dong")
    items = client.get("/api/explore/memories", params={"region": region_id}).json()["data"]["items"]
    assert [m["id"] for m in items] == [memory["id"]]


def test_doi_dia_diem_doi_khu_vuc(ctx):
    client, _, headers = ctx
    memory = _create(client, headers, 21.0287, 105.8524)
    assert memory["region"]["name"] == "Hà Nội"
    res = client.patch(f"/api/memories/{memory['id']}", headers=headers,
                       data={"place_name": "Đà Lạt", "latitude": "11.9404", "longitude": "108.4583"})
    assert res.json()["data"]["region"]["name"] == "Lâm Đồng"


def test_nuoc_ngoai_khong_gan_khu_vuc(ctx):
    client, _, headers = ctx
    assert _create(client, headers, 48.8584, 2.2945)["region"] is None


def _jpeg_with_gps(size=4000) -> bytes:
    exif = b"Exif\x00\x00GPSLatitude=21.0287"
    head = b"\xff\xd8" + b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif + b"\xff\xda\x00\x02"
    return head + b"\x00" * (size - len(head))


def test_chi_tiet_tra_link_anh_video_co_chu_ky_mo_duoc(ctx):
    client, _, headers = ctx
    memory = _create(client, headers, 21.0287, 105.8524)
    client.post(f"/api/memories/{memory['id']}/images", headers=headers,
                files=[("images", ("a.jpg", _jpeg_with_gps(), "image/jpeg"))])
    video = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 500
    client.post(f"/api/memories/{memory['id']}/video", headers=headers, files=[("video", ("v.mp4", video, "video/mp4"))])

    detail = client.get(f"/api/memories/{memory['id']}").json()["data"]
    assert detail["status"] == "active"
    by_type = {m["type"]: m for m in detail["media"]}
    assert "sig=" in by_type["image"]["url"] and "/stream?" in by_type["video"]["url"]
    image = client.get(by_type["image"]["url"])
    assert image.status_code == 200 and b"GPS" not in image.content  # L13: GPS đã bị xóa
    assert client.get(by_type["video"]["url"], headers={"Range": "bytes=0-99"}).status_code == 206


@pytest.mark.parametrize("ext,data", [
    (".jpg", b"\xff\xd8\xff\xe1\x00\x0aExif\x00\x00GP\xff\xda\x00\x02DATA"),
    (".png", b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 3) + b"eXIfGPS" + b"\x00" * 4
             + struct.pack(">I", 0) + b"IEND" + b"\x00" * 4),
])
def test_bo_loc_exif(ext, data):
    clean = strip_metadata(data, ext)
    assert b"GP" not in clean and len(clean) < len(data)


def test_dinh_dang_la_giu_nguyen():
    assert strip_metadata(b"\xff\xd8garbage", ".jpg") == b"\xff\xd8garbage"
    assert strip_metadata(b"GIF89a....", ".gif") == b"GIF89a...."
