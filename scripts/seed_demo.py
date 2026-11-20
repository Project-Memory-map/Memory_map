"""Tạo dữ liệu mẫu để thử giao diện / demo: 1 quản trị viên, 2 người dùng, ký ức ở nhiều tỉnh, hashtag, chuyến đi.

Chạy sau scripts/init_db.py (database lấy từ DB_NAME trong .env):
    python scripts/seed_demo.py

Chạy lại an toàn: tài khoản mẫu đã có thì bỏ qua. Mật khẩu mẫu chỉ dùng ở máy phát triển.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.passwords import hash_password  # noqa: E402
from app.models import register_models  # noqa: E402
from app.modules.accounts.models import User  # noqa: E402
from app.modules.explore.region_lookup import region_id_for  # noqa: E402
from app.modules.memories.models import Hashtag, Memory, MemoryHashtag, Trip, TripMemory  # noqa: E402

ACCOUNTS = [
    # email, mật khẩu, tên hiển thị, vai trò
    ("admin@example.com", "Admin12345", "Quản trị viên", "admin"),
    ("an@example.com", "Matkhau123", "An Nguyễn", "user"),
    ("binh@example.com", "Matkhau123", "Bình Trần", "user"),
]

# chủ, tiêu đề, địa điểm, vĩ độ, kinh độ, ngày, công khai?, hashtag
MEMORIES = [
    ("an@example.com", "Chiều thu Hà Nội", "Hồ Gươm, Hà Nội", 21.0287, 105.8524, date(2025, 10, 12), True, ["hanoi", "muathu"]),
    ("an@example.com", "Sương sớm Đà Lạt", "Hồ Xuân Hương, Đà Lạt", 11.9416, 108.4383, date(2025, 10, 10), True, ["dalat", "phuot"]),
    ("an@example.com", "Đồi chè Cầu Đất", "Cầu Đất, Đà Lạt", 11.8410, 108.5700, date(2025, 10, 11), True, ["dalat"]),
    ("an@example.com", "Chợ đêm Đà Lạt", "Chợ Đà Lạt", 11.9429, 108.4371, date(2025, 10, 11), False, ["dalat", "amthuc"]),
    ("an@example.com", "Phố cổ Hội An", "Phố cổ Hội An", 15.8770, 108.3260, date(2024, 6, 2), True, ["hoian"]),
    ("binh@example.com", "Vịnh Hạ Long", "Vịnh Hạ Long, Quảng Ninh", 20.9101, 107.1839, date(2024, 8, 20), True, ["halong", "bien"]),
    ("binh@example.com", "Ruộng bậc thang Sa Pa", "Sa Pa, Lào Cai", 22.3364, 103.8438, date(2024, 9, 15), True, ["sapa", "phuot"]),
    ("binh@example.com", "Biển Mỹ Khê", "Biển Mỹ Khê, Đà Nẵng", 16.0610, 108.2470, date(2025, 5, 1), True, ["danang", "bien"]),
    ("binh@example.com", "Bến Ninh Kiều", "Bến Ninh Kiều, Cần Thơ", 10.0341, 105.7880, date(2025, 2, 14), True, ["cantho", "amthuc"]),
    ("binh@example.com", "Nhật ký riêng ở Sài Gòn", "Phố đi bộ Nguyễn Huệ", 10.7743, 106.7038, date(2025, 3, 8), False, []),
]

TRIP = ("an@example.com", "Đà Lạt tháng 10", "Ba ngày săn mây và đồi chè", ["Sương sớm Đà Lạt", "Đồi chè Cầu Đất", "Chợ đêm Đà Lạt"])


def main() -> None:
    register_models()
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == ACCOUNTS[0][0])):
            print(f"Dữ liệu mẫu đã có trong `{settings.db_name}`, bỏ qua.")
            return

        users = {}
        for email, password, name, role in ACCOUNTS:
            users[email] = User(email=email, password_hash=hash_password(password), display_name=name,
                                role=role, status="active", token_version=0, failed_login_count=0)
            db.add(users[email])
        db.flush()

        tags: dict[str, Hashtag] = {}
        memories = {}
        for email, title, place, lat, lng, day, public, hashtags in MEMORIES:
            memory = Memory(user_id=users[email].id, title=title, content=f"Kỷ niệm tại {place}.", memory_date=day,
                            place_name=place, latitude=lat, longitude=lng, region_id=region_id_for(db, lat, lng),
                            visibility="public" if public else "private", status="active")
            db.add(memory)
            db.flush()
            memories[title] = memory
            for name in hashtags:
                if name not in tags:
                    tags[name] = db.scalar(select(Hashtag).where(Hashtag.name == name)) or Hashtag(name=name)
                    db.add(tags[name])
                    db.flush()
                db.add(MemoryHashtag(memory_id=memory.id, hashtag_id=tags[name].id, source="manual"))

        owner, trip_name, description, titles = TRIP
        trip = Trip(user_id=users[owner].id, name=trip_name, description=description)
        db.add(trip)
        db.flush()
        for title in titles:
            db.add(TripMemory(trip_id=trip.id, memory_id=memories[title].id))
        db.commit()

    print(f"Đã tạo dữ liệu mẫu trong `{settings.db_name}`: {len(ACCOUNTS)} tài khoản, {len(MEMORIES)} ký ức, "
          f"{len(tags)} hashtag, 1 chuyến đi.")
    for email, password, name, role in ACCOUNTS:
        print(f"  {role:5}  {email:20} / {password}   ({name})")


if __name__ == "__main__":
    main()
