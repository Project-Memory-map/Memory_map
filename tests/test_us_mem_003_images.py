"""US-MEM-003 – Đính kèm ảnh vào ký ức (T05B57A)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, sign_media_url, verify_media_signature
from app.modules.accounts.models import User
from app.modules.memories.models import Media, Memory
from app.modules.memories.services.image_media_service import resolve_upload_path

FIVE_MIB = 5 * 1024 * 1024


@pytest.fixture
def image_context(client: TestClient, db_session, tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")

    owner = User(
        email="owner@example.com",
        password_hash=None,
        display_name="Memory Owner",
        role="user",
        status="active",
        token_version=0,
    )
    other = User(
        email="other@example.com",
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
        title="Photo memory",
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


def jpeg_bytes(marker: bytes = b"x", size: int = 64) -> bytes:
    signature = b"\xff\xd8\xff" + marker[:1]
    return signature + b"\x00" * (size - len(signature))


def image_upload(name: str, content: bytes, mime: str = "image/jpeg"):
    return ("images", (name, content, mime))


def attach(client: TestClient, memory_id: int, token: str, files, **form):
    return client.post(
        f"/api/memories/{memory_id}/images",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
        data=form,
    )


def test_ac1_keeps_three_selected_images_in_order_and_persists_them(image_context):
    client, db_session, memory_id, owner_token, _ = image_context
    expected = [jpeg_bytes(b"a", 2 * 1024 * 1024), jpeg_bytes(b"b", 2 * 1024 * 1024), jpeg_bytes(b"c", 2 * 1024 * 1024)]

    response = attach(
        client,
        memory_id,
        owner_token,
        [
            image_upload("third.jpg", expected[0]),
            image_upload("first.jpg", expected[1]),
            image_upload("second.jpg", expected[2]),
        ],
    )

    body = response.json()
    assert response.status_code == 200
    assert body["statusCode"] == 200
    rows = body["data"]
    assert [row["sort_order"] for row in rows] == [0, 1, 2]

    parsed_url = urlsplit(rows[0]["url"])
    qs = parse_qs(parsed_url.query)
    assert verify_media_signature(rows[0]["id"], int(qs["exp"][0]), qs["sig"][0]) is True
    assert sign_media_url(rows[0]["id"]).startswith(f"/api/media/{rows[0]['id']}?exp=")

    listed = client.get(
        f"/api/memories/{memory_id}/images",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert listed.status_code == 200
    assert listed.json()["statusCode"] == 200
    assert [row["id"] for row in listed.json()["data"]] == [row["id"] for row in rows]

    media_rows = db_session.scalars(
        select(Media).where(Media.memory_id == memory_id).order_by(Media.sort_order)
    ).all()
    assert [row.sort_order for row in media_rows] == [0, 1, 2]
    assert [resolve_upload_path(row.file_path).read_bytes() for row in media_rows] == expected


def test_ac2_accepts_ten_images_at_exactly_five_mib_each(image_context):
    client, _, memory_id, owner_token, _ = image_context
    content = jpeg_bytes(b"5", FIVE_MIB)
    response = attach(
        client,
        memory_id,
        owner_token,
        [image_upload(f"image-{index}.jpg", content) for index in range(10)],
    )

    body = response.json()
    assert response.status_code == 200
    assert body["statusCode"] == 200
    assert len(body["data"]) == 10
    assert {row["size_bytes"] for row in body["data"]} == {FIVE_MIB}


def test_ac3_rejects_eleventh_image_and_keeps_existing_ten(image_context):
    client, _, memory_id, owner_token, _ = image_context
    too_many = attach(
        client,
        memory_id,
        owner_token,
        [image_upload(f"batch-{index}.jpg", jpeg_bytes(bytes([index]))) for index in range(11)],
    )
    assert too_many.status_code == 400
    assert too_many.json()["statusCode"] == 400
    assert too_many.json()["message"] == "Mỗi ký ức tối đa 10 ảnh"

    first = attach(
        client,
        memory_id,
        owner_token,
        [image_upload(f"image-{index}.jpg", jpeg_bytes(bytes([index]))) for index in range(10)],
    )
    assert first.status_code == 200

    response = attach(client, memory_id, owner_token, [image_upload("eleventh.jpg", jpeg_bytes())])
    assert response.status_code == 400
    assert response.json()["statusCode"] == 400
    assert response.json()["message"] == "Mỗi ký ức tối đa 10 ảnh"
    listed = client.get(
        f"/api/memories/{memory_id}/images",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert len(listed.json()["data"]) == 10


def test_image_limit_does_not_count_video_media(image_context):
    client, db_session, memory_id, owner_token, _ = image_context
    db_session.add(
        Media(
            memory_id=memory_id,
            media_type="video",
            file_path="videos/existing.mp4",
            thumb_path=None,
            mime_type="video/mp4",
            size_bytes=1024,
            sort_order=0,
        )
    )
    db_session.commit()

    first = attach(
        client,
        memory_id,
        owner_token,
        [image_upload(f"image-{index}.jpg", jpeg_bytes(bytes([index]))) for index in range(9)],
    )
    assert first.status_code == 200
    tenth = attach(client, memory_id, owner_token, [image_upload("tenth.jpg", jpeg_bytes(b"t"))])
    assert tenth.status_code == 200
    assert len(tenth.json()["data"]) == 10


def test_ac4_rejects_image_larger_than_five_mib(image_context):
    client, _, memory_id, owner_token, _ = image_context
    response = attach(
        client,
        memory_id,
        owner_token,
        [image_upload("large.jpg", jpeg_bytes(b"6", 6 * 1024 * 1024))],
    )

    body = response.json()
    assert response.status_code == 400
    assert body["statusCode"] == 400
    assert body["message"] == "Mỗi ảnh không được vượt quá 5 MB"


@pytest.mark.parametrize(
    ("filename", "content", "mime"),
    [
        ("setup.exe", b"MZ\x00\x01", "application/x-msdownload"),
        ("document.pdf", b"%PDF-1.7", "application/pdf"),
        ("clip.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4"),
        ("bad-signature.jpg", b"\x89PNG\r\n\x1a\n", "image/jpeg"),
    ],
)
def test_ac5_rejects_unsupported_extension_mime_or_magic(image_context, filename, content, mime):
    client, _, memory_id, owner_token, _ = image_context
    response = attach(client, memory_id, owner_token, [image_upload(filename, content, mime)])

    body = response.json()
    assert response.status_code == 400
    assert body["statusCode"] == 400
    assert body["message"] == "Định dạng tệp không được hỗ trợ"


def test_only_memory_owner_can_attach_images(image_context):
    client, _, memory_id, _, other_token = image_context
    response = attach(client, memory_id, other_token, [image_upload("secret.jpg", jpeg_bytes())])

    body = response.json()
    assert response.status_code == 403
    assert body["statusCode"] == 403
    assert body["error"] == "FORBIDDEN"


def test_private_and_deleted_memory_images_are_not_available_to_others(image_context):
    client, db_session, memory_id, owner_token, other_token = image_context
    response = attach(client, memory_id, owner_token, [image_upload("private.jpg", jpeg_bytes())])
    assert response.status_code == 200
    media_url = response.json()["data"][0]["url"]
    parsed = urlsplit(media_url)
    assert parse_qs(parsed.query)["sig"]

    assert client.get(f"/api/memories/{memory_id}/images").status_code == 404
    assert client.get(media_url).status_code == 403
    assert client.get(media_url, headers={"Authorization": f"Bearer {other_token}"}).status_code == 403
    assert client.get(media_url, headers={"Authorization": f"Bearer {owner_token}"}).status_code == 200

    memory = db_session.get(Memory, memory_id)
    memory.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.commit()

    assert client.get(media_url, headers={"Authorization": f"Bearer {owner_token}"}).status_code == 404
    assert client.get(
        f"/api/memories/{memory_id}/images",
        headers={"Authorization": f"Bearer {owner_token}"},
    ).status_code == 404
