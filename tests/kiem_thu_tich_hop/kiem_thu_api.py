"""Kiểm thử tích hợp 108 AC qua HTTP trên server thật (MySQL, có trigger).

Cần chạy trước:  python tests/kiem_thu_tich_hop/chuan_bi_db.py
                 python tests/kiem_thu_tich_hop/chay_server.py      (cửa sổ khác)
Rồi:             python tests/kiem_thu_tich_hop/kiem_thu_api.py

Kết quả: ĐẠT / LỖI / CHẶN (chức năng chưa có hoặc cần dịch vụ ngoài) / UI (kiểm ở kiem_thu_giao_dien.mjs).
Ghi ra ket_qua/api.json để tao_bao_cao.mjs gộp vào báo cáo.
"""
import json
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import httpx
import pymysql

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402

BASE = "http://127.0.0.1:8010"
TEST_DB = "ban_do_ky_uc_kiemthu"
OUT = HERE / "ket_qua" / "api.json"
RUN = uuid.uuid4().hex[:6]
results: dict[str, dict] = {}
MEM: dict = {}  # dữ liệu dùng chung giữa các ca


def db():
    return pymysql.connect(host=settings.db_host, port=settings.db_port, user=settings.db_user,
                           password=settings.db_password, database=TEST_DB, charset="utf8mb4", autocommit=True)


def sql(query, *args):
    with db() as conn, conn.cursor() as cur:
        cur.execute(query, args)
        return cur.fetchall()


def record(ac, ok, detail, status=None):
    status = status or ("ĐẠT" if ok else "LỖI")
    results[ac] = {"status": status, "detail": detail}
    print(f"{status:5} {ac:16} {detail}")


def blocked(ac, detail):
    record(ac, False, detail, "CHẶN")


def ui(ac, detail):
    record(ac, False, detail, "UI")


def safe(ac):
    """Bọc từng ca: lỗi bất ngờ trong kịch bản ghi thành LỖI kèm thông tin, không dừng cả bộ."""
    def wrap(fn):
        try:
            fn()
        except AssertionError as exc:
            record(ac, False, f"Sai khác: {exc}")
        except Exception as exc:  # noqa: BLE001
            record(ac, False, f"Lỗi khi chạy: {type(exc).__name__}: {exc}")
        return fn
    return wrap


c = httpx.Client(base_url=BASE, timeout=120, follow_redirects=False)


def msg(res):
    try:
        return res.json().get("message")
    except Exception:  # noqa: BLE001
        return res.text[:120]


def email(tag):
    return f"{tag}.{RUN}@example.com"


def register(tag, name="Người thử", password="Matkhau123"):
    res = c.post("/api/auth/register", json={"display_name": name, "email": email(tag), "password": password})
    assert res.status_code in (200, 201), f"đăng ký {tag}: {res.status_code} {msg(res)}"
    data = res.json()["data"]
    return {"id": data["user"]["id"], "token": data["access_token"], "email": email(tag), "password": password}


def H(user):
    return {"Authorization": f"Bearer {user['token']}"}


def make_admin(user):
    sql("UPDATE users SET role='admin' WHERE id=%s", user["id"])


def create_memory(user, title="Ký ức thử", lat=21.0287, lng=105.8524, place="Hồ Gươm, Hà Nội",
                  day="2025-10-12", content="Nội dung", visibility=None):
    form = {"title": title, "content": content, "place_name": place, "latitude": str(lat),
            "longitude": str(lng), "memory_date": day}
    if visibility:
        form["visibility"] = visibility
    res = c.post("/api/memories", data=form, headers=H(user))
    assert res.status_code == 201, f"tạo ký ức: {res.status_code} {msg(res)}"
    return res.json()["data"]


def jpeg(size):
    head = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00"
    return head + b"\x00" * (size - len(head))


def mp4(size):
    head = b"\x00\x00\x00\x18ftypmp42"
    return head + b"\x00" * (size - len(head))


MB = 1024 * 1024

# ======================================================================== EP1 – Tài khoản
an = None


@safe("US-ACC-001 AC1")
def _():
    global an
    res = c.post("/api/auth/register", json={"display_name": "An", "email": email("an"), "password": "Matkhau123"})
    body = res.json()
    role = sql("SELECT role FROM users WHERE email=%s", email("an"))
    ok = res.status_code in (200, 201) and body["data"].get("access_token") and role and role[0][0] == "user"
    an = {"id": body["data"]["user"]["id"], "token": body["data"]["access_token"], "email": email("an"), "password": "Matkhau123"}
    record("US-ACC-001 AC1", ok and body["message"] == "Đăng ký thành công",
           f"{res.status_code}, message='{body['message']}', role={role[0][0] if role else None}, có token đăng nhập ngay")


@safe("US-ACC-001 AC2")
def _():
    res = c.post("/api/auth/register", json={"display_name": "B", "email": email("ac2"), "password": "Abcdef12"})
    record("US-ACC-001 AC2", res.status_code in (200, 201), f"Mật khẩu 8 ký tự 'Abcdef12' → {res.status_code} '{msg(res)}'")


@safe("US-ACC-001 AC3")
def _():
    res = c.post("/api/auth/register", json={"display_name": "B", "email": email("ac3"), "password": "Abc12"})
    created = sql("SELECT COUNT(*) FROM users WHERE email=%s", email("ac3"))[0][0]
    expected = "Mật khẩu phải có ít nhất 8 ký tự gồm chữ và số"
    record("US-ACC-001 AC3", res.status_code >= 400 and msg(res) == expected and created == 0,
           f"{res.status_code} '{msg(res)}', số tài khoản tạo ra={created}")


@safe("US-ACC-001 AC4")
def _():
    res = c.post("/api/auth/register", json={"display_name": "An 2", "email": email("an"), "password": "Matkhau123"})
    count = sql("SELECT COUNT(*) FROM users WHERE email=%s", email("an"))[0][0]
    record("US-ACC-001 AC4", res.status_code == 409 and msg(res) == "Email này đã được đăng ký" and count == 1,
           f"{res.status_code} '{msg(res)}', số tài khoản cùng email={count}")


@safe("US-ACC-001 AC5")
def _():
    before = sql("SELECT COUNT(*) FROM users")[0][0]
    res = c.post("/api/auth/register", json={"display_name": "B", "email": "an@", "password": "Matkhau123"})
    after = sql("SELECT COUNT(*) FROM users")[0][0]
    record("US-ACC-001 AC5", res.status_code == 422 and msg(res) == "Email không hợp lệ" and before == after,
           f"{res.status_code} '{msg(res)}'")


@safe("US-ACC-002 AC1")
def _():
    res = c.post("/api/auth/login", json={"email": an["email"], "password": "Matkhau123"})
    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {res.json()['data']['access_token']}"})
    record("US-ACC-002 AC1", res.status_code == 200 and me.json()["data"]["display_name"] == "An",
           f"{res.status_code} '{msg(res)}', /me display_name='{me.json()['data']['display_name']}'")


@safe("US-ACC-002 AC2")
def _():
    res = c.post("/api/auth/login", json={"email": an["email"].upper(), "password": "Matkhau123"})
    record("US-ACC-002 AC2", res.status_code == 200, f"Email viết hoa → {res.status_code} '{msg(res)}'")


@safe("US-ACC-002 AC3")
def _():
    wrong_pw = c.post("/api/auth/login", json={"email": an["email"], "password": "SaiMatKhau1"})
    wrong_mail = c.post("/api/auth/login", json={"email": email("khongco"), "password": "SaiMatKhau1"})
    same = msg(wrong_pw) == msg(wrong_mail) == "Email hoặc mật khẩu không đúng"
    record("US-ACC-002 AC3", wrong_pw.status_code == 401 and same,
           f"sai mật khẩu: {wrong_pw.status_code} '{msg(wrong_pw)}'; email không tồn tại: '{msg(wrong_mail)}' (giống nhau={same})")


@safe("US-ACC-002 AC4")
def _():
    u = register("khoa")
    sql("UPDATE users SET status='locked' WHERE id=%s", u["id"])
    res = c.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
    record("US-ACC-002 AC4", res.status_code == 403 and msg(res) == "Tài khoản của bạn đã bị khóa",
           f"{res.status_code} '{msg(res)}'")


@safe("US-ACC-002 AC5")
def _():
    u = register("sai5")
    codes = [c.post("/api/auth/login", json={"email": u["email"], "password": "SaiMatKhau1"}).status_code for _ in range(5)]
    res = c.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
    expected = "Bạn đã nhập sai quá nhiều lần, vui lòng thử lại sau 15 phút"
    record("US-ACC-002 AC5", res.status_code == 429 and msg(res) == expected,
           f"5 lần sai: {codes}; lần 6 đúng mật khẩu → {res.status_code} '{msg(res)}'")


