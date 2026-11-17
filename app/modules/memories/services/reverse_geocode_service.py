"""US-MEM-002: đổi tọa độ người dùng chọn trên bản đồ thành tên địa điểm (Nominatim reverse).

Gọi qua backend thay vì trình duyệt để đặt User-Agent đúng chính sách Nominatim và cache kết quả
(BR-19: hạn chế gọi dịch vụ bên ngoài). Lỗi mạng trả None, giao diện tự điền "Vị trí <lat>, <lng>".
"""
from __future__ import annotations

import logging
from collections import OrderedDict
from threading import Lock

import httpx

from app.core.config import settings

logger = logging.getLogger("bandokyuc.geocode")

CACHE_SIZE = 512
# 4 chữ số thập phân ≈ 11 m: hai lần nhấp gần nhau dùng chung một kết quả
CACHE_PRECISION = 4
NAME_KEYS = (
    "amenity", "tourism", "leisure", "building", "road", "neighbourhood",
    "quarter", "suburb", "village", "town", "city_district", "city", "county", "state",
)

_cache: OrderedDict[tuple[float, float], dict | None] = OrderedDict()
_lock = Lock()


class GeocodeUnavailable(Exception):
    """Không gọi được dịch vụ bản đồ (mạng lỗi, quá hạn, bị giới hạn)."""


def _short_name(item: dict) -> str | None:
    if item.get("name"):
        return item["name"]
    address = item.get("address") or {}
    for key in NAME_KEYS:
        if address.get(key):
            return address[key]
    display = item.get("display_name") or ""
    return display.split(",")[0].strip() or None


def _to_place(item: dict, latitude: float, longitude: float) -> dict | None:
    if not item or item.get("error"):
        return None
    name = _short_name(item)
    if not name:
        return None
    return {
        "name": name[:255],
        "display_name": item.get("display_name") or name,
        # Giữ đúng tọa độ người dùng chọn, không nhảy sang tọa độ của đối tượng Nominatim tìm được
        "latitude": latitude,
        "longitude": longitude,
    }


def _fetch(latitude: float, longitude: float) -> dict:
    try:
        response = httpx.get(
            f"{settings.nominatim_url.rstrip('/')}/reverse",
            params={
                "lat": latitude,
                "lon": longitude,
                "format": "jsonv2",
                "zoom": 18,
                "addressdetails": 1,
                "accept-language": "vi",
            },
            headers={"User-Agent": settings.geocode_user_agent},
            timeout=settings.geocode_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Reverse geocode lỗi tại %s,%s: %s", latitude, longitude, exc)
        raise GeocodeUnavailable from exc


def reverse_geocode(latitude: float, longitude: float) -> dict | None:
    key = (round(latitude, CACHE_PRECISION), round(longitude, CACHE_PRECISION))
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            cached = _cache[key]
            return None if cached is None else {**cached, "latitude": latitude, "longitude": longitude}

    place = _to_place(_fetch(latitude, longitude), latitude, longitude)

    with _lock:
        _cache[key] = place
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return place


def clear_cache() -> None:
    with _lock:
        _cache.clear()
