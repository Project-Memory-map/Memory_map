import argparse
import sys
from pathlib import Path

import pymysql
from pymysql.constants import CLIENT

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.core.config import settings
from app.models import ALL_MODELS

SCHEMA_FILE = ROOT_DIR / "database" / "schema.sql"


def run_schema(reset: bool) -> None:
    connection = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        charset="utf8mb4",
        client_flag=CLIENT.MULTI_STATEMENTS,
    )
    try:
        with connection.cursor() as cursor:
            if reset:
                cursor.execute(f"DROP DATABASE IF EXISTS `{settings.db_name}`")
                print(f"Đã xóa cơ sở dữ liệu {settings.db_name}")
            cursor.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
            while cursor.nextset():
                pass
        connection.commit()
    finally:
        connection.close()


def check_tables() -> None:
    connection = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            database_tables = {row[0] for row in cursor.fetchall()}
    finally:
        connection.close()
    model_tables = {model.__tablename__ for model in ALL_MODELS}
    missing = sorted(model_tables - database_tables)
    if missing:
        print("Thiếu bảng so với model:", ", ".join(missing))
        sys.exit(1)
    print(f"Đã tạo xong {len(database_tables)} bảng: {', '.join(sorted(database_tables))}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo cơ sở dữ liệu Bản đồ Ký ức từ database/schema.sql")
    parser.add_argument("--reset", action="store_true", help="Xóa cơ sở dữ liệu cũ trước khi tạo lại")
    args = parser.parse_args()
    if not args.reset:
        print("Lưu ý: schema.sql dùng CREATE TABLE, nếu bảng đã tồn tại hãy chạy lại với --reset")
    run_schema(args.reset)
    check_tables()


if __name__ == "__main__":
    main()
