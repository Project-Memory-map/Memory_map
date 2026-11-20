"""Chạy server trên database kiểm thử (cổng 8010), không đụng database/thư mục upload làm việc.

Chạy:  python tests/kiem_thu_tich_hop/chay_server.py
"""
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định không in được tiếng Việt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PORT = 8010

os.environ["DB_NAME"] = "ban_do_ky_uc_kiemthu"
os.environ["UPLOAD_DIR"] = str(HERE / "ket_qua" / "uploads")
os.environ.setdefault("APP_ENV", "dev")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    print(f"Server kiểm thử: http://127.0.0.1:{PORT}  (DB {os.environ['DB_NAME']})")
    uvicorn.run("app.main:app", host="127.0.0.1", port=PORT)