from urllib.parse import parse_qs, unquote_plus, urlsplit  # noqa: E402


def needs_config(ac, detail):
    record(ac, False, detail, "CẦN CẤU HÌNH")


@safe("US-ACC-003")
def _():
    prov = c.get("/api/auth/providers").json()["data"]
    login = c.get("/api/auth/google/login")
    for ac, what in (("US-ACC-003 AC1", "tạo tài khoản mới"), ("US-ACC-003 AC2", "liên kết vào tài khoản cùng email"),
                     ("US-ACC-003 AC4", "chặn tài khoản bị khóa")):
        needs_config(ac, f"Đã có API (/api/auth/google/login, /callback). Cần GOOGLE_CLIENT_ID/SECRET thật trong .env để đi hết luồng "
                         f"với Google; providers={prov}, /login → {login.status_code}. Phần '{what}' đã kiểm bằng Google giả lập: "
                         "tests/accounts/test_us_acc_003_google.py ĐẠT.")
    cancel = c.get("/api/auth/google/callback", params={"error": "access_denied", "state": "x"})
    loc = unquote_plus(cancel.headers.get("location", ""))
    record("US-ACC-003 AC3", cancel.status_code == 302 and "/accounts/login.html" in loc and "Đăng nhập Google chưa hoàn tất" in loc,
           f"callback error=access_denied → {cancel.status_code}, chuyển tới '{loc[:110]}'")


@safe("US-ACC-004")
def _():
    prov = c.get("/api/auth/providers").json()["data"]
    for ac in ("US-ACC-004 AC1", "US-ACC-004 AC2"):
        needs_config(ac, f"Cần FACEBOOK_APP_ID/SECRET thật trong .env để đi hết luồng OAuth (providers={prov}). "
                         "Đã kiểm bằng Facebook giả lập: tests/accounts/test_us_acc_004_facebook.py ĐẠT.")
    cancel = c.get("/api/auth/facebook/callback", params={"error": "access_denied", "state": "x"})
    loc = unquote_plus(cancel.headers.get("location", ""))
    record("US-ACC-004 AC3", cancel.status_code in (302, 303, 307) and "login" in loc and "Đăng nhập Facebook chưa hoàn tất" in loc,
           f"callback error=access_denied → {cancel.status_code}, chuyển tới '{loc[:120]}'")


SENT = "Nếu email tồn tại, chúng tôi đã gửi hướng dẫn đặt lại mật khẩu"


def forgot(email_addr):
    res = c.post("/api/auth/forgot-password", json={"email": email_addr})
    data = res.json().get("data") or {}
    token = parse_qs(urlsplit(data["dev_reset_url"]).query)["token"][0] if data.get("dev_reset_url") else None
    return res, token


@safe("US-ACC-005 AC1")
def _():
    u = register("quenmk1")
    res, token = forgot(u["email"].upper())
    row = sql("SELECT TIMESTAMPDIFF(MINUTE, created_at, expires_at) FROM password_reset_tokens WHERE user_id=%s", u["id"])
    record("US-ACC-005 AC1", res.status_code == 200 and msg(res) == SENT and bool(token) and bool(row) and row[0][0] == 30,
           f"{res.status_code} '{msg(res)}'; tạo link hiệu lực {row[0][0] if row else None} phút "
           "(máy chưa cấu hình SMTP nên chế độ dev hiện link trên trang thay vì gửi mail; có SMTP thì gửi email – xem test_us_acc_005)")
    MEM["reset"] = (u, token)


@safe("US-ACC-005 AC2")
def _():
    before = sql("SELECT COUNT(*) FROM password_reset_tokens")[0][0]
    res, token = forgot(email("khong.co"))
    after = sql("SELECT COUNT(*) FROM password_reset_tokens")[0][0]
    record("US-ACC-005 AC2", res.status_code == 200 and msg(res) == SENT and token is None and before == after,
           f"{res.status_code} '{msg(res)}' (giống hệt AC1); không tạo link/email nào={before == after}")


@safe("US-ACC-005 AC3")
def _():
    u, token = MEM["reset"]
    ok = c.post("/api/auth/reset-password", json={"token": token, "new_password": "Matkhaumoi9"})
    new_login = c.post("/api/auth/login", json={"email": u["email"], "password": "Matkhaumoi9"}).status_code
    old_login = c.post("/api/auth/login", json={"email": u["email"], "password": u["password"]}).status_code
    reuse = c.post("/api/auth/reset-password", json={"token": token, "new_password": "Matkhaumoi10"})
    record("US-ACC-005 AC3", ok.status_code == 200 and new_login == 200 and old_login == 401 and reuse.status_code == 400,
           f"đặt lại → {ok.status_code} '{msg(ok)}'; mk mới={new_login}, mk cũ={old_login}; dùng lại link → {reuse.status_code} '{msg(reuse)}'")


@safe("US-ACC-005 AC4")
def _():
    u = register("quenmk4")
    _, token = forgot(u["email"])
    sql("UPDATE password_reset_tokens SET created_at=UTC_TIMESTAMP() - INTERVAL 31 MINUTE, expires_at=UTC_TIMESTAMP() - INTERVAL 1 MINUTE WHERE user_id=%s", u["id"])
    opened = c.post("/api/auth/validate-reset-token", json={"token": token})
    submit = c.post("/api/auth/reset-password", json={"token": token, "new_password": "Matkhaumoi9"})
    still = c.post("/api/auth/login", json={"email": u["email"], "password": u["password"]}).status_code
    expected = "Liên kết đã hết hạn, vui lòng yêu cầu lại"
    record("US-ACC-005 AC4", msg(opened) == expected and msg(submit) == expected and still == 200,
           f"mở link gửi 31 phút trước → '{msg(opened)}'; cố đặt lại → '{msg(submit)}'; mật khẩu không đổi={still == 200}")


@safe("US-ACC-006 AC1")
def _():
    u = register("hoso", name="An")
    m = create_memory(u, title="Hồ sơ công khai", visibility="public")
    res = c.patch("/api/users/me", json={"display_name": "Dread"}, headers=H(u))
    shown = c.get(f"/api/memories/{m['id']}").json()["data"]["author"]["display_name"]
    MEM["hoso"] = u
    record("US-ACC-006 AC1", res.status_code == 200 and res.json()["data"]["display_name"] == "Dread" and shown == "Dread",
           f"{res.status_code} '{msg(res)}'; ký ức công khai hiện tên '{shown}'")


@safe("US-ACC-006 AC2")
def _():
    res = c.patch("/api/users/me", json={"display_name": "a" * 100}, headers=H(MEM["hoso"]))
    record("US-ACC-006 AC2", res.status_code == 200, f"tên 100 ký tự → {res.status_code} '{msg(res)}'")


@safe("US-ACC-006 AC3")
def _():
    res = c.patch("/api/users/me", json={"display_name": "a" * 101}, headers=H(MEM["hoso"]))
    name = sql("SELECT CHAR_LENGTH(display_name) FROM users WHERE id=%s", MEM["hoso"]["id"])[0][0]
    record("US-ACC-006 AC3", res.status_code == 422 and msg(res) == "Tên hiển thị tối đa 100 ký tự" and name == 100,
           f"tên 101 ký tự → {res.status_code} '{msg(res)}', tên đang lưu vẫn {name} ký tự")


@safe("US-ACC-006 AC4")
def _():
    res = c.post("/api/users/me/avatar", files={"avatar": ("big.jpg", jpeg(6 * MB), "image/jpeg")}, headers=H(MEM["hoso"]))
    record("US-ACC-006 AC4", res.status_code == 400 and msg(res) == "Ảnh không được vượt quá 5 MB", f"ảnh 6 MB → {res.status_code} '{msg(res)}'")


@safe("US-ACC-006 AC5")
def _():
    res = c.post("/api/users/me/avatar", files={"avatar": ("baocao.pdf", b"%PDF-1.7 ...", "application/pdf")}, headers=H(MEM["hoso"]))
    ok = c.post("/api/users/me/avatar", files={"avatar": ("me.jpg", jpeg(3000), "image/jpeg")}, headers=H(MEM["hoso"]))
    url = ok.json()["data"]["avatar_url"] if ok.status_code == 200 else None
    served = c.get(url).status_code if url else None
    record("US-ACC-006 AC5", res.status_code == 400 and msg(res) == "Định dạng tệp không được hỗ trợ" and served == 200,
           f"baocao.pdf → {res.status_code} '{msg(res)}'; (đối chứng) ảnh .jpg hợp lệ → {ok.status_code}, mở {url} → {served}")


