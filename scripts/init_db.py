"""Tạo database từ database/schema.sql + seed_regions.sql bằng Python (thay cho chạy tay trong MySQL Workbench).

Thông tin MySQL và tên database lấy từ file .env (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME).

    python scripts/init_db.py              # tạo database nếu chưa có; chạy lại an toàn, không mất dữ liệu
    python scripts/init_db.py --xoa-cu     # XÓA database cũ (mất toàn bộ dữ liệu) rồi tạo lại từ đầu
    python scripts/init_db.py --ten ten_khac   # tạo database tên khác (vd cho kiểm thử)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import settings  # noqa: E402

SCHEMA = ROOT / "database" / "schema.sql"
SEED_REGIONS = ROOT / "database" / "seed_regions.sql"
SCHEMA_DB_NAME = "ban_do_ky_uc"  # tên database viết sẵn trong các file .sql


def statements(sql_text: str):
    """Tách file .sql thành từng câu lệnh, hiểu cú pháp DELIMITER của MySQL client (dùng cho trigger)."""
    delimiter, buffer = ";", []
    for line in sql_text.splitlines():
        if "'" not in line:  # bỏ chú thích cuối dòng "-- ..." (không đụng dòng có chuỗi ký tự)
            line = re.sub(r"\s--\s.*$", "", line)
        stripped = line.strip()
        match = re.match(r"(?i)^DELIMITER\s+(\S+)", stripped)
        if match:
            delimiter = match.group(1)
            continue
        if not buffer and (not stripped or stripped.startswith("--")):
            continue
        buffer.append(line)
        if stripped.endswith(delimiter):
            statement = "\n".join(buffer).rstrip()[: -len(delimiter)].strip()
            buffer = []
            if statement:
                yield statement


def run_file(cursor, path: Path, db_name: str) -> None:
    text = re.sub(rf"\b{SCHEMA_DB_NAME}\b", db_name, path.read_text(encoding="utf-8"))
    for statement in statements(text):
        cursor.execute(statement)


def connect():
    return pymysql.connect(
        host=settings.db_host, port=settings.db_port, user=settings.db_user,
        password=settings.db_password, charset="utf8mb4", autocommit=True,
    )


def init_database(db_name: str, drop_existing: bool = False) -> dict:
    """Tạo bảng, trigger, view và nạp 34 tỉnh/thành. Trả về số tỉnh/thành, trigger, bảng để in ra."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
        raise SystemExit(f"Tên database không hợp lệ: {db_name}")
    with connect() as conn, conn.cursor() as cursor:
        if drop_existing:
            cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
        run_file(cursor, SCHEMA, db_name)  # mọi CREATE đều IF NOT EXISTS / OR REPLACE nên chạy lại an toàn
        cursor.execute(f"SELECT COUNT(*) FROM `{db_name}`.regions")
        if cursor.fetchone()[0] == 0:
            run_file(cursor, SEED_REGIONS, db_name)
        cursor.execute(f"SELECT COUNT(*) FROM `{db_name}`.regions")
        regions = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=%s", (db_name,))
        triggers = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE'", (db_name,))
        tables = cursor.fetchone()[0]
    return {"regions": regions, "triggers": triggers, "tables": tables}


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo database Bản đồ Ký ức từ database/*.sql")
    parser.add_argument("--ten", default=settings.db_name, help="tên database (mặc định DB_NAME trong .env)")
    parser.add_argument("--xoa-cu", action="store_true", help="xóa database cũ trước khi tạo (MẤT DỮ LIỆU)")
    args = parser.parse_args()
    if args.xoa_cu:
        print(f"⚠️  Xóa database `{args.ten}` và tạo lại từ đầu...")
    result = init_database(args.ten, drop_existing=args.xoa_cu)
    print(f"Đã sẵn sàng `{args.ten}`: {result['tables']} bảng, {result['triggers']} trigger, {result['regions']} tỉnh/thành.")


if __name__ == "__main__":
    main()
