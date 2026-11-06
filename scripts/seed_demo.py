import sys
from datetime import date, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Memory, User

DEMO_PASSWORD = "Matkhau123"

DEMO_USERS = [
    {"email": "admin@bandokyuc.local", "display_name": "Quản trị viên", "role": "admin"},
    {"email": "an@example.com", "display_name": "An", "role": "user"},
]

DEMO_MEMORIES = [
    ("Hồ Xuân Hương buổi sớm", "Sương mù phủ mặt hồ, đi bộ một vòng rất thích.", date(2025, 10, 12), "Hồ Xuân Hương, Đà Lạt", 11.941900, 108.441700, "public"),
    ("Phố cổ Hội An lên đèn", "Thả hoa đăng trên sông Hoài.", date(2025, 6, 2), "Phố cổ Hội An", 15.877000, 108.326000, "public"),
    ("Chợ nổi Cái Răng", "Ăn hủ tiếu trên ghe lúc 6 giờ sáng.", date(2024, 12, 20), "Chợ nổi Cái Răng, Cần Thơ", 10.003900, 105.743500, "public"),
    ("Đèo Mã Pì Lèng", "Ký ức riêng tư, không hiện trên bản đồ cộng đồng.", date(2024, 9, 1), "Đèo Mã Pì Lèng, Hà Giang", 23.234400, 105.414600, "private"),
]


def get_or_create_user(db, email: str, display_name: str, role: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            display_name=display_name,
            role=role,
            password_hash=hash_password(DEMO_PASSWORD),
            email_verified_at=datetime.now(),
        )
        db.add(user)
        db.flush()
        print(f"Đã tạo tài khoản {email} ({role})")
    return user


def main() -> None:
    with SessionLocal() as db:
        users = [get_or_create_user(db, **item) for item in DEMO_USERS]
        owner = users[1]
        has_memories = db.scalar(select(Memory.id).where(Memory.user_id == owner.id).limit(1))
        if has_memories is None:
            for title, content, memory_date, place_name, latitude, longitude, visibility in DEMO_MEMORIES:
                db.add(
                    Memory(
                        user_id=owner.id,
                        title=title,
                        content=content,
                        memory_date=memory_date,
                        place_name=place_name,
                        latitude=latitude,
                        longitude=longitude,
                        visibility=visibility,
                    )
                )
            print(f"Đã tạo {len(DEMO_MEMORIES)} ký ức mẫu cho {owner.email}")
        db.commit()
    print(f"Mật khẩu của các tài khoản mẫu: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