@safe("US-ACC-007 AC1")
def _():
    u = register("doimk")
    res = c.post("/api/auth/change-password", json={"current_password": u["password"], "new_password": "Matkhaumoi9"}, headers=H(u))
    new_login = c.post("/api/auth/login", json={"email": u["email"], "password": "Matkhaumoi9"})
    old_login = c.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
    record("US-ACC-007 AC1", res.status_code == 200 and msg(res) == "Đổi mật khẩu thành công" and new_login.status_code == 200 and old_login.status_code == 401,
           f"{res.status_code} '{msg(res)}'; đăng nhập mk mới={new_login.status_code}, mk cũ={old_login.status_code}")


@safe("US-ACC-007 AC2")
def _():
    u = register("doimk2")
    res = c.post("/api/auth/change-password", json={"current_password": "SaiMatKhau1", "new_password": "Matkhaumoi9"}, headers=H(u))
    still = c.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
    record("US-ACC-007 AC2", res.status_code >= 400 and msg(res) == "Mật khẩu hiện tại không đúng" and still.status_code == 200,
           f"{res.status_code} '{msg(res)}'; mk cũ vẫn đăng nhập={still.status_code}")


@safe("US-ACC-007 AC3")
def _():
    u = register("doimk3")
    res = c.post("/api/auth/change-password", json={"current_password": u["password"], "new_password": "abc"}, headers=H(u))
    still = c.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
    record("US-ACC-007 AC3", res.status_code == 422 and msg(res) == "Mật khẩu phải có ít nhất 8 ký tự gồm chữ và số" and still.status_code == 200,
           f"{res.status_code} '{msg(res)}'")


@safe("US-ACC-007 AC4")
def _():
    u = register("social")
    sql("UPDATE users SET password_hash=NULL WHERE id=%s", u["id"])
    # Giả lập người dùng chỉ đăng nhập Google/Facebook: trigger đã tăng token_version nên cấp lại token đúng phiên bản
    u["token"] = create_access_token(u["id"], sql("SELECT token_version FROM users WHERE id=%s", u["id"])[0][0])
    res = c.post("/api/auth/change-password", json={"new_password": "Matkhaumoi9"}, headers=H(u))
    login = c.post("/api/auth/login", json={"email": u["email"], "password": "Matkhaumoi9"})
    record("US-ACC-007 AC4", res.status_code == 200 and login.status_code == 200,
           f"Tạo mật khẩu khi password_hash rỗng → {res.status_code} '{msg(res)}'; đăng nhập bằng mk mới={login.status_code}")


@safe("US-ACC-008 AC1")
def _():
    u = register("dangxuat")
    out = c.post("/api/auth/logout", headers=H(u))
    me = c.get("/api/auth/me", headers=H(u))
    ui("US-ACC-008 AC1", f"Kiểm ở trình duyệt. API: logout → {out.status_code} '{msg(out)}'; token cũ gọi /me → {me.status_code} "
                         "(đúng thiết kế BR-20: đăng xuất xóa JWT ở trình duyệt, máy chủ không thu hồi)")

ui("US-ACC-008 AC2", "Kiểm ở trình duyệt (mở lại trang hồ sơ sau khi đăng xuất)")
ui("US-ACC-008 AC3", "Kiểm ở trình duyệt (nút Back)")

# ======================================================================== EP2 – Ký ức
owner = register("chu", name="Chủ Ký Ức")
other = register("khac", name="Người Khác")


@safe("US-MEM-001 AC1")
def _():
    # Gọi Nominatim thật qua máy chủ (cần Internet)
    res = c.get("/api/geocode", params={"q": "Hồ Gươm"}, headers=H(owner))
    places = res.json().get("data") or []
    assert places, f"tìm 'Hồ Gươm' → {res.status_code} '{msg(res)}', không có kết quả"
    first = places[0]
    m = create_memory(owner, title="Chiều thu Hà Nội", lat=first["latitude"], lng=first["longitude"], place=first["name"], day="2025-10-12")
    pin = {p["id"]: p for p in c.get("/api/memories/mine/pins", headers=H(owner)).json()["data"]}.get(m["id"])
    near = bool(pin) and abs(pin["latitude"] - 21.0287) < 0.01 and abs(pin["longitude"] - 105.8524) < 0.01
    record("US-MEM-001 AC1", near and m["visibility"] == "private" and str(m["memory_date"]) == "2025-10-12",
           f"kết quả đầu '{first['name']}' ({first['latitude']:.4f}, {first['longitude']:.4f}); ghim đúng Hồ Gươm={near}, "
           f"chế độ={m['visibility']}, ngày={m['memory_date']}, khu vực={m['region']['name'] if m['region'] else None}")


@safe("US-MEM-001 AC2")
def _():
    text = ("Câu chuyện dài. " * 1300)[:20000]
    m = create_memory(owner, title="Câu chuyện dài", content=text)
    stored = sql("SELECT CHAR_LENGTH(content) FROM memories WHERE id=%s", m["id"])[0][0]
    detail = c.get(f"/api/memories/{m['id']}", headers=H(owner)).json()["data"]["content"]
    record("US-MEM-001 AC2", stored == len(text.strip()) and detail == text.strip(),
           f"Gửi {len(text)} ký tự, DB lưu {stored} ký tự, chi tiết trả về {len(detail)} ký tự")


@safe("US-MEM-001 AC3")
def _():
    before = sql("SELECT COUNT(*) FROM memories")[0][0]
    res = c.get("/api/geocode", params={"q": "xyzxyz"}, headers=H(owner))
    after = sql("SELECT COUNT(*) FROM memories")[0][0]
    expected = "Không tìm thấy địa điểm. Hãy thử tên khác hoặc chọn trực tiếp trên bản đồ"
    record("US-MEM-001 AC3", res.status_code == 200 and res.json()["data"] == [] and msg(res) == expected and before == after,
           f"{res.status_code} '{msg(res)}'; không có ghim nào được tạo={before == after}")


@safe("US-MEM-001 AC4")
def _():
    before = sql("SELECT COUNT(*) FROM memories WHERE user_id=%s", owner["id"])[0][0]
    res = c.post("/api/memories", headers=H(owner), data={"title": "  ", "place_name": "Hồ Gươm", "latitude": "21.0287",
                                                          "longitude": "105.8524", "memory_date": "2025-10-12"})
    after = sql("SELECT COUNT(*) FROM memories WHERE user_id=%s", owner["id"])[0][0]
    record("US-MEM-001 AC4", res.status_code == 422 and msg(res) == "Vui lòng nhập tiêu đề" and before == after,
           f"{res.status_code} '{msg(res)}'")


@safe("US-MEM-001 AC5")
def _():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    res = c.post("/api/memories", headers=H(owner), data={"title": "Tương lai", "place_name": "Hồ Gươm", "latitude": "21.0287",
                                                          "longitude": "105.8524", "memory_date": tomorrow})
    record("US-MEM-001 AC5", res.status_code == 422 and msg(res) == "Ngày không được ở tương lai",
           f"Ngày {tomorrow} → {res.status_code} '{msg(res)}'")


@safe("US-MEM-002 AC1")
def _():
    m = create_memory(owner, title="Con suối không tên", lat=11.9404, lng=108.4583, place="Suối, Đà Lạt")
    pins = c.get("/api/memories/mine/pins", headers=H(owner)).json()["data"]
    pin = next(p for p in pins if p["id"] == m["id"])
    record("US-MEM-002 AC1", (pin["latitude"], pin["longitude"]) == (11.9404, 108.4583) and m["visibility"] == "private",
           f"Ghim ở ({pin['latitude']}, {pin['longitude']}), visibility={m['visibility']}")


@safe("US-MEM-002 AC2")
def _():
    m = create_memory(owner, title="Tháp Eiffel", lat=48.8584, lng=2.2945, place="Paris")
    record("US-MEM-002 AC2", m["region"] is None, f"Tạo được (id={m['id']}), region={m['region']}")


@safe("US-MEM-002 AC3")
def _():
    before = sql("SELECT COUNT(*) FROM memories")[0][0]
    res = c.post("/api/memories", data={"title": "Khách", "place_name": "X", "latitude": "21", "longitude": "105", "memory_date": "2025-01-01"})
    after = sql("SELECT COUNT(*) FROM memories")[0][0]
    record("US-MEM-002 AC3", res.status_code == 401 and before == after,
           f"Khách gọi POST /api/memories → {res.status_code} '{msg(res)}' (giao diện kiểm riêng ở trình duyệt)")




