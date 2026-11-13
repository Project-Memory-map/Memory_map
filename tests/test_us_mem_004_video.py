"""US-MEM-004 – Đính kèm video vào ký ức (T05B57B)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.modules.accounts.models import User
from app.modules.memories.models import Media, Memory
from app.modules.memories.services.image_media_service import resolve_upload_path

FIFTY_MIB = 50 * 1024 * 1024


@pytest.fixture
def video_context(client: TestClient, db_session, tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")

    owner = User(
        email="video-owner@example.com",
        password_hash=None,
        display_name="Video Owner",
        role="user",
        status="active",
        token_version=0,
    )
    other = User(
        email="video-other@example.com",
        password_hash=None,
        display_name="Other User",
        role="user",
        status="active",
        token_version=0,
    )
    db_session.add_all([owner, other])
    db_session.flush()
    memory = Memory(
        user_id=owner.id,
        title="Video memory",
        content="Test memory",
        memory_date=date(2025, 1, 1),
        place_name="Hanoi",
        latitude=21.028511,
        longitude=105.804817,
        visibility="private",
        status="active",
    )
    db_session.add(memory)
    db_session.commit()

    owner_token = create_access_token(owner.id, owner.token_version)
    other_token = create_access_token(other.id, other.token_version)
    return client, db_session, memory.id, owner_token, other_token


def video_bytes(size: int = 128, *, mov: bool = False) -> bytes:
    header = b"\x00\x00\x00\x14ftypqt  " if mov else b"\x00\x00\x00\x18ftypmp42"
    return header + b"\x00" * (size - len(header))


def upload_video(name: str, content: bytes, mime: str = "video/mp4"):
    return ("video", (name, content, mime))


def post_video(client: TestClient, memory_id: int, token: str, files=(), data=None):
    return client.post(
        f"/api/memories/{memory_id}/video",
        headers={"Authorization": f"Bearer {token}"},
        files=list(files),
        data=data or {},
    )


def test_ac1_uploads_and_streams_mp4_with_range_and_mime(video_context):
    client, db_session, memory_id, owner_token, _ = video_context
    content = video_bytes(30 * 1024 * 1024)
    response = post_video(client, memory_id, owner_token, [upload_video("trip.mp4", content)])

    body = response.json()
    assert response.status_code == 200
    assert body["statusCode"] == 200
    video = body["data"]
    assert video["type"] == "video"
    assert video["mime_type"] == "video/mp4"
    assert video["size_bytes"] == len(content)
    assert urlsplit(video["url"]).path.endswith("/stream")

    stream = client.get(
        video["url"],
        headers={"Authorization": f"Bearer {owner_token}", "Range": "bytes=0-31"},
    )
    assert stream.status_code == 206
    assert stream.headers["content-type"].startswith("video/mp4")
    assert stream.headers["content-range"] == f"bytes 0-31/{len(content)}"
    assert stream.content == content[:32]

    listed = client.get(
        f"/api/memories/{memory_id}/video",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert listed.status_code == 200
    assert listed.json()["statusCode"] == 200
    assert listed.json()["data"]["id"] == video["id"]

    media = db_session.scalar(
        select(Media).where(Media.memory_id == memory_id, Media.media_type == "video")
    )
    assert media is not None
    assert resolve_upload_path(media.file_path).stat().st_size == len(content)


def test_ac2_accepts_video_at_exactly_fifty_mib(video_context):
    client, _, memory_id, owner_token, _ = video_context
    response = post_video(
        client,
        memory_id,
        owner_token,
        [upload_video("boundary.mp4", video_bytes(FIFTY_MIB))],
    )

    body = response.json()
    assert response.status_code == 200
    assert body["statusCode"] == 200
    assert body["data"]["size_bytes"] == FIFTY_MIB


def test_ac3_rejects_video_over_fifty_mib(video_context):
    client, _, memory_id, owner_token, _ = video_context
    response = post_video(
        client,
        memory_id,
        owner_token,
        [upload_video("too-large.mp4", video_bytes(60 * 1024 * 1024))],
    )

    body = response.json()
    assert response.status_code == 400
    assert body["statusCode"] == 400
    assert body["message"] == "Video không được vượt quá 50 MB"


def test_ac4_rejects_second_video_and_multiple_files_in_one_request(video_context):
    client, _, memory_id, owner_token, _ = video_context
    first = post_video(client, memory_id, owner_token, [upload_video("first.mp4", video_bytes())])
    assert first.status_code == 200

    second = post_video(client, memory_id, owner_token, [upload_video("second.mp4", video_bytes())])
    assert second.status_code == 400
    assert second.json()["statusCode"] == 400
    assert second.json()["message"] == "Mỗi ký ức chỉ có 1 video"

    batch = post_video(
        client,
        memory_id,
        owner_token,
        [upload_video("one.mp4", video_bytes()), upload_video("two.mp4", video_bytes())],
    )
    assert batch.status_code == 400
    assert batch.json()["statusCode"] == 400
    assert batch.json()["message"] == "Mỗi ký ức chỉ có 1 video"


def test_video_limit_counts_only_video_media_and_allows_image_coexistence(video_context):
    client, _, memory_id, owner_token, _ = video_context
    image = client.post(
        f"/api/memories/{memory_id}/images",
        headers={"Authorization": f"Bearer {owner_token}"},
        files=[("images", ("photo.jpg", b"\xff\xd8\xff\x00image", "image/jpeg"))],
    )
    assert image.status_code == 200

    response = post_video(client, memory_id, owner_token, [upload_video("memory.mp4", video_bytes())])
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("filename", "content", "mime"),
    [
        ("setup.exe", b"MZ\x00\x01", "application/x-msdownload"),
        ("movie.avi", b"RIFF\x00\x00\x00\x00AVI ", "video/x-msvideo"),
        ("movie.MKV", b"\x1aE\xdf\xa3", "video/x-matroska"),
        ("not-video.mp4", b"plain text", "video/mp4"),
        ("wrong-mime.mp4", b"\x00\x00\x00\x18ftypmp42", "video/quicktime"),
    ],
)
def test_br06_rejects_unsupported_video_format(video_context, filename, content, mime):
    client, _, memory_id, owner_token, _ = video_context
    response = post_video(client, memory_id, owner_token, [upload_video(filename, content, mime)])

    body = response.json()
    assert response.status_code == 400
    assert body["statusCode"] == 400
    assert body["message"] == "Định dạng tệp không được hỗ trợ"


def test_accepts_uppercase_mov_and_owner_can_replace_or_delete(video_context):
    client, db_session, memory_id, owner_token, other_token = video_context
    first = post_video(
        client,
        memory_id,
        owner_token,
        [upload_video("memory.MOV", video_bytes(mov=True), "video/quicktime")],
    )
    assert first.status_code == 200
    old_url = first.json()["data"]["url"]

    denied = post_video(
        client,
        memory_id,
        other_token,
        [upload_video("replacement.mp4", video_bytes())],
        data={"remove_video": "true"},
    )
    assert denied.status_code == 403
    assert denied.json()["statusCode"] == 403

    replaced = post_video(
        client,
        memory_id,
        owner_token,
        [upload_video("replacement.mp4", video_bytes())],
        data={"remove_video": "true"},
    )
    assert replaced.status_code == 200
    assert replaced.json()["data"]["mime_type"] == "video/mp4"
    assert client.get(old_url, headers={"Authorization": f"Bearer {owner_token}"}).status_code == 404

    deleted = post_video(client, memory_id, owner_token, data={"remove_video": "true"})
    assert deleted.status_code == 200
    assert deleted.json()["data"] is None
    assert client.get(replaced.json()["data"]["url"], headers={"Authorization": f"Bearer {owner_token}"}).status_code == 404
    assert db_session.scalar(select(Media).where(Media.memory_id == memory_id, Media.media_type == "video")) is None


def test_private_or_deleted_video_stream_is_not_available_without_owner(video_context):
    client, db_session, memory_id, owner_token, other_token = video_context
    response = post_video(client, memory_id, owner_token, [upload_video("private.mp4", video_bytes())])
    assert response.status_code == 200
    url = response.json()["data"]["url"]

    assert client.get(url).status_code == 404
    assert client.get(url, headers={"Authorization": f"Bearer {other_token}"}).status_code == 404
    assert client.get(url, headers={"Authorization": f"Bearer {owner_token}"}).status_code == 200

    memory = db_session.get(Memory, memory_id)
    memory.visibility = "public"
    memory.status = "hidden"
    db_session.commit()
    assert client.get(url).status_code == 404
    assert client.get(url, headers={"Authorization": f"Bearer {other_token}"}).status_code == 404
    assert client.get(url, headers={"Authorization": f"Bearer {owner_token}"}).status_code == 200

    memory = db_session.get(Memory, memory_id)
    memory.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.commit()
    assert client.get(url, headers={"Authorization": f"Bearer {owner_token}"}).status_code == 404
