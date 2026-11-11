"""Dọn media đã hết thời gian lưu sau khi xóa mềm."""

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from app.core.database import SessionLocal
from app.core.storage import resolve_path
from app.models import register_models
from app.modules.memories.models import Media, Memory


def cleanup(db, apply=False, now=None):
    current_time = (
        now
        or datetime.now(timezone.utc).replace(tzinfo=None)
    )
    cutoff = current_time - timedelta(days=30)

    rows = db.execute(
        select(
            Media.file_path,
            Media.thumb_path,
        )
        .join(Memory)
        .where(Memory.deleted_at < cutoff)
    ).all()

    candidates = {
        name
        for row in rows
        for name in row
        if name
    }

    result = {
        "deleted": 0,
        "candidates": 0,
        "errors": 0,
    }

    for name in sorted(candidates):
        # Giữ lại tệp nếu một ký ức chưa đến hạn
        # hoặc chưa bị xóa vẫn đang tham chiếu tới nó.
        shared = db.scalar(
            select(Media.id)
            .join(Memory)
            .where(
                or_(
                    Media.file_path == name,
                    Media.thumb_path == name,
                ),
                or_(
                    Memory.deleted_at.is_(None),
                    Memory.deleted_at >= cutoff,
                ),
            )
            .limit(1)
        )

        if shared is not None:
            continue

        try:
            path = resolve_path(name)

            if not path.exists():
                continue

            if not path.is_file():
                raise ValueError(
                    "Không phải tệp thông thường"
                )

            result["candidates"] += 1

            if apply:
                path.unlink()
                result["deleted"] += 1

            prefix = "DELETED " if apply else "PREVIEW "
            print(prefix + name)

        except (OSError, ValueError) as exc:
            result["errors"] += 1
            print(f"ERROR {name}: {exc}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
    )
    args = parser.parse_args()

    register_models()

    with SessionLocal() as db:
        report = cleanup(
            db,
            apply=args.apply,
        )

    print(report)

    raise SystemExit(
        1 if report["errors"] else 0
    )