@safe("US-MEM-003 AC1")
def _():
    m = create_memory(owner, title="Chiều thu Hà Nội", visibility="public")
    MEM["three"] = m["id"]
    files = [("images", (f"anh{i}.jpg", jpeg(2 * MB), "image/jpeg")) for i in (1, 2, 3)]
    up = c.post(f"/api/memories/{m['id']}/images", files=files, headers=H(owner))
    sizes = [r[0] for r in sql("SELECT size_bytes FROM media WHERE memory_id=%s ORDER BY sort_order", m["id"])]
    detail = c.get(f"/api/memories/{m['id']}", headers=H(owner)).json()["data"]
    urls = [x["url"] for x in detail["media"]]
    loads = [c.get(u).status_code for u in urls]
    MEM["detail_media_status"] = loads
    record("US-MEM-003 AC1", up.status_code == 200 and len(sizes) == 3 and loads == [200, 200, 200],
           f"upload → {up.status_code}, DB có {len(sizes)} ảnh theo thứ tự; chi tiết trả {len(urls)} URL dạng '{urls[0] if urls else ''}', "
           f"mở ảnh từ trang chi tiết → {loads}")


@safe("US-MEM-003 AC2")
def _():
    m = create_memory(owner, title="Mười ảnh")
    files = [("images", (f"a{i}.jpg", jpeg(5 * MB), "image/jpeg")) for i in range(10)]
    up = c.post(f"/api/memories/{m['id']}/images", files=files, headers=H(owner))
    MEM["ten"] = m["id"]
    record("US-MEM-003 AC2", up.status_code == 200 and len(up.json()["data"]) == 10, f"10 ảnh × 5 MB → {up.status_code} '{msg(up)}'")


@safe("US-MEM-003 AC3")
def _():
    up = c.post(f"/api/memories/{MEM['ten']}/images", files=[("images", ("a11.jpg", jpeg(1000), "image/jpeg"))], headers=H(owner))
    count = sql("SELECT COUNT(*) FROM media WHERE memory_id=%s", MEM["ten"])[0][0]
    record("US-MEM-003 AC3", up.status_code >= 400 and msg(up) == "Mỗi ký ức tối đa 10 ảnh" and count == 10,
           f"{up.status_code} '{msg(up)}', còn {count} ảnh")


@safe("US-MEM-003 AC4")
def _():
    m = create_memory(owner, title="Ảnh 6MB")
    up = c.post(f"/api/memories/{m['id']}/images", files=[("images", ("big.jpg", jpeg(6 * MB), "image/jpeg"))], headers=H(owner))
    record("US-MEM-003 AC4", up.status_code >= 400 and msg(up) == "Mỗi ảnh không được vượt quá 5 MB", f"{up.status_code} '{msg(up)}'")


@safe("US-MEM-003 AC5")
def _():
    m = create_memory(owner, title="exe")
    up = c.post(f"/api/memories/{m['id']}/images", files=[("images", ("setup.exe", b"MZ" + b"\x00" * 500, "application/octet-stream"))], headers=H(owner))
    record("US-MEM-003 AC5", up.status_code >= 400 and msg(up) == "Định dạng tệp không được hỗ trợ", f"{up.status_code} '{msg(up)}'")


@safe("US-MEM-004 AC1")
def _():
    m = create_memory(owner, title="Video 30MB")
    MEM["video"] = m["id"]
    up = c.post(f"/api/memories/{m['id']}/video", files=[("video", ("v.mp4", mp4(30 * MB), "video/mp4"))], headers=H(owner))
    api_url = up.json()["data"]["url"] if up.status_code == 200 else None
    play = c.get(api_url, headers={**H(owner), "Range": "bytes=0-1023"}).status_code if api_url else None
    detail = c.get(f"/api/memories/{m['id']}", headers=H(owner)).json()["data"]
    vids = [x for x in detail["media"] if x["type"] == "video"]
    detail_play = c.get(vids[0]["url"], headers=H(owner)).status_code if vids else None
    record("US-MEM-004 AC1", up.status_code == 200 and play in (200, 206) and detail_play in (200, 206),
           f"upload → {up.status_code}; URL do API video trả phát được={play}; URL ở trang chi tiết '{vids[0]['url'] if vids else None}' → {detail_play}")


@safe("US-MEM-004 AC2")
def _():
    m = create_memory(owner, title="Video 50MB")
    up = c.post(f"/api/memories/{m['id']}/video", files=[("video", ("v.mp4", mp4(50 * MB), "video/mp4"))], headers=H(owner))
    record("US-MEM-004 AC2", up.status_code == 200, f"Đúng 50 MB → {up.status_code} '{msg(up)}'")


@safe("US-MEM-004 AC3")
def _():
    m = create_memory(owner, title="Video 60MB")
    up = c.post(f"/api/memories/{m['id']}/video", files=[("video", ("v.mp4", mp4(60 * MB), "video/mp4"))], headers=H(owner))
    record("US-MEM-004 AC3", up.status_code >= 400 and msg(up) == "Video không được vượt quá 50 MB", f"{up.status_code} '{msg(up)}'")


@safe("US-MEM-004 AC4")
def _():
    up = c.post(f"/api/memories/{MEM['video']}/video", files=[("video", ("v2.mp4", mp4(1 * MB), "video/mp4"))], headers=H(owner))
    count = sql("SELECT COUNT(*) FROM media WHERE memory_id=%s AND media_type='video'", MEM["video"])[0][0]
    record("US-MEM-004 AC4", up.status_code >= 400 and msg(up) == "Mỗi ký ức chỉ có 1 video" and count == 1,
           f"{up.status_code} '{msg(up)}', còn {count} video")


@safe("US-MEM-005 AC1")
def _():
    mid = MEM["three"]
    c.post(f"/api/memories/{mid}/hashtags", json={"hashtags": ["hanoi"]}, headers=H(owner))
    d = c.get(f"/api/memories/{mid}", headers=H(owner)).json()["data"]
    imgs = [x for x in d["media"] if x["type"] == "image"]
    ok = d["title"] == "Chiều thu Hà Nội" and str(d["memory_date"]) == "2025-10-12" and d["place_name"] and len(imgs) == 3 \
        and d["hashtags"] == ["hanoi"] and d["is_owner"] is True and MEM.get("detail_media_status") == [200, 200, 200]
    record("US-MEM-005 AC1", ok, f"tiêu đề/ngày/địa điểm/hashtag đúng, is_owner={d['is_owner']}, 3 ảnh nhưng mở ảnh → {MEM.get('detail_media_status')}")


@safe("US-MEM-005 AC2")
def _():
    d = c.get(f"/api/memories/{MEM['three']}", headers=H(other)).json()["data"]
    record("US-MEM-005 AC2", d["author"]["display_name"] == "Chủ Ký Ức" and d["is_owner"] is False and "email" not in d["author"],
           f"tác giả='{d['author']['display_name']}', is_owner={d['is_owner']}, khóa của author={sorted(d['author'])}")


@safe("US-MEM-005 AC3")
def _():
    priv = create_memory(owner, title="Bí mật")
    res = c.get(f"/api/memories/{priv['id']}", headers=H(other))
    missing = c.get("/api/memories/99999999", headers=H(other))
    same = res.status_code == missing.status_code and msg(res) == msg(missing)
    record("US-MEM-005 AC3", res.status_code == 404 and msg(res) == "Không tìm thấy ký ức" and same,
           f"ký ức riêng tư người khác → {res.status_code} '{msg(res)}'; id không tồn tại → {missing.status_code} '{msg(missing)}'")


@safe("US-MEM-005 AC4")
def _():
    a = register("adm_mem5")
    make_admin(a)
    a["token"] = c.post("/api/auth/login", json={"email": a["email"], "password": a["password"]}).json()["data"]["access_token"]
    m = create_memory(owner, title="Bị ẩn MEM-005", visibility="public")
    c.post(f"/api/admin/memories/{m['id']}/hide", json={"reason": "Thử MEM-005"}, headers=H(a))
    own = c.get(f"/api/memories/{m['id']}", headers=H(owner))
    oth = c.get(f"/api/memories/{m['id']}", headers=H(other))
    guest = c.get(f"/api/memories/{m['id']}")
    record("US-MEM-005 AC4", own.status_code == 200 and own.json()["data"]["hidden_by_admin"] is True and oth.status_code == 404 and guest.status_code == 404,
           f"chủ → {own.status_code} hidden_by_admin={own.json()['data'].get('hidden_by_admin')}; người khác → {oth.status_code}; khách → {guest.status_code} "
           "(chữ 'Đã bị quản trị viên ẩn' kiểm ở trình duyệt)")


MEM6 = {}


@safe("US-MEM-006 AC1")
def _():
    m = create_memory(owner, title="Tiêu đề cũ")
    up = c.post(f"/api/memories/{m['id']}/images", files=[("images", (f"x{i}.jpg", jpeg(1000 + i), "image/jpeg")) for i in range(3)], headers=H(owner)).json()["data"]
    before = sql("SELECT updated_at FROM memories WHERE id=%s", m["id"])[0][0]
    time.sleep(1.1)
    e = c.patch(f"/api/memories/{m['id']}", data={"title": "Tiêu đề mới"}, headers=H(owner))
    img = c.post(f"/api/memories/{m['id']}/images", data={"remove_media_ids": str(up[0]["id"])},
                 files=[("images", ("moi.jpg", jpeg(2000), "image/jpeg"))], headers=H(owner))
    d = c.get(f"/api/memories/{m['id']}", headers=H(owner)).json()["data"]
    after = sql("SELECT updated_at FROM memories WHERE id=%s", m["id"])[0][0]
    n = len([x for x in d["media"] if x["type"] == "image"])
    record("US-MEM-006 AC1", e.status_code == 200 and img.status_code == 200 and d["title"] == "Tiêu đề mới" and n == 3 and after > before,
           f"sửa tiêu đề → {e.status_code}; thêm 1 bỏ 1 ảnh → {img.status_code}; còn {n} ảnh; updated_at {before} → {after}")


