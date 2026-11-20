"""Gán tỉnh/thành (memories.region_id) cho các ký ức tạo trước khi có tính năng gán khu vực theo tọa độ.

Chạy một lần sau khi cập nhật code (an toàn khi chạy lại):
    python scripts/gan_khu_vuc.py            # chỉ ký ức chưa có khu vực
    python scripts/gan_khu_vuc.py --tat-ca   # tính lại cho mọi ký ức
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import select, update  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models import register_models  # noqa: E402
from app.modules.explore.region_lookup import region_id_for  # noqa: E402
from app.modules.memories.models import Memory  # noqa: E402


def main(recompute_all: bool) -> None:
    register_models()
    stats = Counter()
    with SessionLocal() as db:
        stmt = select(Memory)
        if not recompute_all:
            stmt = stmt.where(Memory.region_id.is_(None))
        for memory_id, latitude, longitude, current in db.execute(
            stmt.with_only_columns(Memory.id, Memory.latitude, Memory.longitude, Memory.region_id)
        ).all():
            region_id = region_id_for(db, latitude, longitude)
            stats["có khu vực" if region_id else "ngoài Việt Nam"] += 1
            if region_id != current:
                # Giữ nguyên updated_at: đây là bổ sung dữ liệu, người dùng không hề sửa ký ức
                db.execute(
                    update(Memory)
                    .where(Memory.id == memory_id)
                    .values(region_id=region_id, updated_at=Memory.updated_at)
                )
                stats["đã cập nhật"] += 1
        db.commit()
    print(dict(stats) or "Không có ký ức nào cần gán khu vực")


if __name__ == "__main__":
    main("--tat-ca" in sys.argv)
