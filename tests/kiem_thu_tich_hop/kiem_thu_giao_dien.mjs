// Kiểm thử giao diện các AC cần trình duyệt, trên Edge: máy tính (1366×800) và điện thoại (giả lập Pixel 7, cảm ứng).
// Cần: server kiểm thử đang chạy (python tests/kiem_thu_tich_hop/chay_server.py) và đã `npm install` trong thư mục này.
// Chạy: node kiem_thu_giao_dien.mjs   →  ket_qua/giao_dien.json + ảnh chụp trong ket_qua/anh_chup/
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, devices } from "playwright-core";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..", "..");
const BASE = "http://127.0.0.1:8010";
const OUT = join(HERE, "ket_qua");
const SHOTS = join(OUT, "anh_chup");
const PYTHON = process.env.PYTHON || join(ROOT, ".venv", "Scripts", "python.exe");
const RUN = Math.random().toString(16).slice(2, 8);
mkdirSync(SHOTS, { recursive: true });

const DEVICES = {
  "Máy tính": { viewport: { width: 1366, height: 800 } },
  "Điện thoại": { ...devices["Pixel 7"] },
};
const results = {}; // { "US-...": { "Máy tính": {status, detail}, "Điện thoại": {...} } }
const pageChecks = {}; // lỗi JS + cuộn ngang theo trang

// ---------- Hỗ trợ dữ liệu ----------
function sql(query) {
  // Chạy SQL trên DB kiểm thử bằng cấu hình .env của dự án (dùng cho việc cấp quyền admin)
  const code = `import sys,pymysql; sys.path.insert(0, r"${ROOT}"); from app.core.config import settings as s
c=pymysql.connect(host=s.db_host,port=s.db_port,user=s.db_user,password=s.db_password,database="ban_do_ky_uc_kiemthu",autocommit=True)
c.cursor().execute(sys.argv[1])`;
  execFileSync(PYTHON, ["-c", code, query]);
}