@safe("US-MEM-006 AC2")
def _():
    m = create_memory(owner, title="Đổi địa điểm", lat=21.0287, lng=105.8524, place="Hà Nội")
    e = c.patch(f"/api/memories/{m['id']}", data={"place_name": "Đà Lạt", "latitude": "11.9404", "longitude": "108.4583"}, headers=H(owner))
    d = e.json()["data"]
    region = d.get("region")
    record("US-MEM-006 AC2", e.status_code == 200 and (d["latitude"], d["longitude"]) == (11.9404, 108.4583) and region and "Lâm Đồng" in region["name"],
           f"ghim chuyển tới ({d['latitude']}, {d['longitude']}); khu vực sau khi đổi={region} (mong đợi Lâm Đồng)")


@safe("US-MEM-006 AC3")
def _():
    m = create_memory(owner, title="Của chủ")
    e = c.patch(f"/api/memories/{m['id']}", data={"title": "Bị sửa"}, headers=H(other))
    title = sql("SELECT title FROM memories WHERE id=%s", m["id"])[0][0]
    record("US-MEM-006 AC3", e.status_code == 403 and msg(e) == "Bạn không có quyền sửa ký ức này" and title == "Của chủ",
           f"{e.status_code} '{msg(e)}', tiêu đề vẫn '{title}'")


@safe("US-MEM-006 AC4")
def _():
    m = create_memory(owner, title="Giữ nguyên")
    e = c.patch(f"/api/memories/{m['id']}", data={"title": "   "}, headers=H(owner))
    title = sql("SELECT title FROM memories WHERE id=%s", m["id"])[0][0]
    record("US-MEM-006 AC4", e.status_code == 422 and msg(e) == "Vui lòng nhập tiêu đề" and title == "Giữ nguyên", f"{e.status_code} '{msg(e)}'")


@safe("US-MEM-007 AC1")
def _():
    m = create_memory(owner, title="Sẽ xóa", visibility="public")
    up = c.post(f"/api/memories/{m['id']}/images", files=[("images", ("x.jpg", jpeg(1000), "image/jpeg"))], headers=H(owner)).json()["data"]
    c.post(f"/api/memories/{m['id']}/hashtags", json={"hashtags": ["xoa"]}, headers=H(owner))
    img_url = up[0]["url"]
    d = c.delete(f"/api/memories/{m['id']}", headers=H(owner))
    mine = [x["id"] for x in c.get("/api/memories/mine", headers=H(owner)).json()["data"]["items"]]
    pins = [x["id"] for x in c.get("/api/memories/mine/pins", headers=H(owner)).json()["data"]]
    img = c.get(img_url, headers=H(owner)).status_code
    record("US-MEM-007 AC1", d.status_code == 200 and m["id"] not in mine and m["id"] not in pins and img == 404,
           f"xóa → {d.status_code}; còn trong danh sách={m['id'] in mine}, trên bản đồ={m['id'] in pins}; mở ảnh → {img}")


ui("US-MEM-007 AC2", "Kiểm ở trình duyệt (nút Hủy ở hộp xác nhận)")


@safe("US-MEM-007 AC3")
def _():
    ms = [create_memory(owner, title=f"Đà Lạt {i}", day=f"2025-10-1{i}") for i in range(3)]
    trip = c.post("/api/trips", json={"name": "Đà Lạt tháng 10", "memory_ids": [m["id"] for m in ms]}, headers=H(owner)).json()["data"]
    c.delete(f"/api/memories/{ms[0]['id']}", headers=H(owner))
    t = c.get(f"/api/trips/{trip['id']}", headers=H(owner)).json()["data"]
    record("US-MEM-007 AC3", t["memory_count"] == 2, f"chuyến đi còn {t['memory_count']} ký ức")


@safe("US-MEM-007 AC4")
def _():
    m = create_memory(owner, title="Không được xóa")
    d = c.delete(f"/api/memories/{m['id']}", headers=H(other))
    deleted = sql("SELECT deleted_at FROM memories WHERE id=%s", m["id"])[0][0]
    record("US-MEM-007 AC4", d.status_code == 403 and deleted is None, f"{d.status_code} '{msg(d)}', deleted_at={deleted}")


@safe("US-MEM-008 AC1")
def _():
    m = create_memory(owner, title="Sắp công khai", lat=10.7769, lng=106.7009, place="Sài Gòn")
    up = c.post(f"/api/memories/{m['id']}/images", files=[("images", ("x.jpg", jpeg(1000), "image/jpeg"))], headers=H(owner)).json()["data"]
    v = c.patch(f"/api/memories/{m['id']}/visibility", json={"visibility": "public"}, headers=H(owner))
    pins = [p["id"] for p in c.get("/api/explore/pins", params={"south": 10, "west": 106, "north": 11, "east": 107}).json()["data"]]
    guest = c.get(f"/api/memories/{m['id']}")
    img = c.get(up[0]["url"]).status_code
    MEM["pub"] = (m["id"], up[0]["url"])
    record("US-MEM-008 AC1", v.status_code == 200 and m["id"] in pins and guest.status_code == 200 and img == 200,
           f"đổi → {v.status_code}; có trên bản đồ công khai={m['id'] in pins}; khách xem chi tiết → {guest.status_code}; khách mở ảnh → {img}")


@safe("US-MEM-008 AC2")
def _():
    mid, url = MEM["pub"]
    v = c.patch(f"/api/memories/{mid}/visibility", json={"visibility": "private"}, headers=H(owner))
    pins = [p["id"] for p in c.get("/api/explore/pins").json()["data"]]
    img = c.get(url, headers=H(other))
    record("US-MEM-008 AC2", v.status_code == 200 and mid not in pins and img.status_code == 403,
           f"đổi → {v.status_code}; còn trên bản đồ={mid in pins}; người khác mở ảnh → {img.status_code} '{msg(img)}'")


@safe("US-MEM-008 AC3")
def _():
    m = create_memory(owner, title="Không đổi được")
    v = c.patch(f"/api/memories/{m['id']}/visibility", json={"visibility": "public"}, headers=H(other))
    vis = sql("SELECT visibility FROM memories WHERE id=%s", m["id"])[0][0]
    record("US-MEM-008 AC3", v.status_code == 403 and vis == "private", f"{v.status_code} '{msg(v)}', visibility={vis}")


@safe("US-MEM-009 AC1")
def _():
    ms = [create_memory(owner, title=f"Ngày {d}", day=f"2025-10-{d}") for d in (12, 10, 11)]
    t = c.post("/api/trips", json={"name": "Đà Lạt tháng 10", "memory_ids": [m["id"] for m in ms]}, headers=H(owner)).json()["data"]
    t = c.get(f"/api/trips/{t['id']}", headers=H(owner)).json()["data"]
    days = [str(x["memory_date"]) for x in t["memories"]]
    record("US-MEM-009 AC1", days == ["2025-10-10", "2025-10-11", "2025-10-12"], f"thứ tự hiển thị {days}")


@safe("US-MEM-009 AC2")
def _():
    a = create_memory(owner, title="Tạo trước", day="2025-10-11")
    time.sleep(1.1)
    b = create_memory(owner, title="Tạo sau", day="2025-10-11")
    t = c.post("/api/trips", json={"name": "Cùng ngày", "memory_ids": [b["id"], a["id"]]}, headers=H(owner)).json()["data"]
    t = c.get(f"/api/trips/{t['id']}", headers=H(owner)).json()["data"]
    titles = [x["title"] for x in t["memories"]]
    record("US-MEM-009 AC2", titles == ["Tạo trước", "Tạo sau"], f"thứ tự {titles}")


@safe("US-MEM-009 AC3")
def _():
    m = create_memory(other, title="Của người khác")
    t = c.post("/api/trips", json={"name": "Của tôi"}, headers=H(owner)).json()["data"]
    r = c.post(f"/api/trips/{t['id']}/memories", json={"memory_ids": [m["id"]]}, headers=H(owner))
    record("US-MEM-009 AC3", r.status_code == 403 and msg(r) == "Chỉ thêm được ký ức của bạn", f"{r.status_code} '{msg(r)}'")


