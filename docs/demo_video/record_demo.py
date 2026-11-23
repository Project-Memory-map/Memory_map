"""Tự động quay màn hình ứng dụng 'Bản đồ Ký ức' (1920x1080, 30fps) bằng Playwright.

Chạy độc lập trên DB cô lập `ban_do_ky_uc_demo` và thư mục `docs/demo_video/.work/uploads`
để tuyệt đối không ảnh hưởng dữ liệu làm việc `ban_do_ky_uc` hay mã nguồn chính.
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path

import httpx
import imageio_ffmpeg
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import demo_config as cfg  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


CURSOR_INIT_SCRIPT = r"""
(() => {
  const initCursor = () => {
    if (!document.body || document.getElementById("__demo_cursor")) return;
    const style = document.createElement("style");
    style.textContent = `
      #__demo_cursor {
        position: fixed;
        top: 0; left: 0;
        width: 26px; height: 26px;
        pointer-events: none;
        z-index: 2147483647;
        transform: translate3d(-100px, -100px, 0);
        filter: drop-shadow(0 3px 6px rgba(15, 23, 42, 0.45));
        transition: transform 0.016s linear;
      }
      .__demo_ripple {
        position: fixed;
        width: 34px; height: 34px;
        margin-left: -17px; margin-top: -17px;
        border-radius: 999px;
        border: 3px solid #2563eb;
        background: rgba(37, 99, 235, 0.18);
        pointer-events: none;
        z-index: 2147483646;
        animation: __demo_ripple_anim 0.48s ease-out forwards;
      }
      @keyframes __demo_ripple_anim {
        0% { transform: scale(0.35); opacity: 0.95; }
        100% { transform: scale(1.65); opacity: 0; }
      }
    `;
    document.head.appendChild(style);
    const cursor = document.createElement("div");
    cursor.id = "__demo_cursor";
    cursor.innerHTML = `
      <svg viewBox="0 0 28 28" width="26" height="26" xmlns="http://www.w3.org/2000/svg">
        <path d="M4 2 L22 14 L13.5 15.8 L17.5 24 L14.2 25.5 L10.2 17.3 L4 22 Z"
              fill="#ffffff" stroke="#0f172a" stroke-width="2" stroke-linejoin="round"/>
      </svg>`;
    document.body.appendChild(cursor);

    window.addEventListener("mousemove", (e) => {
      cursor.style.transform = `translate3d(${e.clientX - 2}px, ${e.clientY - 2}px, 0)`;
    }, { passive: true, capture: true });

    window.addEventListener("mousedown", (e) => {
      const ripple = document.createElement("div");
      ripple.className = "__demo_ripple";
      ripple.style.left = `${e.clientX}px`;
      ripple.style.top = `${e.clientY}px`;
      document.body.appendChild(ripple);
      setTimeout(() => ripple.remove(), 520);
    }, { passive: true, capture: true });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCursor);
  } else {
    initCursor();
  }
  const observer = new MutationObserver(() => initCursor());
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def start_static_server(directory: Path) -> tuple[socketserver.TCPServer, int]:
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def run_cmd(cmd: list[str], env: dict[str, str] | None = None, cwd: Path | None = None) -> None:
    res = subprocess.run(cmd, env=env, cwd=str(cwd or cfg.ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"Lệnh thất bại ({res.returncode}): {' '.join(cmd)}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")


def prepare_isolated_db_and_server() -> subprocess.Popen:
    print("1/5 Khởi tạo DB cô lập `ban_do_ky_uc_demo` và nạp dữ liệu mẫu...")
    shutil.rmtree(cfg.DEMO_UPLOADS, ignore_errors=True)
    cfg.DEMO_UPLOADS.mkdir(parents=True, exist_ok=True)

    env = {
        **os.environ,
        "APP_ENV": "dev",
        "DB_NAME": cfg.DEMO_DB,
        "UPLOAD_DIR": str(cfg.DEMO_UPLOADS),
        "APP_BASE_URL": cfg.DEMO_BASE_URL,
    }
    py = sys.executable
    run_cmd([py, str(cfg.ROOT / "scripts" / "init_db.py"), "--ten", cfg.DEMO_DB, "--xoa-cu"], env=env)
    run_cmd([py, str(cfg.ROOT / "scripts" / "seed_demo.py")], env=env)

    print(f"2/5 Khởi chạy server demo trên {cfg.DEMO_BASE_URL} ...")
    server_proc = subprocess.Popen(
        [py, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(cfg.DEMO_PORT), "--log-level", "warning"],
        cwd=str(cfg.ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    deadline = time.monotonic() + 25.0
    while time.monotonic() < deadline:
        if server_proc.poll() is not None:
            err = server_proc.stderr.read().decode("utf-8", errors="replace") if server_proc.stderr else ""
            raise RuntimeError(f"Uvicorn thoát sớm: {err}")
        try:
            r = httpx.get(f"{cfg.DEMO_BASE_URL}/api/health", timeout=2.0)
            if r.status_code == 200 and r.json().get("data", {}).get("database") is True:
                break
        except Exception:
            pass
        time.sleep(0.4)
    else:
        server_proc.terminate()
        raise RuntimeError("Hết thời gian chờ server demo /api/health.")

    seed_cover_images()
    return server_proc


def seed_cover_images() -> None:
    """Đính kèm ảnh bìa mẫu vào một số ký ức công khai để danh sách khám phá lên hình đẹp."""
    cover_map = {
        cfg.USER_EMAIL: (cfg.USER_PASS, {
            "Chiều thu Hà Nội": "cover_hoanghon.jpg",
            "Sương sớm Đà Lạt": "cover_dalat.jpg",
            "Đồi chè Cầu Đất": "cover_dalat.jpg",
            "Phố cổ Hội An": "cover_hoian.jpg",
        }),
        "binh@example.com": ("Matkhau123", {
            "Vịnh Hạ Long": "cover_bien.jpg",
            "Biển Mỹ Khê": "cover_bien.jpg",
        }),
    }
    with httpx.Client(base_url=cfg.DEMO_BASE_URL, timeout=10.0) as client:
        for email, (password, titles) in cover_map.items():
            login = client.post("/api/auth/login", json={"email": email, "password": password})
            login.raise_for_status()
            token = login.json()["data"]["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            mine = client.get("/api/memories/mine", params={"page_size": 50}, headers=headers)
            mine.raise_for_status()
            for item in mine.json()["data"]["items"]:
                img_name = titles.get(item["title"])
                if not img_name:
                    continue
                img_path = cfg.ASSETS_DIR / img_name
                with img_path.open("rb") as f:
                    resp = client.post(
                        f"/api/memories/{item['id']}/images",
                        headers=headers,
                        files=[("images", (img_name, f, "image/jpeg"))],
                    )
                    resp.raise_for_status()


def launch_browser(p):
    for channel in ("msedge", "chrome"):
        try:
            return p.chromium.launch(
                channel=channel,
                headless=True,
                args=["--disable-gpu-vsync", "--autoplay-policy=no-user-gesture-required"],
            )
        except Exception:
            continue
    return p.chromium.launch(headless=True)


def render_card_video(page: Page, url: str, duration: float, out_mp4: Path) -> None:
    """Chụp từng frame deterministic từ HTML/GSAP OpenDesign ở 1920x1080 30fps và pipe vào FFmpeg."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    page.set_viewport_size({"width": cfg.WIDTH, "height": cfg.HEIGHT})
    page.goto(url, wait_until="networkidle")
    page.evaluate("() => document.fonts.ready")
    page.wait_for_timeout(200)

    total_frames = int(round(duration * cfg.FPS))
    cmd = [
        ffmpeg, "-y",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-framerate", str(cfg.FPS),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "16",
        "-pix_fmt", "yuv420p",
        "-r", str(cfg.FPS),
        "-video_track_timescale", "30000",
        str(out_mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None

    for i in range(total_frames):
        t = i / cfg.FPS
        page.evaluate(
            """(t) => new Promise((resolve) => {
                if (window.__timelines && window.__timelines.main) {
                    window.__timelines.main.pause();
                    window.__timelines.main.time(t);
                } else {
                    for (const anim of document.getAnimations()) {
                        anim.pause();
                        anim.currentTime = t * 1000;
                    }
                }
                requestAnimationFrame(() => requestAnimationFrame(resolve));
            })""",
            t,
        )
        png = page.screenshot(type="png")
        proc.stdin.write(png)

    proc.stdin.close()
    stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"FFmpeg lỗi khi xuất {out_mp4.name}:\n{stderr}")


def render_lower_thirds(page: Page, od_url_base: str) -> None:
    cfg.BADGES_DIR.mkdir(parents=True, exist_ok=True)
    page.set_viewport_size({"width": cfg.WIDTH, "height": cfg.HEIGHT})
    for seg in cfg.SEGMENTS:
        if not seg.badge_title:
            continue
        qs = urllib.parse.urlencode({
            "tag": seg.badge_tag or "",
            "title": seg.badge_title or "",
            "subtitle": seg.badge_subtitle or "",
        })
        page.goto(f"{od_url_base}/lower-third.html?{qs}", wait_until="networkidle")
        page.evaluate("() => document.fonts.ready")
        page.wait_for_timeout(150)
        page.screenshot(path=str(cfg.BADGES_DIR / f"{seg.id}.png"), omit_background=True)


class SmoothActor:
    def __init__(self, page: Page):
        self.page = page
        self.x = 960.0
        self.y = 540.0
        page.mouse.move(self.x, self.y)

    def move_to(self, tx: float, ty: float, steps: int = 20, duration_s: float = 0.38) -> None:
        sx, sy = self.x, self.y
        step_sleep = max(0.008, duration_s / max(steps, 1))
        for i in range(1, steps + 1):
            u = i / steps
            ease = 4 * u * u * u if u < 0.5 else 1 - ((-2 * u + 2) ** 3) / 2
            nx = sx + (tx - sx) * ease
            ny = sy + (ty - sy) * ease
            self.page.mouse.move(nx, ny)
            time.sleep(step_sleep)
        self.x, self.y = tx, ty

    def click_locator(self, locator, pause_after: float = 0.25) -> None:
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        if not box:
            locator.click()
            return
        tx = box["x"] + box["width"] / 2
        ty = box["y"] + box["height"] / 2
        self.move_to(tx, ty)
        time.sleep(0.1)
        self.page.mouse.click(tx, ty)
        if pause_after > 0:
            time.sleep(pause_after)

    def type_locator(self, locator, text: str, delay_ms: int = 55, clear_first: bool = True) -> None:
        self.click_locator(locator, pause_after=0.12)
        if clear_first:
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Backspace")
        self.page.keyboard.type(text, delay=delay_ms)
        time.sleep(0.15)


def wait_tiles_ready(page: Page, min_tiles: int = 6, timeout_ms: int = 8000) -> None:
    page.wait_for_function(
        f"() => document.querySelectorAll('.leaflet-tile-loaded').length >= {min_tiles}",
        timeout=timeout_ms,
    )


def record_live_app(browser) -> dict:
    cfg.RAW_DIR.mkdir(parents=True, exist_ok=True)
    for old in cfg.RAW_DIR.glob("*.webm"):
        old.unlink()

    context = browser.new_context(
        viewport={"width": cfg.WIDTH, "height": cfg.HEIGHT},
        record_video_dir=str(cfg.RAW_DIR),
        record_video_size={"width": cfg.WIDTH, "height": cfg.HEIGHT},
        locale="vi-VN",
    )
    context.add_init_script(CURSOR_INIT_SCRIPT)
    page = context.new_page()
    actor = SmoothActor(page)

    marks: dict[str, float] = {}
    marks["video_new_page_at"] = time.monotonic()

    # Tải sẵn trang bản đồ + bản đồ nền trước khi bắt đầu ghi dấu đoạn 1b
    page.goto(f"{cfg.DEMO_BASE_URL}/ban-do", wait_until="networkidle")
    page.locator("#explore-list .memory-card").first.wait_for(timeout=15000)
    wait_tiles_ready(page, min_tiles=6)
    # Chờ nhẹ map-hint ẩn hoặc làm mờ tự nhiên không che màn hình
    page.evaluate("() => { const h = document.getElementById('map-hint'); if (h) h.hidden = true; }")
    time.sleep(0.4)

    # ===== PHÂN ĐOẠN 1b: Toàn cảnh bản đồ công khai (mục tiêu ~7s) =====
    marks["s1_map_start"] = time.monotonic()
    actor.move_to(1150, 500, steps=18, duration_s=0.45)
    actor.click_locator(page.locator(".leaflet-control-zoom-in"), pause_after=1.1)
    actor.click_locator(page.locator(".leaflet-control-zoom-in"), pause_after=1.1)
    actor.click_locator(page.locator(".leaflet-control-zoom-out"), pause_after=1.2)
    # Căn giữa Đà Lạt để chuẩn bị chuyển mượt sang phân đoạn 2
    page.evaluate("() => MemoryMap.flyTo(11.9416, 108.4383, 11)")
    time.sleep(1.3)

    # ===== PHÂN ĐOẠN 2: Khám phá - explore (mục tiêu ~15s) =====
    marks["s2_explore_start"] = time.monotonic()
    dalat_pin = page.locator('.map-pin--public[title="Sương sớm Đà Lạt"]').first
    dalat_pin.wait_for(timeout=8000)
    actor.click_locator(dalat_pin, pause_after=0.4)
    page.locator(".pin-popup").wait_for(timeout=5000)
    time.sleep(2.1)  # Cho thấy tên tác giả 'An Nguyễn', ẩn hoàn toàn email
    actor.click_locator(page.locator(".leaflet-popup-close-button"), pause_after=0.3)

    # Lọc theo hashtag #dalat
    dalat_chip = page.locator("#explore-tags button.chip", has_text="#dalat").first
    actor.click_locator(dalat_chip, pause_after=1.7)

    # Lọc theo khu vực tỉnh/thành Lâm Đồng
    region_select = page.locator('#explore-filter select[name="region"]')
    actor.click_locator(region_select, pause_after=0.15)
    region_select.select_option("lam-dong")
    time.sleep(1.8)

    # Xóa lọc và gõ từ khóa không dấu vào ô tìm kiếm
    actor.click_locator(page.locator('#explore-filter button[type="reset"]'), pause_after=0.5)
    actor.type_locator(page.locator('#explore-filter input[name="q"]'), "ho guom", delay_ms=70)
    actor.click_locator(page.locator('#explore-filter button[type="submit"]'), pause_after=2.1)

    # ===== PHÂN ĐOẠN 3: Tài khoản - accounts (mục tiêu ~15s) =====
    marks["s3_accounts_start"] = time.monotonic()
    actor.click_locator(page.locator('#account-menu a:has-text("Đăng nhập")'), pause_after=0.3)
    page.wait_for_url("**/accounts/login.html*", timeout=10000)
    page.wait_for_load_state("networkidle")
    time.sleep(1.2)

    # Rê chuột qua Google & Facebook OAuth để cho thấy đủ 3 tùy chọn
    google_btn = page.locator('[data-provider="google"]')
    gbox = google_btn.bounding_box()
    if gbox:
        actor.move_to(gbox["x"] + gbox["width"] / 2, gbox["y"] + gbox["height"] / 2, duration_s=0.45)
        time.sleep(1.0)
    fb_btn = page.locator('[data-provider="facebook"]')
    fbox = fb_btn.bounding_box()
    if fbox:
        actor.move_to(fbox["x"] + fbox["width"] / 2, fbox["y"] + fbox["height"] / 2, duration_s=0.45)
        time.sleep(1.0)

    actor.type_locator(page.locator('input[name="email"]'), cfg.USER_EMAIL, delay_ms=55)
    actor.type_locator(page.locator('input[name="password"]'), cfg.USER_PASS, delay_ms=55)
    actor.click_locator(page.locator('form button[type="submit"]'), pause_after=0.2)

    page.wait_for_url("**/ban-do*", timeout=12000)
    page.locator(".account-menu__name").wait_for(timeout=10000)
    wait_tiles_ready(page, min_tiles=6)
    page.evaluate("() => { const h = document.getElementById('map-hint'); if (h) h.hidden = true; }")
    name_box = page.locator(".account-trigger").bounding_box()
    if name_box:
        actor.move_to(name_box["x"] + name_box["width"] / 2, name_box["y"] + name_box["height"] / 2, duration_s=0.5)
    time.sleep(2.1)

    # ===== PHÂN ĐOẠN 4: Ký ức, Media & Quyền riêng tư (mục tiêu ~25s) =====
    marks["s4_memories_start"] = time.monotonic()
    actor.click_locator(page.locator('button.tab[data-tab="mine"]'), pause_after=0.4)
    actor.click_locator(page.locator("#mine-new"), pause_after=0.4)
    page.locator("#memory-form").wait_for(timeout=8000)

    # Đưa tâm bản đồ tới Hồ Tuyền Lâm Đà Lạt trước khi chọn điểm
    page.evaluate("() => MemoryMap.instance.setView([11.9055, 108.48], 13)")
    time.sleep(0.6)
    actor.click_locator(page.locator("#pick-on-map"), pause_after=0.25)
    # Click giữa vùng bản đồ còn trống bên trái Drawer (x=920, y=540)
    actor.move_to(920, 540, steps=20, duration_s=0.45)
    page.mouse.click(920, 540)
    time.sleep(1.3)

    # Đảm bảo tên địa điểm sắc nét (phòng trường hợp Nominatim chậm)
    place_input = page.locator('#memory-form input[name="place_name"]')
    current_place = (place_input.input_value() or "").strip()
    if not current_place or current_place.startswith("Vị trí"):
        actor.type_locator(place_input, "Hồ Tuyền Lâm, Đà Lạt", delay_ms=35)

    actor.type_locator(page.locator('#memory-form input[name="title"]'), "Hoàng hôn Hồ Tuyền Lâm", delay_ms=42)
    page.locator('#memory-form input[name="memory_date"]').fill("2025-10-12")
    actor.type_locator(
        page.locator('#memory-form textarea[name="content"]'),
        "Ánh chiều buông xuống mặt hồ phẳng lặng giữa rừng thông Đà Lạt.",
        delay_ms=26,
    )

    page.locator("#drawer").evaluate("el => el.scrollTo({ top: 380, behavior: 'smooth' })")
    time.sleep(0.35)
    actor.type_locator(page.locator('#memory-form input[name="hashtags"]'), "#dalat #phuot", delay_ms=48)

    # Đính kèm 2 ảnh và 1 video ngắn
    page.locator("#image-grid input[type='file']").set_input_files([
        str(cfg.ASSETS_DIR / "tuyen_lam_1.jpg"),
        str(cfg.ASSETS_DIR / "tuyen_lam_2.jpg"),
    ])
    time.sleep(0.45)
    page.locator("#video-box input[type='file']").set_input_files(
        str(cfg.ASSETS_DIR / "dalat_sunset_demo.mp4")
    )
    time.sleep(0.45)

    # Gắn vào chuyến đi 'Đà Lạt tháng 10' để hiển thị ở phân đoạn 5
    page.locator("#drawer").evaluate("el => el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })")
    time.sleep(0.3)
    trip_chk = page.locator('#trip-checks label:has-text("Đà Lạt tháng 10") input[type="checkbox"]').first
    if trip_chk.count() > 0:
        actor.click_locator(trip_chk, pause_after=0.25)

    actor.click_locator(page.locator("#memory-save"), pause_after=0.2)
    page.locator(".memory-detail__title").wait_for(timeout=15000)
    page.wait_for_function(
        "() => [...document.querySelectorAll('.memory-detail .gallery img')].filter(i => i.complete && i.naturalWidth > 0).length >= 2",
        timeout=10000,
    )
    video_loc = page.locator(".memory-detail video")
    video_loc.wait_for(timeout=10000)
    page.wait_for_function(
        "() => { const v = document.querySelector('.memory-detail video'); return v && v.src && v.readyState >= 1; }",
        timeout=10000,
    )
    page.locator("#drawer").evaluate("el => el.scrollTo({ top: 200, behavior: 'smooth' })")
    page.evaluate("() => { const v = document.querySelector('.memory-detail video'); if (v) { v.muted = true; v.play().catch(()=>{}); } }")
    time.sleep(2.8)

    # Chuyển từ Riêng tư -> Công khai ngay trên giao diện
    actor.click_locator(page.locator('.drawer__footer button:has-text("Công khai")'), pause_after=0.35)
    page.locator(".modal").wait_for(timeout=5000)
    actor.click_locator(page.locator('.modal button:has-text("Công khai")'), pause_after=0.4)
    page.locator(".memory-detail__meta .badge--public").wait_for(timeout=8000)
    time.sleep(1.5)

    # ===== PHÂN ĐOẠN 5: Chuyến đi & Dòng thời gian (mục tiêu ~15s) =====
    marks["s5_trips_start"] = time.monotonic()
    actor.click_locator(page.locator('button.tab[data-tab="trips"]'), pause_after=0.5)
    trip_card = page.locator('#trip-list .trip-card:has-text("Đà Lạt tháng 10")').first
    trip_card.wait_for(timeout=8000)
    actor.click_locator(trip_card, pause_after=1.0)
    page.locator(".timeline li").first.wait_for(timeout=8000)
    time.sleep(1.4)
    page.locator("#drawer").evaluate("el => el.scrollTo({ top: 280, behavior: 'smooth' })")
    time.sleep(2.2)

    actor.click_locator(page.locator('.drawer__header button[aria-label="Đóng"]'), pause_after=0.35)
    actor.click_locator(page.locator('button.tab[data-tab="mine"]'), pause_after=0.45)

    year_select = page.locator('#mine-filter select[name="year"]')
    actor.click_locator(year_select, pause_after=0.15)
    year_select.select_option("2025")
    actor.click_locator(page.locator("#mine-filter details.filter-more summary"), pause_after=0.3)
    page.locator('#mine-filter input[name="date_from"]').fill("2025-10-01")
    page.locator('#mine-filter input[name="date_to"]').fill("2025-10-31")
    actor.click_locator(page.locator('#mine-filter button[type="submit"]'), pause_after=2.8)

    # ===== PHÂN ĐOẠN 6: Quản trị - admin (mục tiêu ~12s) =====
    marks["s6_admin_start"] = time.monotonic()
    actor.click_locator(page.locator(".account-trigger"), pause_after=0.25)
    actor.click_locator(page.locator('.account-dropdown button:has-text("Đăng xuất")'), pause_after=0.3)
    page.wait_for_url("**/accounts/login.html*", timeout=10000)
    page.wait_for_load_state("networkidle")

    actor.type_locator(page.locator('input[name="email"]'), cfg.ADMIN_EMAIL, delay_ms=42)
    actor.type_locator(page.locator('input[name="password"]'), cfg.ADMIN_PASS, delay_ms=42)
    actor.click_locator(page.locator('form button[type="submit"]'), pause_after=0.2)
    page.wait_for_url("**/ban-do*", timeout=10000)
    page.goto(f"{cfg.DEMO_BASE_URL}/admin/", wait_until="networkidle")
    page.locator("#admin-memories tr").first.wait_for(timeout=10000)

    actor.type_locator(page.locator('.admin-search[data-target="memories"] input[name="q"]'), "Hoàng hôn", delay_ms=42)
    actor.click_locator(page.locator('.admin-search[data-target="memories"] button[type="submit"]'), pause_after=0.6)
    hide_btn = page.locator("#admin-memories tr").first.get_by_role("button", name="Ẩn", exact=True)
    hide_btn.wait_for(timeout=6000)
    actor.click_locator(hide_btn, pause_after=0.3)

    page.locator(".modal textarea").wait_for(timeout=5000)
    actor.type_locator(page.locator(".modal textarea"), "Kiểm duyệt nội dung thử nghiệm", delay_ms=28, clear_first=False)
    actor.click_locator(page.locator('.modal button[type="submit"]'), pause_after=0.7)
    page.locator("#admin-memories .badge--hidden").first.wait_for(timeout=6000)
    time.sleep(0.8)

    actor.click_locator(page.locator('.admin-tabs button[data-tab="actions"]'), pause_after=0.5)
    page.locator("#admin-actions tr").first.wait_for(timeout=6000)
    time.sleep(2.2)

    marks["s6_admin_end"] = time.monotonic()

    video = page.video
    assert video is not None
    raw_path = Path(video.path())
    page.close()
    context.close()
    marks["close_time"] = time.monotonic()

    shutil.copy2(raw_path, cfg.RAW_SCREEN_WEBM)
    return marks


def main() -> None:
    if not (cfg.OD_CARDS_DIR / "intro-card.html").exists():
        raise FileNotFoundError(f"Thiếu thẻ đồ họa OpenDesign trong {cfg.OD_CARDS_DIR}")

    cfg.WORK_DIR.mkdir(parents=True, exist_ok=True)
    server_proc = prepare_isolated_db_and_server()
    od_server, od_port = start_static_server(cfg.OD_CARDS_DIR)
    od_url_base = f"http://127.0.0.1:{od_port}"

    try:
        with sync_playwright() as p:
            browser = launch_browser(p)
            try:
                print("3/5 Render Intro Card (3s), Outro Card (8s) và Lower-Third Badges từ OpenDesign...")
                card_ctx = browser.new_context(viewport={"width": cfg.WIDTH, "height": cfg.HEIGHT}, locale="vi-VN")
                card_page = card_ctx.new_page()
                render_card_video(card_page, f"{od_url_base}/intro-card.html", 3.0, cfg.WORK_DIR / "intro_3s.mp4")
                render_card_video(card_page, f"{od_url_base}/outro-card.html", 8.0, cfg.WORK_DIR / "outro_8s.mp4")
                render_lower_thirds(card_page, od_url_base)
                card_ctx.close()

                print("4/5 Quay màn hình ứng dụng thực tế qua 6 phân đoạn live...")
                marks = record_live_app(browser)
            finally:
                browser.close()
    finally:
        od_server.shutdown()
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()

    cfg.MARKS_JSON.write_text(json.dumps(marks, indent=2), encoding="utf-8")
    print(f"5/5 Hoàn tất quay thô: {cfg.RAW_SCREEN_WEBM}")


if __name__ == "__main__":
    main()
