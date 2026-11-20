"""US-MEM-001: tìm địa điểm theo tên (Nominatim /search) để tạo ký ức.

Dựa trên geocode.py của Lê Minh Trí (nhánh LeMinhTri_Sprint3), chuyển sang cấu trúc hiện tại:
gọi qua backend (đúng User-Agent), cache 24 giờ trong bộ nhớ, tối đa 1 yêu cầu/giây toàn hệ thống (BR-19).
"""
from __future__ import annotations

import logging
import math
import time
from collections import OrderedDict
from threading import Lock

import httpx

from app.core.config import settings
from app.modules.memories.services.nominatim_gate import NominatimBusy, wait_for_slot

logger = logging.getLogger("bandokyuc.geocode")

QUERY_MIN, QUERY_MAX = 2, 200
RESULT_LIMIT = 5
CACHE_SIZE = 1000
CACHE_SECONDS = 24 * 3600

_cache: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()
_lock = Lock()


class PlaceSearchError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def normalize_query(query: str | None) -> str:
    text = " ".join((query or "").split())
    if not QUERY_MIN <= len(text) <= QUERY_MAX:
        raise PlaceSearchError(422, f"Nhập tên địa điểm từ {QUERY_MIN} đến {QUERY_MAX} ký tự")
    return text


def _to_places(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        raise ValueError("Dữ liệu địa điểm không hợp lệ")
    places = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            lat, lng = float(item["lat"]), float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        label = str(item.get("display_name") or "")
        name = str(item.get("name") or label.split(",")[0]).strip()
        if name:
            places.append({"name": name[:255], "display_name": label or name, "latitude": lat, "longitude": lng})
    return places


def search_places(query: str | None) -> list[dict]:
    text = normalize_query(query)
    key = text.casefold()
    now = time.time()
    with _lock:
        cached = _cache.get(key)
        if cached and cached[0] > now:
            _cache.move_to_end(key)
            return cached[1]

    try:
        wait_for_slot()
        response = httpx.get(
            f"{settings.nominatim_url.rstrip('/')}/search",
            params={"q": text, "format": "jsonv2", "limit": RESULT_LIMIT, "accept-language": "vi"},
            headers={"User-Agent": settings.geocode_user_agent},
            timeout=settings.geocode_timeout_seconds,
        )
        if response.status_code == 429:
            raise PlaceSearchError(503, "Dịch vụ địa điểm đang giới hạn yêu cầu. Vui lòng thử lại sau.")
        response.raise_for_status()
        places = _to_places(response.json())
    except NominatimBusy:
        raise PlaceSearchError(503, "Nhiều người đang tìm địa điểm cùng lúc, vui lòng thử lại sau vài giây") from None
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Tìm địa điểm lỗi với '%s': %s", text, exc)
        raise PlaceSearchError(503, "Không kết nối được dịch vụ tìm địa điểm. Hãy thử lại hoặc chọn trực tiếp trên bản đồ") from exc

    with _lock:
        _cache[key] = (now + CACHE_SECONDS, places)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return places


def clear_cache() -> None:
    with _lock:
        _cache.clear()