@safe("US-MEM-009 AC4")
def _():
    before = sql("SELECT COUNT(*) FROM trips WHERE user_id=%s", owner["id"])[0][0]
    r = c.post("/api/trips", json={"name": "  "}, headers=H(owner))
    after = sql("SELECT COUNT(*) FROM trips WHERE user_id=%s", owner["id"])[0][0]
    record("US-MEM-009 AC4", r.status_code == 422 and msg(r) == "Vui lòng nhập tên chuyến đi" and before == after, f"{r.status_code} '{msg(r)}'")


@safe("US-MEM-009 AC5")
def _():
    ms = [create_memory(owner, title=f"T{i}", day=f"2025-10-1{i}") for i in range(3)]
    t = c.post("/api/trips", json={"name": "Đà Lạt tháng 10", "memory_ids": [m["id"] for m in ms]}, headers=H(owner)).json()["data"]
    ren = c.patch(f"/api/trips/{t['id']}", json={"name": "Đà Lạt mùa thu"}, headers=H(owner))
    rm = c.delete(f"/api/trips/{t['id']}/memories/{ms[0]['id']}", headers=H(owner))
    still = c.get(f"/api/memories/{ms[0]['id']}", headers=H(owner)).status_code
    dl = c.delete(f"/api/trips/{t['id']}", headers=H(owner))
    left = [c.get(f"/api/memories/{m['id']}", headers=H(owner)).status_code for m in ms]
    record("US-MEM-009 AC5", ren.json()["data"]["name"] == "Đà Lạt mùa thu" and rm.status_code == 200 and still == 200 and dl.status_code == 200 and left == [200] * 3,
           f"đổi tên → '{ren.json()['data']['name']}'; bỏ ký ức → {rm.status_code} (ký ức vẫn còn {still}); xóa chuyến → {dl.status_code}; ký ức còn {left}")


@safe("US-MEM-010 AC1")
def _():
    m = create_memory(owner, title="Hashtag")
    r = c.post(f"/api/memories/{m['id']}/hashtags", json={"hashtags": ["#dalat", "#phuot"]}, headers=H(owner))
    d = c.get(f"/api/memories/{m['id']}", headers=H(owner)).json()["data"]
    record("US-MEM-010 AC1", r.status_code == 200 and sorted(d["hashtags"]) == ["dalat", "phuot"], f"{r.status_code}, chi tiết có {d['hashtags']}")


@safe("US-MEM-010 AC2")
def _():
    m = create_memory(owner, title="Hashtag 2")
    r = c.post(f"/api/memories/{m['id']}/hashtags", json={"hashtags": ["#DaLat"]}, headers=H(owner))
    n = sql("SELECT COUNT(*) FROM hashtags WHERE name='dalat'")[0][0]
    record("US-MEM-010 AC2", r.status_code == 200 and n == 1, f"{r.status_code}; số hashtag 'dalat' trong DB = {n}")


@safe("US-MEM-010 AC3")
def _():
    m = create_memory(owner, title="Hashtag 3")
    r = c.post(f"/api/memories/{m['id']}/hashtags", json={"hashtags": ["#đà lạt!"]}, headers=H(owner))
    expected = "Hashtag chỉ gồm chữ, số, dấu gạch dưới (tối đa 30 ký tự)"
    record("US-MEM-010 AC3", r.status_code >= 400 and msg(r) == expected, f"{r.status_code} '{msg(r)}'")


@safe("US-MEM-010 AC4")
def _():
    m = create_memory(owner, title="Hashtag 4")
    c.post(f"/api/memories/{m['id']}/hashtags", json={"hashtags": [f"tag{i}" for i in range(10)]}, headers=H(owner))
    r = c.post(f"/api/memories/{m['id']}/hashtags", json={"hashtags": ["tag10"]}, headers=H(owner))
    n = sql("SELECT COUNT(*) FROM memory_hashtags WHERE memory_id=%s", m["id"])[0][0]
    record("US-MEM-010 AC4", r.status_code >= 400 and msg(r) == "Mỗi ký ức tối đa 10 hashtag" and n == 10, f"{r.status_code} '{msg(r)}', còn {n} hashtag")


# ======================================================================== EP3 – Khám phá
def region_id(name):
    return sql("SELECT id FROM regions WHERE name=%s", name)[0][0]


# Vùng thử riêng ngoài Việt Nam để đếm chính xác (giữa Thái Bình Dương)
BOX = {"south": -11, "west": -161, "north": -9, "east": -159}


@safe("US-EXP-001 AC1")
def _():
    u = register("exp1", name="Tác giả EXP")
    pub = [create_memory(u, title=f"Công khai {i}", lat=-10 + i * 0.01, lng=-160, place="Đảo", visibility="public")["id"] for i in range(20)]
    priv = [create_memory(u, title=f"Riêng {i}", lat=-10.5, lng=-160.5, place="Đảo")["id"] for i in range(5)]
    MEM["exp_pub"] = pub
    pins = [p["id"] for p in c.get("/api/explore/pins", params=BOX).json()["data"]]
    record("US-EXP-001 AC1", sorted(pins) == sorted(pub) and not set(priv) & set(pins), f"khách thấy {len(pins)} ghim (mong 20), lẫn riêng tư={bool(set(priv) & set(pins))}")


@safe("US-EXP-001 AC2")
def _():
    r = c.get("/api/explore/memories", params={"south": -60, "west": -40, "north": -59, "east": -39})
    pins = c.get("/api/explore/pins", params={"south": -60, "west": -40, "north": -59, "east": -39})
    record("US-EXP-001 AC2", msg(r) == "Chưa có ký ức công khai trong khu vực này" and pins.json()["data"] == [],
           f"danh sách vùng trống → '{msg(r)}', ghim={pins.json()['data']} (thông báo trên bản đồ kiểm ở trình duyệt)")


@safe("US-EXP-001 AC3")
def _():
    item = c.get("/api/explore/memories", params=BOX).json()["data"]["items"][0]
    d = c.get(f"/api/memories/{item['id']}").json()["data"]
    leaked = [k for k in ("email",) if k in item["author"] or k in d["author"] or "@example.com" in json.dumps(d)]
    record("US-EXP-001 AC3", not leaked, f"author danh sách={sorted(item['author'])}, author chi tiết={sorted(d['author'])}")


@safe("US-EXP-001 AC4")
def _():
    a = register("adm_exp")
    make_admin(a)
    a["token"] = c.post("/api/auth/login", json={"email": a["email"], "password": a["password"]}).json()["data"]["access_token"]
    MEM["admin"] = a
    target = MEM["exp_pub"][0]
    c.post(f"/api/admin/memories/{target}/hide", json={"reason": "Thử EXP-001"}, headers=H(a))
    pins = [p["id"] for p in c.get("/api/explore/pins", params=BOX).json()["data"]]
    record("US-EXP-001 AC4", target not in pins and len(pins) == 19, f"sau khi ẩn: còn {len(pins)} ghim, ký ức ẩn còn hiện={target in pins}")


@safe("US-EXP-002 AC1")
def _():
    u = register("exp2", name="Tác giả hashtag")
    tagged = []
    for i in range(20):
        m = create_memory(u, title=f"H{i}", lat=-20 + i * 0.01, lng=-150, place="Đảo", visibility="public")
        if i < 8:
            c.post(f"/api/memories/{m['id']}/hashtags", json={"hashtags": [f"dalat{RUN}"]}, headers=H(u))
            tagged.append(m["id"])
        elif i < 10:
            c.post(f"/api/memories/{m['id']}/hashtags", json={"hashtags": [f"phuot{RUN}"]}, headers=H(u))
            MEM.setdefault("phuot", []).append(m["id"])
    MEM["dalat"] = tagged
    lst = c.get("/api/explore/memories", params={"hashtags": f"dalat{RUN}", "page_size": 50}).json()["data"]
    pins = [p["id"] for p in c.get("/api/explore/pins", params={"hashtags": f"dalat{RUN}"}).json()["data"]]
    ids = [x["id"] for x in lst["items"]]
    record("US-EXP-002 AC1", sorted(ids) == sorted(tagged) and sorted(pins) == sorted(tagged), f"danh sách {lst['total']} ký ức, bản đồ {len(pins)} ghim (mong 8)")


@safe("US-EXP-002 AC2")
def _():
    lst = c.get("/api/explore/memories", params={"hashtags": f"dalat{RUN},phuot{RUN}", "page_size": 50}).json()["data"]
    record("US-EXP-002 AC2", lst["total"] == 10, f"chọn 2 hashtag → {lst['total']} ký ức (mong 10 = 8 + 2, phép OR)")


@safe("US-EXP-002 AC3")
def _():
    r = c.get("/api/explore/memories", params={"hashtags": f"bienxanh{RUN}"})
    record("US-EXP-002 AC3", msg(r) == "Chưa có ký ức nào với hashtag này" and r.json()["data"]["total"] == 0, f"'{msg(r)}'")


