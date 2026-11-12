"""US-MEM-008 – Đổi chế độ riêng tư hoặc công khai của ký ức (FR-2.6)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from app.modules.accounts.models import User
from app.modules.memories.models import Memory


def _jpeg_bytes(marker: bytes = b"a", size: int = 128) -> bytes:
    signature = b"\xff\xd8\xff" + marker[:1]
    return signature + b"\x00" * (size - len(signature))


def _video_bytes(size: int = 128) -> bytes:
    header = b"\x00\x00\x00\x18ftypmp42"
    return header + b"\x00" * (size - len(header))


@pytest.fixture
def privacy_context(client: TestClient, db_session, tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")

    owner = User(
        email="owner-privacy@example.com",
        password_hash=None,
        display_name="Chủ Ký Ức",
        role="user",
        status="active",
        token_version=0,
    )
    other = User(
        email="other-privacy@example.com",
        password_hash=None,
        display_name="Người Dùng Khác",
        role="user",
        status="active",
        token_version=0,
    )
    db_session.add_all([owner, other])
    db_session.flush()

    past_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    memory = Memory(
        user_id=owner.id,
        title="Chiều hoàng hôn Hồ Tây",
        content="Kỷ niệm đáng nhớ tại Hà Nội",
        memory_date=date(2025, 5, 10),
        place_name="Hồ Tây, Hà Nội",
        latitude=21.0583,
        longitude=105.8232,
        visibility="private",
        status="active",
        created_at=past_time,
        updated_at=past_time,
    )
    db_session.add(memory)
    db_session.commit()

    owner_token = create_access_token(owner.id, owner.token_version)
    other_token = create_access_token(other.id, other.token_version)
    return client, db_session, memory.id, owner_token, other_token


def test_ac1_switch_to_public(privacy_context):
    client, db_session, memory_id, owner_token, other_token = privacy_context

    # Đính kèm 1 ảnh và 1 video khi ký ức đang private
    img_res = client.post(
        f"/api/memories/{memory_id}/images",
        headers={"Authorization": f"Bearer {owner_token}"},
        files=[("images", ("sunset.jpg", _jpeg_bytes(), "image/jpeg"))],
    )
    assert img_res.status_code == 200
    image_url = img_res.json()["data"][0]["url"]

    vid_res = client.post(
        f"/api/memories/{memory_id}/video",
        headers={"Authorization": f"Bearer {owner_token}"},
        files=[("video", ("sunset.mp4", _video_bytes(), "video/mp4"))],
    )
    assert vid_res.status_code == 200
    video_url = vid_res.json()["data"]["url"]

    before_updated = db_session.get(Memory, memory_id).updated_at

    # Khi: Chủ ký ức gọi API chuyển chế độ sang công khai (public)
    response = client.patch(
        f"/api/memories/{memory_id}/visibility",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"visibility": "public"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["statusCode"] == 200
    assert body["error"] is None
    assert body["data"]["id"] == memory_id
    assert body["data"]["visibility"] == "public"

    db_session.expire_all()
    memory = db_session.get(Memory, memory_id)
    assert memory.visibility == "public"
    assert memory.updated_at >= before_updated

    # Ký ức xuất hiện trên bản đồ công khai ở lần tải kế tiếp
    pins_res = client.get(
        "/api/explore/pins",
        params={"south": 20.0, "west": 105.0, "north": 22.0, "east": 106.0},
    )
    assert pins_res.status_code == 200
    pin_ids = [pin["id"] for pin in pins_res.json()["data"]]
    assert memory_id in pin_ids

    # Khách (chưa đăng nhập) và người dùng khác xem được chi tiết ký ức và ảnh/video đính kèm
    guest_detail = client.get(f"/api/memories/{memory_id}")
    assert guest_detail.status_code == 200
    assert guest_detail.json()["data"]["id"] == memory_id
    assert guest_detail.json()["data"]["visibility"] == "public"
    assert guest_detail.json()["data"]["is_owner"] is False

    other_detail = client.get(
        f"/api/memories/{memory_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other_detail.status_code == 200

    guest_images = client.get(f"/api/memories/{memory_id}/images")
    assert guest_images.status_code == 200
    assert len(guest_images.json()["data"]) == 1

    assert client.get(image_url).status_code == 200
    assert client.get(image_url, headers={"Authorization": f"Bearer {other_token}"}).status_code == 200
    assert client.get(video_url).status_code == 200
    assert client.get(video_url, headers={"Authorization": f"Bearer {other_token}"}).status_code == 200


def test_ac2_switch_to_private_blocks_public_and_media_access(privacy_context):
    client, db_session, memory_id, owner_token, other_token = privacy_context

    # Given: Ký ức đang ở chế độ công khai (public) và có đính kèm ảnh + video
    memory = db_session.get(Memory, memory_id)
    memory.visibility = "public"
    db_session.commit()

    img_res = client.post(
        f"/api/memories/{memory_id}/images",
        headers={"Authorization": f"Bearer {owner_token}"},
        files=[("images", ("public-photo.jpg", _jpeg_bytes(b"p"), "image/jpeg"))],
    )
    assert img_res.status_code == 200
    image_url = img_res.json()["data"][0]["url"]

    vid_res = client.post(
        f"/api/memories/{memory_id}/video",
        headers={"Authorization": f"Bearer {owner_token}"},
        files=[("video", ("public-clip.mp4", _video_bytes(), "video/mp4"))],
    )
    assert vid_res.status_code == 200
    video_url = vid_res.json()["data"]["url"]

    # Xác nhận khi đang public thì khách mở được ảnh và thấy trên bản đồ
    assert client.get(image_url).status_code == 200
    pins_before = client.get(
        "/api/explore/pins",
        params={"south": 20.0, "west": 105.0, "north": 22.0, "east": 106.0},
    )
    assert memory_id in [pin["id"] for pin in pins_before.json()["data"]]

    # When: Chủ ký ức gọi API chuyển chế độ về riêng tư (private)
    response = client.patch(
        f"/api/memories/{memory_id}/visibility",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"visibility": "private"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["statusCode"] == 200
    assert body["data"]["visibility"] == "private"

    db_session.expire_all()
    assert db_session.get(Memory, memory_id).visibility == "private"

    # Then 1: Ký ức lập tức biến mất khỏi bản đồ công khai và kết quả xem chi tiết của người khác
    pins_after = client.get(
        "/api/explore/pins",
        params={"south": 20.0, "west": 105.0, "north": 22.0, "east": 106.0},
    )
    assert pins_after.status_code == 200
    assert memory_id not in [pin["id"] for pin in pins_after.json()["data"]]

    assert client.get(f"/api/memories/{memory_id}").status_code == 404
    assert (
        client.get(
            f"/api/memories/{memory_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        ).status_code
        == 404
    )

    # Then 2: Khách hoặc người dùng khác mở trực tiếp đường dẫn ảnh/video cũ nhận lỗi 403 (ForbiddenException)
    guest_img_res = client.get(image_url)
    assert guest_img_res.status_code == 403
    assert guest_img_res.json()["statusCode"] == 403
    assert guest_img_res.json()["error"] == "FORBIDDEN"

    other_img_res = client.get(image_url, headers={"Authorization": f"Bearer {other_token}"})
    assert other_img_res.status_code == 403
    assert other_img_res.json()["statusCode"] == 403
    assert other_img_res.json()["error"] == "FORBIDDEN"

    guest_vid_res = client.get(video_url)
    assert guest_vid_res.status_code == 403
    assert guest_vid_res.json()["statusCode"] == 403

    other_vid_res = client.get(video_url, headers={"Authorization": f"Bearer {other_token}"})
    assert other_vid_res.status_code == 403
    assert other_vid_res.json()["statusCode"] == 403

    # Chủ sở hữu ký ức vẫn xem được bình thường
    owner_detail = client.get(
        f"/api/memories/{memory_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_detail.status_code == 200
    assert client.get(image_url, headers={"Authorization": f"Bearer {owner_token}"}).status_code == 200
    assert client.get(video_url, headers={"Authorization": f"Bearer {owner_token}"}).status_code == 200


def test_ac3_non_owner_cannot_change_privacy(privacy_context):
    client, db_session, memory_id, _, other_token = privacy_context

    response = client.patch(
        f"/api/memories/{memory_id}/visibility",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"visibility": "public"},
    )
    body = response.json()
    assert response.status_code == 403
    assert body["statusCode"] == 403
    assert body["error"] == "FORBIDDEN"

    db_session.expire_all()
    memory = db_session.get(Memory, memory_id)
    assert memory.visibility == "private"


@pytest.mark.parametrize("invalid_value", ["friends_only", "secret", "", None])
def test_invalid_visibility_returns_422(privacy_context, invalid_value):
    client, db_session, memory_id, owner_token, _ = privacy_context

    response = client.patch(
        f"/api/memories/{memory_id}/visibility",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"visibility": invalid_value},
    )
    body = response.json()
    assert response.status_code == 422
    assert body["statusCode"] == 422
    assert body["error"] == "VALIDATION_ERROR"

    db_session.expire_all()
    assert db_session.get(Memory, memory_id).visibility == "private"


def test_unauthenticated_user_cannot_change_privacy(privacy_context):
    client, db_session, memory_id, _, _ = privacy_context

    response = client.patch(
        f"/api/memories/{memory_id}/visibility",
        json={"visibility": "public"},
    )
    body = response.json()
    assert response.status_code == 401
    assert body["statusCode"] == 401
    assert body["error"] == "UNAUTHORIZED"

    db_session.expire_all()
    assert db_session.get(Memory, memory_id).visibility == "private"


def test_not_found_and_soft_deleted_memory_return_404(privacy_context):
    client, db_session, memory_id, owner_token, _ = privacy_context

    missing = client.patch(
        "/api/memories/999999/visibility",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"visibility": "public"},
    )
    assert missing.status_code == 404
    assert missing.json()["statusCode"] == 404
    assert missing.json()["message"] == "Không tìm thấy ký ức"

    memory = db_session.get(Memory, memory_id)
    memory.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.commit()

    deleted_res = client.patch(
        f"/api/memories/{memory_id}/visibility",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"visibility": "public"},
    )
    assert deleted_res.status_code == 404
    assert deleted_res.json()["statusCode"] == 404
    assert deleted_res.json()["message"] == "Không tìm thấy ký ức"
