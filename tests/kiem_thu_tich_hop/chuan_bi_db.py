"""Tạo lại database kiểm thử riêng `ban_do_ky_uc_kiemthu` (dùng scripts/init_db.py).

Không đụng database làm việc `ban_do_ky_uc`. Thông tin MySQL lấy từ file .env của dự án.
Chạy:  python tests/kiem_thu_tich_hop/chuan_bi_db.py
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định không in được tiếng Việt

from scripts.init_db import init_database  # noqa: E402

TEST_DB = "ban_do_ky_uc_kiemthu"
UPLOAD_DIR = HERE / "ket_qua" / "uploads"


def main() -> None:
    result = init_database(TEST_DB, drop_existing=True)
    shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
    UPLOAD_DIR.mkdir(parents=True)
    print(f"Đã tạo {TEST_DB}: {result['regions']} tỉnh/thành, {result['triggers']} trigger. Thư mục upload: {UPLOAD_DIR}")


if __name__ == "__main__":
    main()