@safe("US-EXP-002 AC4")
def _():
    box = {"south": -21, "west": -151, "north": -19, "east": -149}
    pins = c.get("/api/explore/pins", params=box).json()["data"]
    record("US-EXP-002 AC4", len(pins) == 20, f"bỏ lọc → {len(pins)} ghim trong vùng (mong 20)")


@safe("US-EXP-003 AC1")
def _():
    u = register("exp3", name="Tác giả khu vực")
    ld = [create_memory(u, title=f"LĐ {i}", lat=11.94 + i * 0.001, lng=108.45, place="Đà Lạt", visibility="public") for i in range(6)]
    regions = [x["region"] for x in ld]
    MEM["ld"] = [x["id"] for x in ld]
    rid = region_id("Lâm Đồng")
    lst = c.get("/api/explore/memories", params={"region": rid, "page_size": 50}).json()["data"]
    record("US-EXP-003 AC1", lst["total"] >= 6 and all(r and r["name"] == "Lâm Đồng" for r in regions),
           f"6 ký ức tạo tại tọa độ Đà Lạt được gán khu vực={regions[0]}; lọc Lâm Đồng → {lst['total']} ký ức (mong 6)")


@safe("US-EXP-003 AC2")
def _():
    rid = region_id("Lâm Đồng")
    nores = MEM["exp_pub"][1]
    in_filter = nores in [x["id"] for x in c.get("/api/explore/memories", params={"region": rid, "page_size": 50}).json()["data"]["items"]]
    in_all = nores in [p["id"] for p in c.get("/api/explore/pins", params=BOX).json()["data"]]
    record("US-EXP-003 AC2", not in_filter and in_all, f"ký ức không có khu vực: có trong kết quả lọc={in_filter}, có khi không lọc={in_all}")


@safe("US-EXP-003 AC3")
def _():
    rid = region_id("Lâm Đồng")
    u = register("exp3b")
    a = create_memory(u, title="LĐ phượt", lat=11.95, lng=108.44, place="Đà Lạt", visibility="public")
    b = create_memory(u, title="LĐ không tag", lat=11.95, lng=108.44, place="Đà Lạt", visibility="public")
    c.post(f"/api/memories/{a['id']}/hashtags", json={"hashtags": [f"phuotld{RUN}"]}, headers=H(u))
    sql("UPDATE memories SET region_id=%s WHERE id IN (%s,%s)", rid, a["id"], b["id"])  # bỏ qua lỗi gán khu vực để kiểm phép AND
    ids = [x["id"] for x in c.get("/api/explore/memories", params={"region": rid, "hashtags": f"phuotld{RUN}"}).json()["data"]["items"]]
    record("US-EXP-003 AC3", ids == [a["id"]], f"(gán khu vực bằng SQL để kiểm riêng phép kết hợp) kết quả {ids}, mong [{a['id']}]")


@safe("US-EXP-003 AC4")
def _():
    rid = region_id("Cao Bằng")
    r = c.get("/api/explore/memories", params={"region": rid})
    record("US-EXP-003 AC4", msg(r) == "Chưa có ký ức công khai trong khu vực này", f"'{msg(r)}'")


@safe("US-EXP-004 AC1")
def _():
    u = register("exp4", name="Tác giả tìm kiếm")
    ids = []
    for i, d in enumerate(["2024-01-01", "2025-05-05", "2023-03-03", "2025-09-09", "2024-12-12"]):
        title = f"Dạo Hồ Gươm {RUN} {i}" if i % 2 == 0 else f"Ký ức {RUN} {i}"
        place = "Hồ Gươm, Hà Nội" if i % 2 else "Hà Nội"
        ids.append((d, create_memory(u, title=title, place=place, day=d, visibility="public")["id"]))
    MEM["search_ids"] = {i for _, i in ids}
    r = c.get("/api/explore/memories", params={"q": "Hồ Gươm", "page_size": 50}).json()["data"]
    got = [x for x in r["items"] if x["id"] in MEM["search_ids"]]
    dates = [str(x["memory_date"]) for x in got]
    record("US-EXP-004 AC1", len(got) == 5 and dates == sorted(dates, reverse=True), f"tìm 'Hồ Gươm' → {len(got)}/5 ký ức thử; thứ tự ngày {dates}")


@safe("US-EXP-004 AC2")
def _():
    a = [x["id"] for x in c.get("/api/explore/memories", params={"q": "Hồ Gươm", "page_size": 50}).json()["data"]["items"]]
    b = [x["id"] for x in c.get("/api/explore/memories", params={"q": "hồ gươm", "page_size": 50}).json()["data"]["items"]]
    record("US-EXP-004 AC2", a == b and a, f"'Hồ Gươm' {len(a)} kết quả, 'hồ gươm' {len(b)} kết quả, giống nhau={a == b}")


@safe("US-EXP-004 AC3")
def _():
    r = c.get("/api/explore/memories", params={"q": "a"})
    record("US-EXP-004 AC3", r.status_code == 422 and msg(r) == "Nhập ít nhất 2 ký tự", f"{r.status_code} '{msg(r)}'")


@safe("US-EXP-004 AC4")
def _():
    r = c.get("/api/explore/memories", params={"q": "xyzxyz"})
    record("US-EXP-004 AC4", msg(r) == "Không tìm thấy kết quả cho xyzxyz", f"'{msg(r)}'")


@safe("US-EXP-005 AC1")
def _():
    u = register("exp5")
    for d in ["2024-01-05", "2024-03-01", "2024-07-07", "2024-12-31"]:
        create_memory(u, title=d, day=d, visibility="public" if d.endswith("01") else None)
    for d in ["2025-01-01", "2025-03-01", "2025-03-31"]:
        create_memory(u, title=d, day=d)
    MEM["exp5"] = u
    r = c.get("/api/memories/mine", params={"year": 2024, "order": "asc"}, headers=H(u)).json()["data"]
    dates = [str(x["memory_date"]) for x in r["items"]]
    vis = {x["visibility"] for x in r["items"]}
    record("US-EXP-005 AC1", dates == ["2024-01-05", "2024-03-01", "2024-07-07", "2024-12-31"] and vis == {"public", "private"},
           f"năm 2024 → {dates}, chế độ {sorted(vis)}")


@safe("US-EXP-005 AC2")
def _():
    r = c.get("/api/memories/mine", params={"date_from": "2025-03-01", "date_to": "2025-03-31"}, headers=H(MEM["exp5"])).json()["data"]
    dates = sorted(str(x["memory_date"]) for x in r["items"])
    record("US-EXP-005 AC2", dates == ["2025-03-01", "2025-03-31"], f"→ {dates}")


@safe("US-EXP-005 AC3")
def _():
    r = c.get("/api/memories/mine", params={"date_from": "2025-03-31", "date_to": "2025-03-01"}, headers=H(MEM["exp5"]))
    record("US-EXP-005 AC3", r.status_code == 422 and msg(r) == "Ngày bắt đầu phải trước hoặc bằng ngày kết thúc", f"{r.status_code} '{msg(r)}'")


@safe("US-EXP-005 AC4")
def _():
    r = c.get("/api/memories/mine", params={"year": 2020}, headers=H(MEM["exp5"]))
    record("US-EXP-005 AC4", msg(r) == "Bạn chưa có ký ức nào trong khoảng thời gian này", f"'{msg(r)}'")


# ======================================================================== EP4 – Quản trị
@safe("US-ADM-001 AC1")
def _():
    a = MEM["admin"]
    m = create_memory(owner, title="Vi phạm", lat=-30, lng=-140, place="Đảo", visibility="public")
    MEM["adm"] = m["id"]
    r = c.post(f"/api/admin/memories/{m['id']}/hide", json={"reason": "Hình ảnh không phù hợp"}, headers=H(a))
    pins = [p["id"] for p in c.get("/api/explore/pins").json()["data"]]
    own = c.get(f"/api/memories/{m['id']}", headers=H(owner)).json()["data"]
    log = sql("SELECT admin_id, created_at, reason FROM admin_actions WHERE action='hide_memory' AND target_id=%s", m["id"])
    record("US-ADM-001 AC1", r.status_code == 200 and m["id"] not in pins and own["hidden_by_admin"] and log and log[0][0] == a["id"] and log[0][2] == "Hình ảnh không phù hợp",
           f"{r.status_code}; còn trên bản đồ={m['id'] in pins}; chủ thấy hidden_by_admin={own['hidden_by_admin']}; nhật ký={log[0] if log else None}")


