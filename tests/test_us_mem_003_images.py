from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_access_token
from app.main import create_app
from app.modules.accounts.models import User
from app.modules.memories.models import Media, Memory
from app.modules.memories.services.image_media_service import resolve_upload_path

JWT_SECRET = "test-signing-secret-with-enough-entropy"
FIVE_MIB = 5 * 1024 * 1024


@pytest.fixture
def image_client(tmp_path):
    configuration = Settings(
        jwt_secret_key=JWT_SECRET,
        database_path=str(tmp_path / "images.sqlite3"),
    )
    app = create_app(configuration)
    object.__setattr__(configuration, "upload_dir", tmp_path / "uploads")

    with Session(app.state.database_engine, expire_on_commit=False) as db:
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
        db.add_all([owner, other])
        db.flush()
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
        db.add(memory)
        db.commit()
        owner_token = create_access_token(owner, configuration)
        other_token = create_access_token(other, configuration)
        memory_id = memory.id

    with TestClient(app) as client:
        yield client, app, memory_id, owner_token, other_token


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


def test_ac1_keeps_three_selected_images_in_order_and_persists_them(image_client):
    client, app, memory_id, owner_token, _ = image_client
    expected = [jpeg_bytes(b"a"), jpeg_bytes(b"b"), jpeg_bytes(b"c")]

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

    assert response.status_code == 200
    rows = response.json()["data"]
    assert [row["sort_order"] for row in rows] == [0, 1, 2]
    listed = client.get(f"/api/memories/{memory_id}/images", headers={"Authorization": f"Bearer {owner_token}"})
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()["data"]] == [row["id"] for row in rows]

    with Session(app.state.database_engine) as db:
        media_rows = db.scalars(
            select(Media).where(Media.memory_id == memory_id).order_by(Media.sort_order)
        ).all()
        assert [row.sort_order for row in media_rows] == [0, 1, 2]
        assert [resolve_upload_path(row.file_path, app.state.settings).read_bytes() for row in media_rows] == expected


def test_ac2_accepts_ten_images_at_exactly_five_mib_each(image_client):
    client, _, memory_id, owner_token, _ = image_client
    content = jpeg_bytes(b"5", FIVE_MIB)
    response = attach(
        client,
        memory_id,
        owner_token,
        [image_upload(f"image-{index}.jpg", content) for index in range(10)],
    )

    assert response.status_code == 200
    assert len(response.json()["data"]) == 10
    assert {row["size_bytes"] for row in response.json()["data"]} == {FIVE_MIB}


def test_ac3_rejects_eleventh_image_and_keeps_existing_ten(image_client):
    client, _, memory_id, owner_token, _ = image_client
    too_many = attach(
        client,
        memory_id,
        owner_token,
        [image_upload(f"batch-{index}.jpg", jpeg_bytes(bytes([index]))) for index in range(11)],
    )
    assert too_many.status_code == 400
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
    assert response.json()["message"] == "Mỗi ký ức tối đa 10 ảnh"
    listed = client.get(f"/api/memories/{memory_id}/images", headers={"Authorization": f"Bearer {owner_token}"})
    assert len(listed.json()["data"]) == 10


def test_image_limit_does_not_count_video_media(image_client):
    client, app, memory_id, owner_token, _ = image_client
    with Session(app.state.database_engine) as db:
        db.add(
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
        db.commit()

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


def test_ac4_rejects_image_larger_than_five_mib(image_client):
    client, _, memory_id, owner_token, _ = image_client
    response = attach(
        client,
        memory_id,
        owner_token,
        [image_upload("large.jpg", jpeg_bytes(b"6", FIVE_MIB + 1))],
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Mỗi ảnh không được vượt quá 5 MB"


@pytest.mark.parametrize(
    ("filename", "content", "mime"),
    [
        ("setup.exe", b"MZ\x00\x01", "application/x-msdownload"),
        ("document.pdf", b"%PDF-1.7", "application/pdf"),
        ("clip.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4"),
        ("bad-signature.jpg", b"\x89PNG\r\n\x1a\n", "image/jpeg"),
    ],
)
def test_ac5_rejects_unsupported_extension_mime_or_magic(image_client, filename, content, mime):
    client, _, memory_id, owner_token, _ = image_client
    response = attach(client, memory_id, owner_token, [image_upload(filename, content, mime)])

    assert response.status_code == 400
    assert response.json()["message"] == "Định dạng tệp không được hỗ trợ"


def test_only_memory_owner_can_attach_images(image_client):
    client, _, memory_id, _, other_token = image_client
    response = attach(client, memory_id, other_token, [image_upload("secret.jpg", jpeg_bytes())])

    assert response.status_code == 403


def test_private_and_deleted_memory_images_are_not_available_to_others(image_client):
    client, app, memory_id, owner_token, other_token = image_client
    response = attach(client, memory_id, owner_token, [image_upload("private.jpg", jpeg_bytes())])
    assert response.status_code == 200
    media_url = response.json()["data"][0]["url"]
    parsed = urlsplit(media_url)
    assert parse_qs(parsed.query)["sig"]

    assert client.get(f"/api/memories/{memory_id}/images").status_code == 404
    assert client.get(media_url).status_code == 404
    assert client.get(media_url, headers={"Authorization": f"Bearer {other_token}"}).status_code == 404
    assert client.get(media_url, headers={"Authorization": f"Bearer {owner_token}"}).status_code == 200

    with Session(app.state.database_engine) as db:
        memory = db.get(Memory, memory_id)
        memory.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()

    assert client.get(media_url, headers={"Authorization": f"Bearer {owner_token}"}).status_code == 404
    assert client.get(
        f"/api/memories/{memory_id}/images",
        headers={"Authorization": f"Bearer {owner_token}"},
    ).status_code == 404