async function api(method, path, { token, json, form } = {}) {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  let body;
  if (json) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) body = form;
  const res = await fetch(BASE + path, { method, headers, body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status} ${data.message}`);
  return data.data;
}

async function register(tag, name) {
  const email = `${tag}.${RUN}@example.com`;
  const data = await api("POST", "/api/auth/register", { json: { display_name: name, email, password: "Matkhau123" } });
  return { id: data.user.id, token: data.access_token, email, password: "Matkhau123", name };
}

async function memory(user, title, { visibility = "private", lat = 21.0287, lng = 105.8524 } = {}) {
  const form = new FormData();
  Object.entries({ title, content: "Nội dung kiểm thử", place_name: "Hồ Gươm, Hà Nội", latitude: lat, longitude: lng, memory_date: "2025-10-12", visibility })
    .forEach(([k, v]) => form.append(k, String(v)));
  return api("POST", "/api/memories", { token: user.token, form });
}

function record(ac, device, ok, detail, status) {
  results[ac] ??= {};
  results[ac][device] = { status: status || (ok ? "ĐẠT" : "LỖI"), detail };
  console.log(`${(status || (ok ? "ĐẠT" : "LỖI")).padEnd(5)} ${device.padEnd(10)} ${ac.padEnd(15)} ${detail}`);
}

async function shot(page, name) {
  const file = `${name}.png`;
  await page.screenshot({ path: join(SHOTS, file) }).catch(() => {});
  return file;
}

async function login(page, user, next = "/ban-do") {
  await page.goto(`${BASE}/accounts/login.html?next=${encodeURIComponent(next)}`);
  await page.fill('input[name="email"]', user.email);
  await page.fill('input[name="password"]', user.password);
  await Promise.all([page.waitForURL((url) => !url.pathname.startsWith("/accounts/login")), page.click('form button[type="submit"]')]);
  await page.waitForLoadState("networkidle");
}

// Chạm giữ (điện thoại) hoặc nhấp đúp (máy tính) giữa bản đồ
async function pickOnMap(page, mobile) {
  const box = await page.locator("#map").boundingBox();
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  if (!mobile) return page.mouse.dblclick(x, y);
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] });
  await page.waitForTimeout(900);
  await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
}

async function check(ac, device, page, fn) {
  try {
    await fn();
  } catch (error) {
    const file = await shot(page, `${ac.replace(/ /g, "_")}_${device === "Máy tính" ? "may_tinh" : "dien_thoai"}_loi`);
    record(ac, device, false, `Lỗi khi chạy: ${error.message.split("\n")[0]} (ảnh ${file})`);
  }
}

// ---------- Chạy ----------
const browser = await chromium.launch({ channel: "msedge" });
const edgeVersion = browser.version();

// Ảnh JPEG thật (để trình duyệt hiển thị được), vẽ bằng canvas của Edge
const jpegPage = await browser.newPage();
const jpegBase64 = await jpegPage.evaluate(() => {
  const canvas = Object.assign(document.createElement("canvas"), { width: 320, height: 200 });
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#ff8a3d";
  ctx.fillRect(0, 0, 320, 200);
  return canvas.toDataURL("image/jpeg", 0.9).split(",")[1];
});
await jpegPage.close();
const jpeg = Buffer.from(jpegBase64, "base64");

for (const [device, options] of Object.entries(DEVICES)) {
  const mobile = device === "Điện thoại";
  const slug = mobile ? "dien_thoai" : "may_tinh";

  // Dữ liệu riêng cho từng thiết bị
  const owner = await register(`ui_chu_${slug}`, `Chủ UI ${slug}`);
  const normal = await register(`ui_thuong_${slug}`, `Thường UI ${slug}`);
  const admin = await register(`ui_admin_${slug}`, `Admin UI ${slug}`);
  sql(`UPDATE users SET role='admin' WHERE id=${admin.id}`);
  admin.token = (await api("POST", "/api/auth/login", { json: { email: admin.email, password: admin.password } })).access_token;

  const withImages = await memory(owner, "Chiều thu Hà Nội", { visibility: "public" });
  const imgForm = new FormData();
  for (let i = 1; i <= 3; i++) imgForm.append("images", new Blob([jpeg], { type: "image/jpeg" }), `anh${i}.jpg`);
  await api("POST", `/api/memories/${withImages.id}/images`, { token: owner.token, form: imgForm });
  await api("POST", `/api/memories/${withImages.id}/hashtags`, { token: owner.token, json: { hashtags: ["hanoi", "mua_thu"] } });
  const toDelete = await memory(owner, "Ký ức thử nút Hủy");
  const hidden = await memory(owner, "Ký ức bị ẩn", { visibility: "public" });
  await api("POST", `/api/admin/memories/${hidden.id}/hide`, { token: admin.token, json: { reason: "Kiểm thử giao diện" } });

  const context = await browser.newContext({ ...options, locale: "vi-VN" });
  const page = await context.newPage();
  const jsErrors = [];
  page.on("pageerror", (error) => jsErrors.push(`${new URL(page.url()).pathname}: ${error.message}`));
  page.on("console", (m) => m.type() === "error" && !/tile\.openstreetmap|Failed to load resource/.test(m.text()) && jsErrors.push(`${new URL(page.url()).pathname}: ${m.text()}`));

  // US-ACC-001 AC1 – đăng ký trên form → vào bản đồ + thông báo
  await check("US-ACC-001 AC1", device, page, async () => {
    await page.goto(`${BASE}/accounts/register.html`);
    await page.fill('input[name="display_name"]', "An");
    await page.fill('input[name="email"]', `ui_dk_${slug}.${RUN}@example.com`);
    await page.fill('input[name="password"]', "Matkhau123");
    await page.fill('input[name="password_confirm"]', "Matkhau123");
    await Promise.all([page.waitForURL(/\/ban-do/), page.click('form button[type="submit"]')]);
    const toast = await page.locator("#toast").textContent({ timeout: 5000 }).catch(() => "");
    const file = await shot(page, `ACC001_AC1_${slug}`);
    record("US-ACC-001 AC1", device, page.url().includes("/ban-do") && toast.includes("Đăng ký thành công"), `chuyển tới ${new URL(page.url()).pathname}, thông báo '${toast.trim()}' (ảnh ${file})`);
    await page.evaluate(() => localStorage.clear());
  });

  // US-ACC-002 AC1 – đăng nhập → bản đồ + tên hiển thị
  await check("US-ACC-002 AC1", device, page, async () => {
    await login(page, owner);
    const nameVisible = await page.getByText(owner.name).first().isVisible().catch(() => false);
    const nameInDom = (await page.locator(".account-menu__name").textContent().catch(() => "")) || "";
    const file = await shot(page, `ACC002_AC1_${slug}`);
    record("US-ACC-002 AC1", device, page.url().includes("/ban-do") && nameInDom.includes(owner.name),
      `trang ${new URL(page.url()).pathname}; tên '${nameInDom}' ${nameVisible ? "đang hiện" : "có trong menu (thu gọn trên màn hình nhỏ)"} (ảnh ${file})`);
  });

  // US-MEM-005 AC1 + US-MEM-003 AC1 – chi tiết ký ức của mình: tiêu đề, ngày, ảnh hiển thị được, hashtag, nút sửa/xóa
  await check("US-MEM-005 AC1", device, page, async () => {
    await page.goto(`${BASE}/ban-do?memory=${withImages.id}`);
    await page.locator(".memory-detail__title").waitFor({ timeout: 10000 });
    await page.waitForFunction(() => [...document.querySelectorAll(".memory-detail img")].filter((i) => i.complete && i.naturalWidth > 0).length >= 3, null, { timeout: 10000 }).catch(() => {});
    const info = await page.evaluate(() => {
      const d = document.querySelector(".memory-detail");
      const imgs = [...d.querySelectorAll("img")];
      return {
        title: d.querySelector(".memory-detail__title")?.textContent,
        text: d.textContent,
        shown: imgs.filter((i) => i.complete && i.naturalWidth > 0).length,
        total: imgs.length,
        buttons: [...document.querySelectorAll(".drawer button, .memory-detail button, [class*=drawer] button")].map((b) => b.textContent.trim()),
      };
    });
    const hasEdit = info.buttons.some((t) => /Sửa/.test(t));
    const hasDelete = info.buttons.some((t) => /Xóa/.test(t));
    const ok = info.title === "Chiều thu Hà Nội" && info.text.includes("12/10/2025") && info.shown === 3 && /hanoi/.test(info.text) && hasEdit && hasDelete;
    const file = await shot(page, `MEM005_AC1_${slug}`);
    const detail = `tiêu đề '${info.title}', ngày 12/10/2025=${info.text.includes("12/10/2025")}, ảnh hiển thị ${info.shown}/${info.total}, hashtag=${/hanoi/.test(info.text)}, nút Sửa=${hasEdit}, Xóa=${hasDelete} (ảnh ${file})`;
    record("US-MEM-005 AC1", device, ok, detail);
    record("US-MEM-003 AC1", device, info.shown === 3, `chi tiết hiển thị ${info.shown}/3 ảnh (ảnh ${file})`);
  });

  // US-MEM-004 AC1 – chi tiết ký ức có video: thẻ <video> được gắn và luồng video tải được
  await check("US-MEM-004 AC1", device, page, async () => {
    const withVideo = await memory(owner, "Ký ức có video");
    const header = Buffer.from([0, 0, 0, 0x18, ...Buffer.from("ftypmp42")]);
    const videoForm = new FormData();
    videoForm.append("video", new Blob([Buffer.concat([header, Buffer.alloc(200_000)])], { type: "video/mp4" }), "v.mp4");
    await api("POST", `/api/memories/${withVideo.id}/video`, { token: owner.token, form: videoForm });
    const videoRequests = [];
    const onResponse = (res) => /\/api\/media\/\d+/.test(res.url()) && videoRequests.push(`${new URL(res.url()).pathname} → ${res.status()}`);
    page.on("response", onResponse);
    await page.goto(`${BASE}/ban-do?memory=${withVideo.id}`);
    await page.locator(".memory-detail__title").waitFor({ timeout: 10000 });
    const video = page.locator(".memory-detail video");
    await video.waitFor({ timeout: 8000 });
    const src = await video.evaluate((v) => new Promise((done) => {
      const read = () => v.currentSrc || v.src || v.querySelector("source")?.src || "";
      const started = Date.now();
      (function poll() { const s = read(); if (s || Date.now() - started > 8000) done(s); else setTimeout(poll, 200); })();
    }));
    await page.waitForTimeout(500);
    page.off("response", onResponse);
    const okLoads = videoRequests.filter((r) => /→ 20[06]$/.test(r));
    const file = await shot(page, `MEM004_AC1_${slug}`);
    record("US-MEM-004 AC1", device, Boolean(src) && okLoads.length > 0,
      `thẻ video có trên trang chi tiết, nguồn '${src ? src.replace(BASE, "").slice(0, 50) : "(rỗng)"}'; tải video qua mạng: ${videoRequests.join(", ") || "không có"} ` +
      `(tệp thử không phải video thật nên không kiểm được hình/tiếng) (ảnh ${file})`);
  });

  // US-MEM-005 AC4 – chủ thấy "Đã bị quản trị viên ẩn"
  await check("US-MEM-005 AC4", device, page, async () => {
    await page.goto(`${BASE}/ban-do?memory=${hidden.id}`);
    await page.locator(".memory-detail__title").waitFor({ timeout: 10000 });
    const banner = await page.locator(".notice-banner").first().textContent().catch(() => "");
    const file = await shot(page, `MEM005_AC4_${slug}`);
    record("US-MEM-005 AC4", device, banner.includes("Đã bị quản trị viên ẩn"), `chủ ký ức thấy '${banner.trim()}' (ảnh ${file})`);
  });

  // US-MEM-007 AC2 – chọn Xóa rồi Hủy → ký ức còn nguyên
  await check("US-MEM-007 AC2", device, page, async () => {
    await page.goto(`${BASE}/ban-do?memory=${toDelete.id}`);
    await page.locator(".memory-detail__title").waitFor({ timeout: 10000 });
    await page.getByRole("button", { name: /Xóa/ }).first().click();
    await page.locator(".modal").waitFor();
    const file = await shot(page, `MEM007_AC2_${slug}`);
    await page.locator(".modal").getByRole("button", { name: "Hủy" }).click();
    await page.waitForTimeout(500);
    const still = await fetch(`${BASE}/api/memories/${toDelete.id}`, { headers: { Authorization: `Bearer ${owner.token}` } });
    record("US-MEM-007 AC2", device, still.status === 200, `sau khi bấm Hủy, ký ức → ${still.status} (ảnh hộp xác nhận ${file})`);
  });

  // US-MEM-002 AC1 – người dùng nhấp đúp / chạm giữ trên bản đồ → mở form tạo ký ức
  await check("US-MEM-002 AC1", device, page, async () => {
    await page.goto(`${BASE}/ban-do`);
    await page.waitForLoadState("networkidle");
    if (mobile) await page.locator("#sidebar-backdrop").click({ trial: false, timeout: 1000 }).catch(() => {});
    await pickOnMap(page, mobile);
    const form = page.locator('form input[name="title"]');
    const opened = await form.waitFor({ timeout: 6000 }).then(() => true).catch(() => false);
    const file = await shot(page, `MEM002_AC1_${slug}`);
    record("US-MEM-002 AC1", device, opened, `${mobile ? "chạm giữ" : "nhấp đúp"} bản đồ → form tạo ký ức ${opened ? "mở" : "KHÔNG mở"} (ảnh ${file})`);
  });

  // US-MEM-001 AC1 + AC3 – tìm địa điểm trong form tạo ký ức (gọi Nominatim thật qua máy chủ, cần Internet)
  await check("US-MEM-001 AC3", device, page, async () => {
    const query = page.locator("#location-query");
    await query.waitFor({ timeout: 5000 });
    await query.fill("xyzxyz");
    await page.locator("#location-search").click();
    const results = page.locator("#location-results");
    await results.getByText(/Không tìm thấy địa điểm/).waitFor({ timeout: 15000 });
    const text = (await results.innerText()).trim();
    const file = await shot(page, `MEM001_AC3_${slug}`);
    record("US-MEM-001 AC3", device, text === "Không tìm thấy địa điểm. Hãy thử tên khác hoặc chọn trực tiếp trên bản đồ", `'${text}' (ảnh ${file})`);
  });

  await check("US-MEM-001 AC1", device, page, async () => {
    const title = `Chiều thu Hà Nội ${slug}`;
    await page.locator("#location-query").fill("Hồ Gươm");
    await page.locator("#location-search").click();
    const first = page.locator("#location-results li button").first();
    await first.waitFor({ timeout: 15000 });
    await first.click();
    const form = page.locator('input[name="title"]').locator("xpath=ancestor::form");
    await form.locator('input[name="title"]').fill(title);
    await form.locator('input[name="memory_date"]').fill("2025-10-12");
    await form.locator('textarea[name="content"]').fill("Dạo quanh hồ buổi chiều");
    await page.locator("#memory-save").click();
    await page.locator(".memory-detail__title").waitFor({ timeout: 10000 });
    const mine = await api("GET", "/api/memories/mine?page_size=50", { token: owner.token });
    const saved = mine.items.find((m) => m.title === title);
    const near = saved && Math.abs(saved.latitude - 21.0287) < 0.01 && Math.abs(saved.longitude - 105.8524) < 0.01;
    const shown = (await page.locator(".memory-detail").innerText()).includes("12/10/2025");
    const file = await shot(page, `MEM001_AC1_${slug}`);
    record("US-MEM-001 AC1", device, Boolean(near) && saved.visibility === "private" && shown,
      `tìm 'Hồ Gươm' → chọn kết quả đầu → lưu: ghim tại (${saved?.latitude}, ${saved?.longitude}) đúng Hồ Gươm=${Boolean(near)}, ` +
      `chế độ=${saved?.visibility}, chi tiết hiện 12/10/2025=${shown} (ảnh ${file})`);
  });

  // US-ACC-006 – trang hồ sơ: đổi tên, chặn ảnh quá lớn / sai định dạng ngay trên trình duyệt
  await check("US-ACC-006 AC1", device, page, async () => {
    await page.goto(`${BASE}/accounts/profile.html`);
    await page.locator('.profile-tabs .tab[data-tab="info"]').click();
    const form = page.locator("#profile-form");
    await form.locator('input[name="display_name"]').fill(`Dread ${slug}`);
    await form.locator('button[type="submit"]').click();
    const message = form.locator(".form-message");
    await message.getByText("Đã cập nhật hồ sơ").waitFor({ timeout: 5000 });
    const author = (await api("GET", `/api/memories/${withImages.id}`)).author.display_name;
    const file = await shot(page, `ACC006_AC1_${slug}`);
    record("US-ACC-006 AC1", device, author === `Dread ${slug}`, `lưu → '${(await message.innerText()).trim()}'; ký ức công khai hiện tên '${author}' (ảnh ${file})`);
    owner.name = `Dread ${slug}`;

    const avatar = page.locator('#avatar-form input[name="avatar"]');
    const avatarMessage = page.locator("#avatar-form .form-message");
    await avatar.setInputFiles({ name: "big.jpg", mimeType: "image/jpeg", buffer: Buffer.alloc(6 * 1024 * 1024, 1) });
    const tooBig = (await avatarMessage.innerText()).trim();
    await avatar.setInputFiles({ name: "baocao.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7") });
    const wrongType = (await avatarMessage.innerText()).trim();
    const file2 = await shot(page, `ACC006_AC5_${slug}`);
    record("US-ACC-006 AC4", device, tooBig === "Ảnh không được vượt quá 5 MB", `chọn ảnh 6 MB → '${tooBig}' (ảnh ${file2})`);
    record("US-ACC-006 AC5", device, wrongType === "Định dạng tệp không được hỗ trợ", `chọn baocao.pdf → '${wrongType}' (ảnh ${file2})`);
  });

  // US-ADM-001 AC4 – người dùng thường mở trang quản trị
  await check("US-ADM-001 AC4", device, page, async () => {
    await page.evaluate((t) => localStorage.setItem("bdku_access_token", t), normal.token);
    await page.goto(`${BASE}/admin/`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(800);
    const text = await page.locator("body").innerText();
    const file = await shot(page, `ADM001_AC4_${slug}`);
    record("US-ADM-001 AC4", device, text.includes("Bạn không có quyền truy cập"),
      `người dùng thường mở /admin/ → trang ${new URL(page.url()).pathname}, có chữ 'Bạn không có quyền truy cập'=${text.includes("Bạn không có quyền truy cập")} (ảnh ${file})`);
    await page.evaluate(() => localStorage.clear());
  });

  // Trang quản trị dùng được trên thiết bị (admin): bảng ký ức + tài khoản tải được
  await check("Trang quản trị", device, page, async () => {
    await page.evaluate((t) => localStorage.setItem("bdku_access_token", t), admin.token);
    await page.goto(`${BASE}/admin/`);
    await page.locator("#admin-memories tr").first().waitFor({ timeout: 8000 });
    await page.waitForTimeout(800);
    const rows = await page.locator("#admin-memories tr").count();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    const file = await shot(page, `quan_tri_${slug}`);
    record("Trang quản trị", device, rows > 0 && overflow <= 1, `bảng ký ức có ${rows} dòng, tràn ngang ${overflow}px (ảnh ${file})`);
    await page.evaluate(() => localStorage.clear());
  });

  // US-ACC-008 AC1 → AC3 – đăng xuất, mở lại trang riêng tư, nút Back
  await check("US-ACC-008 AC1", device, page, async () => {
    await login(page, owner, "/accounts/profile.html");
    await page.waitForTimeout(500);
    await page.locator(".account-trigger").click();
    await Promise.all([page.waitForURL(/login\.html/), page.getByRole("menuitem", { name: /Đăng xuất/ }).click()]);
    await page.waitForLoadState("networkidle");
    const shown = (await page.locator("body").innerText()).includes(owner.name);
    const token = await page.evaluate(() => localStorage.getItem("bdku_access_token"));
    const file = await shot(page, `ACC008_AC1_${slug}`);
    record("US-ACC-008 AC1", device, page.url().includes("login.html") && !shown && !token, `chuyển tới ${new URL(page.url()).pathname}, còn hiện tên=${shown}, còn token=${Boolean(token)} (ảnh ${file})`);

    await page.goBack();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(800);
    const backShown = (await page.locator("body").innerText()).includes(owner.name);
    const file3 = await shot(page, `ACC008_AC3_${slug}`);
    record("US-ACC-008 AC3", device, page.url().includes("login.html") && !backShown, `bấm Back → ${new URL(page.url()).pathname}${new URL(page.url()).search}, lộ thông tin cá nhân=${backShown} (ảnh ${file3})`);

    await page.goto(`${BASE}/accounts/profile.html`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);
    const file2 = await shot(page, `ACC008_AC2_${slug}`);
    const leak = (await page.locator("body").innerText()).includes(owner.name);
    record("US-ACC-008 AC2", device, page.url().includes("login.html") && !leak, `mở lại hồ sơ → ${new URL(page.url()).pathname}, lộ thông tin=${leak} (ảnh ${file2})`);
  });

  // US-ACC-005 – quên mật khẩu → link (chế độ dev chưa có SMTP hiện link trên trang) → đặt mật khẩu mới
  await check("US-ACC-005 AC3", device, page, async () => {
    const user = await register(`ui_quenmk_${slug}`, "Quên MK");
    await page.goto(`${BASE}/accounts/forgot-password.html`);
    await page.fill('#forgot-form input[name="email"]', user.email);
    await page.click('#forgot-form button[type="submit"]');
    const sentBox = page.locator("#forgot-form .form-message:not(#dev-link)");
    await sentBox.getByText(/Nếu email tồn tại/).waitFor({ timeout: 5000 });
    const sent = (await sentBox.innerText()).trim();
    const link = page.locator("#dev-link a");
    await link.waitFor({ timeout: 5000 });
    const file1 = await shot(page, `ACC005_AC1_${slug}`);
    record("US-ACC-005 AC1", device, sent === "Nếu email tồn tại, chúng tôi đã gửi hướng dẫn đặt lại mật khẩu",
      `thông báo '${sent}', liên kết đặt lại hiện ở chế độ dev (ảnh ${file1})`);
    const resetUrl = await link.getAttribute("href");
    await page.goto(resetUrl.replace(/^https?:\/\/[^/]+/, BASE));
    await page.fill('input[name="new_password"]', "Matkhaumoi9");
    await page.fill('input[name="password_confirm"]', "Matkhaumoi9");
    await page.click('form[data-with-token] button[type="submit"]');
    const doneBox = page.locator("form[data-with-token] .form-message");
    await doneBox.getByText(/Đặt lại mật khẩu thành công|Liên kết|Mật khẩu/).waitFor({ timeout: 5000 });
    const done = (await doneBox.innerText()).trim();
    const loginNew = await fetch(`${BASE}/api/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: user.email, password: "Matkhaumoi9" }) });
    const file = await shot(page, `ACC005_AC3_${slug}`);
    record("US-ACC-005 AC3", device, done.includes("Đặt lại mật khẩu thành công") && loginNew.status === 200,
      `'${done}'; đăng nhập bằng mật khẩu mới → ${loginNew.status} (ảnh ${file})`);

    // AC4: mở lại đúng link đó sau khi hết hạn → báo ngay khi mở trang, form bị khóa
    const user2 = await register(`ui_quenmk4_${slug}`, "Hết hạn");
    const forgot2 = await api("POST", "/api/auth/forgot-password", { json: { email: user2.email } });
    sql(`UPDATE password_reset_tokens SET created_at = UTC_TIMESTAMP() - INTERVAL 31 MINUTE, expires_at = UTC_TIMESTAMP() - INTERVAL 1 MINUTE WHERE user_id = ${user2.id}`);
    await page.goto(forgot2.dev_reset_url.replace(/^https?:\/\/[^/]+/, BASE));
    await page.waitForTimeout(800);
    const expired = (await page.locator("form[data-with-token] .form-message").innerText()).trim();
    const locked = await page.locator('input[name="new_password"]').isDisabled();
    const file4 = await shot(page, `ACC005_AC4_${slug}`);
    record("US-ACC-005 AC4", device, expired === "Liên kết đã hết hạn, vui lòng yêu cầu lại" && locked,
      `mở link gửi 31 phút trước → '${expired}', ô mật khẩu bị khóa=${locked} (ảnh ${file4})`);
  });

  // US-MEM-002 AC3 – khách nhấp đúp / chạm giữ bản đồ → yêu cầu đăng nhập
  await check("US-MEM-002 AC3", device, page, async () => {
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${BASE}/ban-do`);
    await page.waitForLoadState("networkidle");
    await pickOnMap(page, mobile);
    const modal = await page.locator(".modal").textContent({ timeout: 5000 }).catch(() => "");
    const file = await shot(page, `MEM002_AC3_${slug}`);
    record("US-MEM-002 AC3", device, /đăng nhập/i.test(modal), `khách ${mobile ? "chạm giữ" : "nhấp đúp"} → '${modal.trim().slice(0, 90)}' (ảnh ${file})`);
    await page.keyboard.press("Escape");
  });

  // US-EXP-001 AC2 – di chuyển bản đồ tới vùng trống
  await check("US-EXP-001 AC2", device, page, async () => {
    await page.goto(`${BASE}/ban-do`);
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => MemoryMap.flyTo(-60, -40, 8));
    await page.waitForTimeout(2500);
    if (mobile) await page.locator("#sidebar-toggle").click();
    await page.locator('#explore-filter input[name="viewport"]').check();
    await page.waitForTimeout(1500);
    const text = await page.locator("#explore-list").innerText();
    const file = await shot(page, `EXP001_AC2_${slug}`);
    record("US-EXP-001 AC2", device, text.includes("Chưa có ký ức công khai trong khu vực này"), `danh sách: '${text.trim().slice(0, 80)}' (ảnh ${file})`);
  });

  // Lỗi JS + tràn ngang trên các trang chính (khách)
  for (const path of ["/", "/ban-do", "/accounts/login.html", "/accounts/register.html", "/accounts/forgot-password.html"]) {
    await page.goto(BASE + path);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    pageChecks[`${device} ${path}`] = { overflow };
  }
  pageChecks[`${device} lỗi JavaScript`] = [...new Set(jsErrors)];
  await context.close();
}

await browser.close();
writeFileSync(join(OUT, "giao_dien.json"), JSON.stringify({ edgeVersion, devices: { "Máy tính": "1366×800", "Điện thoại": "giả lập Pixel 7 (412×915, cảm ứng)" }, results, pageChecks }, null, 1), "utf-8");
console.log("\nKiểm tra trang:", JSON.stringify(pageChecks, null, 1));
