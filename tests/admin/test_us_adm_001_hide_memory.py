"""US-ADM-001 – Ẩn và bỏ ẩn ký ức công khai vi phạm."""
from app.modules.admin.models import AdminAction
from app.modules.memories.models import Memory


def test_non_admin_and_guest_are_rejected(ctx):
    url = f"/api/admin/memories/{ctx.public_memory.id}/hide"
    assert ctx.client.post(url, json={"reason": "x"}).status_code == 401
    assert ctx.client.post(url, json={"reason": "x"}, headers=ctx.headers(ctx.other)).status_code == 403
    assert ctx.client.get("/api/admin/memories", headers=ctx.headers(ctx.other)).status_code == 403
    assert ctx.client.get("/api/admin/stats", headers=ctx.headers(ctx.other)).status_code == 403
    # AC4: thông báo đúng câu chữ
    res = ctx.client.get("/api/admin/memories", headers=ctx.headers(ctx.other))
    assert res.json()["message"] == "Bạn không có quyền truy cập"


def test_list_shows_only_public_memories_with_search_and_status(ctx):
    res = ctx.client.get("/api/admin/memories", headers=ctx.admin_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert [item["id"] for item in data["items"]] == [ctx.public_memory.id]
    item = data["items"][0]
    assert item["status"] == "active"
    assert item["author"] == {"id": ctx.owner.id, "display_name": "Chủ Ký Ức", "status": "active"}
    assert data["total"] == 1 and data["pages"] == 1

    by_author = ctx.client.get("/api/admin/memories", params={"q": "chủ ký"}, headers=ctx.admin_headers)
    assert by_author.json()["data"]["total"] == 1
    none = ctx.client.get("/api/admin/memories", params={"q": "không-có"}, headers=ctx.admin_headers)
    assert none.json()["data"]["total"] == 0
    hidden = ctx.client.get("/api/admin/memories", params={"status": "hidden"}, headers=ctx.admin_headers)
    assert hidden.json()["data"]["total"] == 0
    # "%" và "_" là ký tự thường, không phải ký tự đại diện của LIKE
    for wildcard in ("%", "_"):
        res = ctx.client.get("/api/admin/memories", params={"q": wildcard}, headers=ctx.admin_headers)
        assert res.json()["data"]["total"] == 0, wildcard
    bad = ctx.client.get("/api/admin/memories", params={"status": "deleted"}, headers=ctx.admin_headers)
    assert bad.status_code == 422


def test_hide_requires_reason(ctx):
    url = f"/api/admin/memories/{ctx.public_memory.id}/hide"
    for body in ({}, {"reason": "   "}, {"reason": "x" * 501}):
        res = ctx.client.post(url, json=body, headers=ctx.admin_headers)
        assert res.status_code == 422, body
    ctx.db.expire_all()
    assert ctx.db.get(Memory, ctx.public_memory.id).status == "active"
    assert ctx.db.query(AdminAction).count() == 0


def test_hide_removes_from_community_but_owner_still_sees_it(ctx):
    memory_id = ctx.public_memory.id
    res = ctx.client.post(
        f"/api/admin/memories/{memory_id}/hide", json={"reason": "  Nội dung phản cảm  "}, headers=ctx.admin_headers
    )
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "hidden"

    # Khách và người khác không còn thấy
    assert ctx.client.get(f"/api/memories/{memory_id}").status_code == 404
    pins = ctx.client.get("/api/explore/pins").json()["data"]
    assert memory_id not in [p["id"] for p in pins]
    explore = ctx.client.get("/api/explore/memories").json()["data"]["items"]
    assert memory_id not in [m["id"] for m in explore]

    # Chủ ký ức vẫn thấy, kèm trạng thái đã bị ẩn
    owner_view = ctx.client.get(f"/api/memories/{memory_id}", headers=ctx.headers(ctx.owner))
    assert owner_view.status_code == 200
    assert owner_view.json()["data"]["hidden_by_admin"] is True

    log = ctx.db.query(AdminAction).one()
    assert (log.admin_id, log.action, log.target_type, log.target_id, log.reason) == (
        ctx.admin.id, "hide_memory", "memory", memory_id, "Nội dung phản cảm"
    )

    # Ẩn lần hai báo trùng
    again = ctx.client.post(f"/api/admin/memories/{memory_id}/hide", json={"reason": "x"}, headers=ctx.admin_headers)
    assert again.status_code == 409


def test_unhide_restores_memory_and_logs(ctx):
    memory_id = ctx.public_memory.id
    ctx.client.post(f"/api/admin/memories/{memory_id}/hide", json={"reason": "spam"}, headers=ctx.admin_headers)

    res = ctx.client.post(f"/api/admin/memories/{memory_id}/unhide", json={}, headers=ctx.admin_headers)
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "active"
    assert ctx.client.get(f"/api/memories/{memory_id}").status_code == 200

    actions = [a.action for a in ctx.db.query(AdminAction).order_by(AdminAction.id)]
    assert actions == ["hide_memory", "unhide_memory"]

    again = ctx.client.post(f"/api/admin/memories/{memory_id}/unhide", json={}, headers=ctx.admin_headers)
    assert again.status_code == 409


def test_cannot_act_on_private_or_missing_memory(ctx):
    for memory_id in (ctx.private_memory.id, 99999):
        res = ctx.client.post(
            f"/api/admin/memories/{memory_id}/hide", json={"reason": "x"}, headers=ctx.admin_headers
        )
        assert res.status_code == 404


def test_stats_and_action_log(ctx):
    ctx.client.post(
        f"/api/admin/memories/{ctx.public_memory.id}/hide", json={"reason": "spam"}, headers=ctx.admin_headers
    )
    stats = ctx.client.get("/api/admin/stats", headers=ctx.admin_headers).json()["data"]
    assert stats == {
        "users": 3,
        "locked_users": 0,
        "memories": 2,
        "public_memories": 1,
        "hidden_memories": 1,
        "new_memories_7d": 2,
    }

    log = ctx.client.get("/api/admin/actions", headers=ctx.admin_headers).json()["data"]
    assert log["total"] == 1
    item = log["items"][0]
    assert item["action"] == "hide_memory"
    assert item["action_label"] == "Ẩn ký ức"
    assert item["target_label"] == "Hoàng hôn Hồ Tây"
    assert item["admin"]["display_name"] == "Quản Trị"
    assert item["reason"] == "spam"

    filtered = ctx.client.get("/api/admin/actions", params={"action": "lock_user"}, headers=ctx.admin_headers)
    assert filtered.json()["data"]["total"] == 0
    bad = ctx.client.get("/api/admin/actions", params={"action": "drop"}, headers=ctx.admin_headers)
    assert bad.status_code == 422
