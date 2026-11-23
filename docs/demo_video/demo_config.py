"""Cấu hình dùng chung cho pipeline quay và dựng Video Demo 100 giây "Bản đồ Ký ức"."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = Path(__file__).resolve().parent
WORK_DIR = DEMO_DIR / ".work"
ASSETS_DIR = DEMO_DIR / "assets"
OD_CARDS_DIR = DEMO_DIR / "od_cards"
BADGES_DIR = WORK_DIR / "badges"
AUDIO_DIR = WORK_DIR / "audio"
RAW_DIR = WORK_DIR / "raw"
CLIPS_DIR = WORK_DIR / "clips"
SUBTITLES_PNG_DIR = WORK_DIR / "subtitles_png"
VERIFY_DIR = WORK_DIR / "verify_frames"

OUTPUT_VIDEO = DEMO_DIR / "demo_ban_do_ky_uc_100s.mp4"
SUBTITLES_SRT = DEMO_DIR / "subtitles.srt"
MARKS_JSON = WORK_DIR / "recording_marks.json"
RAW_SCREEN_WEBM = WORK_DIR / "raw_screen.webm"

# Server & DB cô lập hoàn toàn khỏi DB làm việc `ban_do_ky_uc`
DEMO_DB = "ban_do_ky_uc_demo"
DEMO_PORT = 8012
DEMO_BASE_URL = f"http://127.0.0.1:{DEMO_PORT}"
DEMO_UPLOADS = WORK_DIR / "uploads"

WIDTH = 1920
HEIGHT = 1080
FPS = 30

USER_EMAIL = "an@example.com"
USER_PASS = "Matkhau123"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASS = "Admin12345"

DEFAULT_VOICE = "vi-VN-NamMinhNeural"
DEFAULT_RATE = "+5%"


@dataclass(frozen=True)
class SegmentSpec:
    id: str
    kind: str  # "card" | "live"
    duration: float
    badge_tag: str | None
    badge_title: str | None
    badge_subtitle: str | None
    narrations: tuple[str, ...]


SEGMENTS: tuple[SegmentSpec, ...] = (
    SegmentSpec(
        id="s1_intro",
        kind="card",
        duration=3.0,
        badge_tag=None,
        badge_title=None,
        badge_subtitle=None,
        narrations=(
            "Bản đồ Ký ức — lưu giữ hành trình trên không gian và thời gian.",
        ),
    ),
    SegmentSpec(
        id="s1_map",
        kind="live",
        duration=7.0,
        badge_tag="TỔNG QUAN",
        badge_title="Bản đồ Ký ức Công khai",
        badge_subtitle="Leaflet + OpenStreetMap · 34 tỉnh/thành",
        narrations=(
            "Trên bản đồ Leaflet công khai, các ghim ký ức khắp ba mươi tư tỉnh thành hiện lên trực quan.",
        ),
    ),
    SegmentSpec(
        id="s2_explore",
        kind="live",
        duration=15.0,
        badge_tag="MODULE 3 · EXPLORE",
        badge_title="Khám phá & Bộ lọc tức thì",
        badge_subtitle="Ẩn email tác giả · Hashtag OR · GeoJSON · FULLTEXT",
        narrations=(
            "Tại phân hệ Khám phá, nhấp vào ghim công khai hiện thông tin và tên tác giả, ẩn hoàn toàn email.",
            "Người dùng dễ dàng lọc theo hashtag Đà Lạt, chọn tỉnh Lâm Đồng và tìm từ khóa tức thì.",
        ),
    ),
    SegmentSpec(
        id="s3_accounts",
        kind="live",
        duration=15.0,
        badge_tag="MODULE 1 · ACCOUNTS",
        badge_title="Tài khoản & Xác thực đa phương thức",
        badge_subtitle="Email · Google & Facebook OAuth · JWT",
        narrations=(
            "Phân hệ Tài khoản hỗ trợ đăng nhập linh hoạt bằng Email, Google và Facebook, bảo mật với JWT.",
            "Đăng nhập tài khoản mẫu để mở bản đồ cá nhân cùng tên hiển thị ở góc trên màn hình.",
        ),
    ),
    SegmentSpec(
        id="s4_memories",
        kind="live",
        duration=25.0,
        badge_tag="MODULE 2 · MEMORIES",
        badge_title="Ký ức, Media & Quyền riêng tư",
        badge_subtitle="Ghim vị trí · Ảnh/Video HMAC · Riêng tư → Công khai",
        narrations=(
            "Ở phân hệ Ký ức, chọn vị trí trên bản đồ, nhập tiêu đề, nội dung, ngày và gắn hashtag Đà Lạt, phượt.",
            "Đính kèm ảnh sắc nét đã xóa tọa độ GPS cùng một đoạn video ngắn rồi lưu lại.",
            "Chi tiết ký ức tải ảnh qua đường dẫn có chữ ký HMAC và phát video mượt mà ngay trên giao diện.",
            "Bật công tắc chuyển nhanh từ Riêng tư sang Công khai để chia sẻ với cộng đồng.",
        ),
    ),
    SegmentSpec(
        id="s5_trips",
        kind="live",
        duration=15.0,
        badge_tag="MODULE 2 · TRIPS & TIMELINE",
        badge_title="Chuyến đi & Dòng thời gian",
        badge_subtitle="Lộ trình theo ngày tăng dần · Lọc theo năm & khoảng ngày",
        narrations=(
            "Mục Chuyến đi gom các ký ức thành hành trình trên bản đồ, sắp xếp theo ngày tăng dần.",
            "Bộ lọc dòng thời gian theo năm và khoảng ngày giúp tra cứu ký ức cá nhân nhanh chóng.",
        ),
    ),
    SegmentSpec(
        id="s6_admin",
        kind="live",
        duration=12.0,
        badge_tag="MODULE 4 · ADMIN",
        badge_title="Quản trị & Kiểm duyệt nội dung",
        badge_subtitle="Ẩn kèm lý do bắt buộc · Nhật ký kiểm duyệt bất biến",
        narrations=(
            "Phân hệ Quản trị cho phép tìm kiếm và kiểm duyệt mọi ký ức công khai trên hệ thống.",
            "Thao tác ẩn kèm lý do cập nhật trạng thái tức thì và lưu vào nhật ký kiểm duyệt.",
        ),
    ),
    SegmentSpec(
        id="s7_outro",
        kind="card",
        duration=8.0,
        badge_tag=None,
        badge_title=None,
        badge_subtitle=None,
        narrations=(
            "Bản đồ Ký ức — FastAPI, MySQL 8, Leaflet, đạt 238 test pytest vượt qua. Xin cảm ơn Quý Hội đồng!",
        ),
    ),
)

TOTAL_DURATION = sum(seg.duration for seg in SEGMENTS)  # 100.0s
