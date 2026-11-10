import json
import logging
import math
import sqlite3
import time
from contextlib import closing
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import BASE_DIR


class GeocodeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )

    nominatim_url: str = "https://nominatim.openstreetmap.org/search"

    nominatim_user_agent: str = (
        "MemoryMap/1.0 "
        "(+https://github.com/Project-Memory-map/Memory_map)"
    )


settings = GeocodeSettings()
logger = logging.getLogger(__name__)

CACHE_FILE = BASE_DIR / "uploads" / "geocode-cache.sqlite3"

EMPTY_MESSAGE = (
    "Không tìm thấy địa điểm. "
    "Hãy thử tên khác hoặc chọn trực tiếp trên bản đồ"
)


def search_places(query):
    query = " ".join(query.split())

    if not 2 <= len(query) <= 200:
        raise HTTPException(
            400,
            "Nhập tên địa điểm từ 2 đến 200 ký tự",
        )

    endpoint = settings.nominatim_url.rstrip("/")

    if not endpoint.endswith("/search"):
        endpoint += "/search"

    key = endpoint + "|" + query.casefold()
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Cache và hạn mức dùng chung cho các worker trên cùng máy.
    with closing(sqlite3.connect(CACHE_FILE, timeout=10)) as cache, cache:
        cache.execute(
            "CREATE TABLE IF NOT EXISTS places "
            "(q TEXT PRIMARY KEY, expires REAL, data TEXT)"
        )
        cache.execute(
            "CREATE TABLE IF NOT EXISTS gate "
            "(id INTEGER PRIMARY KEY, last_call REAL)"
        )

        cache.execute("BEGIN IMMEDIATE")
        now = time.time()

        cache.execute(
            "DELETE FROM places WHERE expires <= ?",
            (now,),
        )

        row = cache.execute(
            "SELECT data FROM places WHERE q = ?",
            (key,),
        ).fetchone()

        if row:
            return json.loads(row[0])

        last = cache.execute(
            "SELECT last_call FROM gate WHERE id = 1"
        ).fetchone()

        if last and now - last[0] < 1.1:
            raise HTTPException(
                429,
                "Vui lòng chờ một giây rồi tìm lại",
            )

        cache.execute(
            "INSERT OR REPLACE INTO gate VALUES (1, ?)",
            (now,),
        )

    params = urlencode({
        "q": query,
        "format": "jsonv2",
        "limit": 5,
        "accept-language": "vi",
    })

    request = Request(
        endpoint + "?" + params,
        headers={
            "User-Agent": settings.nominatim_user_agent,
        },
    )

    try:
        with urlopen(request, timeout=8) as response:
            raw = json.load(response)

        if not isinstance(raw, list):
            raise ValueError("Dữ liệu địa điểm không hợp lệ")

        places = []

        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("Kết quả địa điểm không hợp lệ")

            lat = float(item["lat"])
            lng = float(item["lon"])

            if not (
                math.isfinite(lat)
                and math.isfinite(lng)
                and -90 <= lat <= 90
                and -180 <= lng <= 180
            ):
                continue

            label = str(item.get("display_name", ""))

            places.append({
                "name": str(
                    item.get("name") or label.split(",")[0]
                )[:255],
                "display_name": label,
                "latitude": lat,
                "longitude": lng,
            })

    except HTTPError as exc:
        logger.warning("NOMINATIM HTTP %s", exc.code)

        if exc.code == 429:
            message = (
                "Dịch vụ địa điểm đang giới hạn yêu cầu. "
                "Vui lòng thử lại sau."
            )
        elif exc.code == 403:
            message = (
                "Dịch vụ địa điểm từ chối truy cập. "
                "Cần kiểm tra cấu hình kết nối."
            )
        else:
            message = (
                "Dịch vụ địa điểm đang gặp lỗi. "
                "Vui lòng thử lại sau."
            )

        raise HTTPException(503, message) from exc

    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning(
            "LOI NOMINATIM: %s: %s",
            type(exc).__name__,
            exc,
        )

        raise HTTPException(
            503,
            "Không kết nối được dịch vụ tìm địa điểm. "
            "Hãy thử lại hoặc chọn trực tiếp trên bản đồ",
        ) from exc

    with closing(sqlite3.connect(CACHE_FILE, timeout=10)) as cache, cache:
        cache.execute(
            "INSERT OR REPLACE INTO places VALUES (?, ?, ?)",
            (
                key,
                time.time() + 86400,
                json.dumps(places, ensure_ascii=False),
            ),
        )

        cache.execute(
            "DELETE FROM places WHERE q IN "
            "(SELECT q FROM places "
            "ORDER BY expires DESC LIMIT -1 OFFSET 2000)"
        )

    return places        