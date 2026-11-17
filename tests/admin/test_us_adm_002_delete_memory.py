"""US-ADM-002 – Xóa ký ức vi phạm nghiêm trọng."""
import pytest

from app.core.config import settings
from app.modules.admin.models import AdminAction
from app.modules.memories.models import Memory


def _jpeg_bytes(size: int = 128) -> bytes:
    signature = b"\xff\xd8\xffa"
    return signature + b"\x00" * (size - len(signature))


def _delete(ctx, memory_id: int, reason="Vi phạm pháp luật", headers=None):
    return ctx.client.post(
        f"/api/admin/memories/{memory_id}/delete",
        json={"reason": reason} if reason is not None else {},
        headers=headers if headers is not None else ctx.admin_headers,
    )


def test_only_admin_can_delete(ctx):
    memory_id = ctx.public_memory.id
    assert ctx.client.post(f"/api/admin/memories/{memory_id}/delete", json={"reason": "x"}).status_code == 401
    assert _delete(ctx, memory_id, headers=ctx.headers(ctx.owner)).status_code == 403
    assert _delete(ctx, memory_id, headers=ctx.headers(ctx.other)).status_code == 403
    ctx.db.expire_all()
    assert ctx.db.get(Memory, memory_id).deleted_at is None


@pytest.mark.parametrize("reason", [None, "", "   ", "x" * 501])
def test_delete_requires_valid_reason(ctx, reason):
    res = _delete(ctx, ctx.public_memory.id, reason=reason)
    assert res.status_code == 422
    ctx.db.expire_all()
    assert ctx.db.get(Memory, ctx.public_memory.id).deleted_at is None
    assert ctx.db.query(AdminAction).count() == 0


def test_delete_is_soft_and_logged(ctx):
    memory_id = ctx.public_memory.id
    res = _delete(ctx, memory_id, reason="  Vi phạm pháp luật  ")
    assert res.status_code == 200
    assert res.json()["message"] == "Đã xóa ký ức"

    ctx.db.expire_all()
    memory = ctx.db.get(Memory, memory_id)
    assert memory is not None and memory.deleted_at is not None  # dòng vẫn còn (BR-13)

    log = ctx.db.query(AdminAction).one()
    assert (log.admin_id, log.action, log.target_type, log.target_id, log.reason) == (
        ctx.admin.id, "delete_memory", "memory", memory_id, "Vi phạm pháp luật"
    )

    # Nhật ký vẫn hiện được tên ký ức đã xóa
    item = ctx.client.get("/api/admin/actions", headers=ctx.admin_headers).json()["data"]["items"][0]
    assert item["action_label"] == "Xóa ký ức"
    assert item["target_label"] == "Hoàng hôn Hồ Tây"
    assert item["reason"] == "Vi phạm pháp luật"


def test_deleted_memory_disappears_from_every_screen(ctx, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    memory_id = ctx.public_memory.id
    owner_headers = ctx.headers(ctx.owner)

    # Chủ ký ức có ảnh đính kèm và đã đưa ký ức vào một chuyến đi
    upload = ctx.client.post(
        f"/api/memories/{memory_id}/images",
        headers=owner_headers,
        files=[("images", ("a.jpg", _jpeg_bytes(), "image/jpeg"))],
    )
    assert upload.status_code == 200
    image_url = upload.json()["data"][0]["url"]
    trip_id = ctx.client.post("/api/trips", headers=owner_headers, json={"name": "Hà Nội"}).json()["data"]["id"]
    ctx.client.post(f"/api/trips/{trip_id}/memories", headers=owner_headers, json={"memory_ids": [memory_id]})
    assert ctx.client.get(image_url).status_code == 200

    assert _delete(ctx, memory_id).status_code == 200

    # Khách, người khác và cả chủ ký ức đều không còn thấy
    for headers in ({}, ctx.headers(ctx.other), owner_headers):
        assert ctx.client.get(f"/api/memories/{memory_id}", headers=headers).status_code == 404
    assert ctx.client.get(image_url).status_code == 404
    assert memory_id not in [p["id"] for p in ctx.client.get("/api/explore/pins").json()["data"]]
    explore = ctx.client.get("/api/explore/memories").json()["data"]["items"]
    assert memory_id not in [m["id"] for m in explore]
    trip = ctx.client.get(f"/api/trips/{trip_id}", headers=owner_headers).json()["data"]
    assert trip["memory_count"] == 0 and trip["memories"] == []

    # Trang quản trị: biến khỏi danh sách, thống kê giảm
    admin_list = ctx.client.get("/api/admin/memories", headers=ctx.admin_headers).json()["data"]
    assert admin_list["total"] == 0
    stats = ctx.client.get("/api/admin/stats", headers=ctx.admin_headers).json()["data"]
    assert stats["memories"] == 1 and stats["public_memories"] == 0


def test_can_delete_hidden_memory(ctx):
    memory_id = ctx.public_memory.id
    ctx.client.post(f"/api/admin/memories/{memory_id}/hide", json={"reason": "spam"}, headers=ctx.admin_headers)

    assert _delete(ctx, memory_id, reason="tái phạm").status_code == 200
    stats = ctx.client.get("/api/admin/stats", headers=ctx.admin_headers).json()["data"]
    assert stats["hidden_memories"] == 0
    actions = [a.action for a in ctx.db.query(AdminAction).order_by(AdminAction.id)]
    assert actions == ["hide_memory", "delete_memory"]


def test_deleted_memory_cannot_be_deleted_hidden_or_unhidden_again(ctx):
    memory_id = ctx.public_memory.id
    assert _delete(ctx, memory_id).status_code == 200

    assert _delete(ctx, memory_id).status_code == 404
    hide = ctx.client.post(f"/api/admin/memories/{memory_id}/hide", json={"reason": "x"}, headers=ctx.admin_headers)
    assert hide.status_code == 404
    unhide = ctx.client.post(f"/api/admin/memories/{memory_id}/unhide", json={}, headers=ctx.admin_headers)
    assert unhide.status_code == 404
    assert ctx.db.query(AdminAction).count() == 1


def test_cannot_delete_private_or_missing_memory(ctx):
    for memory_id in (ctx.private_memory.id, 99999):
        assert _delete(ctx, memory_id).status_code == 404
    ctx.db.expire_all()
    assert ctx.db.get(Memory, ctx.private_memory.id).deleted_at is None
