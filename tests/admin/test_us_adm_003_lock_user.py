"""US-ADM-003 – Khóa và mở khóa tài khoản người dùng."""
import pytest

from app.core.passwords import hash_password
from app.modules.accounts.models import User
from app.modules.admin.models import AdminAction
from app.modules.explore.models import Region
from app.modules.memories.models import Hashtag, MemoryHashtag

PASSWORD = "MatKhau@123"


def _lock(ctx, user_id: int, reason="Spam liên tục", headers=None):
    return ctx.client.post(
        f"/api/admin/users/{user_id}/lock",
        json={"reason": reason} if reason is not None else {},
        headers=headers if headers is not None else ctx.admin_headers,
    )


def _unlock(ctx, user_id: int):
    return ctx.client.post(f"/api/admin/users/{user_id}/unlock", json={}, headers=ctx.admin_headers)


def _login(ctx, email: str):
    return ctx.client.post("/api/auth/login", json={"email": email, "password": PASSWORD})


@pytest.fixture
def community(ctx):
    """Ký ức công khai của chủ có tỉnh/thành, hashtag và mật khẩu đăng nhập được."""
    region = Region(name="Hà Nội", slug="ha-noi", level="city")
    tag = Hashtag(name="hoanghon")
    ctx.db.add_all([region, tag])
    ctx.db.flush()
    ctx.public_memory.region_id = region.id
    ctx.db.add(MemoryHashtag(memory_id=ctx.public_memory.id, hashtag_id=tag.id))
    ctx.owner.password_hash = hash_password(PASSWORD)
    ctx.db.commit()
    return region


def _community_view(ctx, region_id: int) -> dict:
    """Những gì khách thấy về ký ức công khai của chủ trên các màn hình cộng đồng."""
    memory_id = ctx.public_memory.id
    regions = ctx.client.get("/api/explore/regions").json()["data"]
    hashtags = ctx.client.get("/api/explore/hashtags").json()["data"]
    return {
        "detail": ctx.client.get(f"/api/memories/{memory_id}").status_code,
        "pin": memory_id in [p["id"] for p in ctx.client.get("/api/explore/pins").json()["data"]],
        "explore": memory_id in [m["id"] for m in ctx.client.get("/api/explore/memories").json()["data"]["items"]],
        "region_count": next(r["count"] for r in regions if r["id"] == region_id),
        "hashtag": "hoanghon" in [h["name"] for h in hashtags],
    }


VISIBLE = {"detail": 200, "pin": True, "explore": True, "region_count": 1, "hashtag": True}
HIDDEN = {"detail": 404, "pin": False, "explore": False, "region_count": 0, "hashtag": False}


# ----- Danh sách tài khoản