@safe("US-ADM-001 AC2")
def _():
    r = c.post(f"/api/admin/memories/{MEM['adm']}/unhide", json={}, headers=H(MEM["admin"]))
    pins = [p["id"] for p in c.get("/api/explore/pins").json()["data"]]
    record("US-ADM-001 AC2", r.status_code == 200 and MEM["adm"] in pins, f"{r.status_code}; xuất hiện lại={MEM['adm'] in pins}")


@safe("US-ADM-001 AC3")
def _():
    r = c.post(f"/api/admin/memories/{MEM['adm']}/hide", json={"reason": " "}, headers=H(MEM["admin"]))
    st = sql("SELECT status FROM memories WHERE id=%s", MEM["adm"])[0][0]
    record("US-ADM-001 AC3", r.status_code == 422 and msg(r) == "Vui lòng nhập lý do" and st == "active", f"{r.status_code} '{msg(r)}', status={st}")


@safe("US-ADM-001 AC4")
def _():
    r = c.get("/api/admin/memories", headers=H(other))
    h = c.post(f"/api/admin/memories/{MEM['adm']}/hide", json={"reason": "x"}, headers=H(other))
    st = sql("SELECT status FROM memories WHERE id=%s", MEM["adm"])[0][0]
    record("US-ADM-001 AC4", r.status_code == 403 and msg(r) == "Bạn không có quyền truy cập" and st == "active",
           f"API → {r.status_code} '{msg(r)}'; thử ẩn → {h.status_code}; status={st} (trang /admin/ kiểm ở trình duyệt)")


@safe("US-ADM-001 AC5")
def _():
    a = MEM["admin"]
    by_title = c.get("/api/admin/memories", params={"q": "Vi phạm"}, headers=H(a)).json()["data"]["items"]
    by_author = c.get("/api/admin/memories", params={"q": "Chủ Ký Ức"}, headers=H(a)).json()["data"]["items"]
    only_public = all(x["visibility"] == "public" for x in by_author)
    has_status = all("status" in x for x in by_title + by_author)
    record("US-ADM-001 AC5", any(x["id"] == MEM["adm"] for x in by_title) and by_author and only_public and has_status,
           f"theo tiêu đề {len(by_title)} kết quả, theo tác giả {len(by_author)} kết quả, chỉ công khai={only_public}, có trạng thái={has_status}")


@safe("US-ADM-002 AC1")
def _():
    a = MEM["admin"]
    m = create_memory(owner, title="Xóa nặng", visibility="public")
    up = c.post(f"/api/memories/{m['id']}/images", files=[("images", ("x.jpg", jpeg(1000), "image/jpeg"))], headers=H(owner)).json()["data"]
    r = c.post(f"/api/admin/memories/{m['id']}/delete", json={"reason": "Vi phạm nghiêm trọng"}, headers=H(a))
    det = c.get(f"/api/memories/{m['id']}", headers=H(owner)).status_code
    img = c.get(up[0]["url"], headers=H(owner)).status_code
    log = sql("SELECT reason FROM admin_actions WHERE action='delete_memory' AND target_id=%s", m["id"])
    record("US-ADM-002 AC1", r.status_code == 200 and det == 404 and img == 404 and log and log[0][0] == "Vi phạm nghiêm trọng",
           f"{r.status_code}; chi tiết → {det}; ảnh → {img}; nhật ký lý do={log[0][0] if log else None}")


@safe("US-ADM-002 AC2")
def _():
    m = create_memory(owner, title="Không lý do", visibility="public")
    r = c.post(f"/api/admin/memories/{m['id']}/delete", json={"reason": ""}, headers=H(MEM["admin"]))
    d = sql("SELECT deleted_at FROM memories WHERE id=%s", m["id"])[0][0]
    record("US-ADM-002 AC2", r.status_code == 422 and msg(r) == "Vui lòng nhập lý do" and d is None, f"{r.status_code} '{msg(r)}'")


@safe("US-ADM-002 AC3")
def _():
    m = create_memory(owner, title="Chủ xóa trước", visibility="public")
    c.delete(f"/api/memories/{m['id']}", headers=H(owner))
    r = c.post(f"/api/admin/memories/{m['id']}/delete", json={"reason": "x"}, headers=H(MEM["admin"]))
    record("US-ADM-002 AC3", r.status_code == 404 and msg(r) == "Ký ức không tồn tại", f"{r.status_code} '{msg(r)}'")


@safe("US-ADM-002 AC4")
def _():
    m = create_memory(owner, title="Người thường xóa", visibility="public")
    r = c.post(f"/api/admin/memories/{m['id']}/delete", json={"reason": "x"}, headers=H(other))
    d = sql("SELECT deleted_at FROM memories WHERE id=%s", m["id"])[0][0]
    record("US-ADM-002 AC4", r.status_code == 403 and d is None, f"{r.status_code} '{msg(r)}', deleted_at={d}")


@safe("US-ADM-003 AC1")
def _():
    u = register("bikhoa", name="Bị khóa")
    r = c.post(f"/api/admin/users/{u['id']}/lock", json={"reason": "Spam"}, headers=H(MEM["admin"]))
    login = c.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
    log = sql("SELECT reason FROM admin_actions WHERE action='lock_user' AND target_id=%s", u["id"])
    MEM["locked"] = u
    record("US-ADM-003 AC1", r.status_code == 200 and login.status_code == 403 and log and log[0][0] == "Spam",
           f"{r.status_code}; đăng nhập → {login.status_code} '{msg(login)}'; nhật ký={log[0][0] if log else None}")


@safe("US-ADM-003 AC2")
def _():
    u = MEM["locked"]
    r = c.post(f"/api/admin/users/{u['id']}/unlock", json={}, headers=H(MEM["admin"]))
    login = c.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
    record("US-ADM-003 AC2", r.status_code == 200 and login.status_code == 200, f"{r.status_code}; đăng nhập lại → {login.status_code}")


@safe("US-ADM-003 AC3")
def _():
    a = MEM["admin"]
    r = c.post(f"/api/admin/users/{a['id']}/lock", json={"reason": "x"}, headers=H(a))
    record("US-ADM-003 AC3", r.status_code == 422 and msg(r) == "Bạn không thể khóa chính tài khoản của mình", f"{r.status_code} '{msg(r)}'")


@safe("US-ADM-003 AC4")
def _():
    r = c.post(f"/api/admin/users/{owner['id']}/lock", json={"reason": "x"}, headers=H(other))
    st = sql("SELECT status FROM users WHERE id=%s", owner["id"])[0][0]
    record("US-ADM-003 AC4", r.status_code == 403 and st == "active", f"{r.status_code} '{msg(r)}', status={st}")


@safe("US-ADM-003 AC5")
def _():
    a = MEM["admin"]
    by_mail = c.get("/api/admin/users", params={"q": email("chu")}, headers=H(a)).json()["data"]["items"]
    by_name = c.get("/api/admin/users", params={"q": "Người Khác"}, headers=H(a)).json()["data"]["items"]
    record("US-ADM-003 AC5", [x["id"] for x in by_mail] == [owner["id"]] and other["id"] in [x["id"] for x in by_name] and all(x["status"] in ("active", "locked") for x in by_mail + by_name),
           f"theo email {len(by_mail)} kết quả, theo tên {len(by_name)} kết quả, có trạng thái")


# ======================================================================== Kiểm tra thêm (lỗi tiềm ẩn, không thuộc AC)
extra: dict[str, dict] = {}


def check_extra(name, ok, detail):
    extra[name] = {"status": "ĐẠT" if ok else "LỖI", "detail": detail}
    print(f"{extra[name]['status']:5} {name}: {detail}")


try:
    bad_time = sql("SELECT COUNT(*) FROM memories WHERE updated_at < created_at")[0][0]
    check_extra("Thời điểm cập nhật không sớm hơn thời điểm tạo (L14)", bad_time == 0,
                f"{bad_time} ký ức có updated_at < created_at sau khi đổi chế độ/hashtag/chuyến đi")
    leaked = [x for x in c.get("/api/explore/memories", params={"page_size": 50}).json()["data"]["items"]
              if (x["author"].get("avatar_url") or "").startswith("avatars/")]
    check_extra("Không lộ đường dẫn lưu trữ ảnh đại diện", not leaked, f"{len(leaked)} ký ức lộ avatar_path")
    with_region = sql("SELECT COUNT(*) FROM memories WHERE region_id IS NOT NULL AND deleted_at IS NULL")[0][0]
    check_extra("Ký ức trong nước được gán tỉnh/thành (L05)", with_region > 0, f"{with_region} ký ức có khu vực")
except Exception as exc:  # noqa: BLE001
    check_extra("Kiểm tra thêm", False, f"Lỗi khi chạy: {exc}")

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps({**results, "_kiem_tra_them": extra}, ensure_ascii=False, indent=1), encoding="utf-8")
counts = {}
for v in results.values():
    counts[v["status"]] = counts.get(v["status"], 0) + 1
print("\nTỔNG:", len(results), counts)