def test_list_users_with_search_status_and_memory_count(ctx):
    res = ctx.client.get("/api/admin/users", headers=ctx.admin_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 3 and data["pages"] == 1
    owner = next(u for u in data["items"] if u["id"] == ctx.owner.id)
    assert owner == {
        "id": ctx.owner.id,
        "display_name": "Chủ Ký Ức",
        "email": "owner@example.com",
        "role": "user",
        "status": "active",
        "memory_count": 2,
        "created_at": owner["created_at"],
    }

    by_email = ctx.client.get("/api/admin/users", params={"q": "OTHER@"}, headers=ctx.admin_headers)
    assert [u["id"] for u in by_email.json()["data"]["items"]] == [ctx.other.id]
    by_name = ctx.client.get("/api/admin/users", params={"q": "quản trị"}, headers=ctx.admin_headers)
    assert [u["id"] for u in by_name.json()["data"]["items"]] == [ctx.admin.id]
    wildcard = ctx.client.get("/api/admin/users", params={"q": "%"}, headers=ctx.admin_headers)
    assert wildcard.json()["data"]["total"] == 0

    _lock(ctx, ctx.owner.id)
    locked = ctx.client.get("/api/admin/users", params={"status": "locked"}, headers=ctx.admin_headers)
    assert [u["id"] for u in locked.json()["data"]["items"]] == [ctx.owner.id]
    bad = ctx.client.get("/api/admin/users", params={"status": "banned"}, headers=ctx.admin_headers)
    assert bad.status_code == 422


def test_memory_count_ignores_deleted_memories(ctx):
    ctx.client.post(
        f"/api/admin/memories/{ctx.public_memory.id}/delete", json={"reason": "x"}, headers=ctx.admin_headers
    )
    items = ctx.client.get("/api/admin/users", headers=ctx.admin_headers).json()["data"]["items"]
    assert next(u for u in items if u["id"] == ctx.owner.id)["memory_count"] == 1


# ----- Quyền và dữ liệu gửi lên

def test_only_admin_can_manage_users(ctx):
    assert ctx.client.get("/api/admin/users").status_code == 401
    assert ctx.client.get("/api/admin/users", headers=ctx.headers(ctx.other)).status_code == 403
    assert _lock(ctx, ctx.owner.id, headers=ctx.headers(ctx.other)).status_code == 403
    unlock = ctx.client.post(f"/api/admin/users/{ctx.owner.id}/unlock", json={}, headers=ctx.headers(ctx.other))
    assert unlock.status_code == 403
    ctx.db.expire_all()
    assert ctx.db.get(User, ctx.owner.id).status == "active"


@pytest.mark.parametrize("reason", [None, "", "   ", "x" * 501])
def test_lock_requires_valid_reason(ctx, reason):
    assert _lock(ctx, ctx.owner.id, reason=reason).status_code == 422
    ctx.db.expire_all()
    assert ctx.db.get(User, ctx.owner.id).status == "active"
    assert ctx.db.query(AdminAction).count() == 0


def test_admin_cannot_lock_self(ctx):
    res = _lock(ctx, ctx.admin.id, reason="thử")
    assert res.status_code == 422
    assert res.json()["message"] == "Bạn không thể khóa chính tài khoản của mình"
    ctx.db.expire_all()
    assert ctx.db.get(User, ctx.admin.id).status == "active"
    assert ctx.db.query(AdminAction).count() == 0


def test_lock_or_unlock_missing_user_returns_404(ctx):
    assert _lock(ctx, 99999).status_code == 404
    assert _unlock(ctx, 99999).status_code == 404


# ----- Khóa

def test_lock_signs_out_blocks_login_and_logs(ctx, community):
    old_headers = ctx.headers(ctx.owner)
    assert ctx.client.get("/api/auth/me", headers=old_headers).status_code == 200
    assert _login(ctx, "owner@example.com").status_code == 200

    res = _lock(ctx, ctx.owner.id, reason="  Spam liên tục  ")
    assert res.status_code == 200
    assert res.json()["data"] == {"id": ctx.owner.id, "status": "locked"}

    # Phiên đang mở bị đăng xuất ngay, không đăng nhập lại được
    assert ctx.client.get("/api/auth/me", headers=old_headers).status_code == 401
    login = _login(ctx, "owner@example.com")
    assert login.status_code == 403
    assert login.json()["message"] == "Tài khoản của bạn đã bị khóa"

    log = ctx.db.query(AdminAction).one()
    assert (log.admin_id, log.action, log.target_type, log.target_id, log.reason) == (
        ctx.admin.id, "lock_user", "user", ctx.owner.id, "Spam liên tục"
    )
    item = ctx.client.get("/api/admin/actions", headers=ctx.admin_headers).json()["data"]["items"][0]
    assert item["action_label"] == "Khóa tài khoản"
    assert item["target_type"] == "user" and item["target_label"] == "Chủ Ký Ức"

    stats = ctx.client.get("/api/admin/stats", headers=ctx.admin_headers).json()["data"]
    assert stats["locked_users"] == 1

    assert _lock(ctx, ctx.owner.id).status_code == 409


def test_lock_hides_public_memories_from_community(ctx, community):
    assert _community_view(ctx, community.id) == VISIBLE

    _lock(ctx, ctx.owner.id)
    assert _community_view(ctx, community.id) == HIDDEN

    # Trang quản trị vẫn thấy ký ức, kèm trạng thái tác giả bị khóa
    item = ctx.client.get("/api/admin/memories", headers=ctx.admin_headers).json()["data"]["items"][0]
    assert item["id"] == ctx.public_memory.id
    assert item["status"] == "active" and item["author"]["status"] == "locked"


def test_admin_can_lock_another_admin(ctx):
    ctx.other.role = "admin"
    ctx.db.commit()
    assert _lock(ctx, ctx.other.id).status_code == 200


# ----- Mở khóa

def test_unlock_restores_login_and_memories(ctx, community):
    _lock(ctx, ctx.owner.id)

    res = _unlock(ctx, ctx.owner.id)
    assert res.status_code == 200
    assert res.json()["data"] == {"id": ctx.owner.id, "status": "active"}

    # Đăng nhập lại được; ký ức công khai hiện lại nguyên trạng
    login = _login(ctx, "owner@example.com")
    assert login.status_code == 200
    token = login.json()["data"]["access_token"]
    assert ctx.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert _community_view(ctx, community.id) == VISIBLE

    actions = [a.action for a in ctx.db.query(AdminAction).order_by(AdminAction.id)]
    assert actions == ["lock_user", "unlock_user"]

    assert _unlock(ctx, ctx.owner.id).status_code == 409


def test_unlock_keeps_memory_hidden_by_admin_hidden(ctx):
    """Mở khóa tài khoản không bỏ ẩn những ký ức admin đã ẩn riêng."""
    memory_id = ctx.public_memory.id
    ctx.client.post(f"/api/admin/memories/{memory_id}/hide", json={"reason": "spam"}, headers=ctx.admin_headers)
    _lock(ctx, ctx.owner.id)
    _unlock(ctx, ctx.owner.id)
    assert ctx.client.get(f"/api/memories/{memory_id}").status_code == 404
