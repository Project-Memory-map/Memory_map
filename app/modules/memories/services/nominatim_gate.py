"""BR-19: gọi Nominatim tối đa 1 yêu cầu/giây cho toàn hệ thống (chính sách sử dụng của OpenStreetMap).

Dùng chung cho tìm địa điểm theo tên (place_search_service) và đổi tọa độ thành tên (reverse_geocode_service).
Thay vì báo lỗi khi quá nhịp, yêu cầu sau chờ tới lượt (tối đa MAX_WAIT_SECONDS) rồi mới gọi.
"""
from __future__ import annotations

import time
from threading import Lock

MIN_INTERVAL_SECONDS = 1.0
MAX_WAIT_SECONDS = 5.0

_lock = Lock()
_next_slot = 0.0


class NominatimBusy(Exception):
    """Quá nhiều người tìm cùng lúc, hàng chờ vượt MAX_WAIT_SECONDS."""


def wait_for_slot() -> None:
    global _next_slot
    with _lock:
        now = time.monotonic()
        slot = max(now, _next_slot)
        if slot - now > MAX_WAIT_SECONDS:
            raise NominatimBusy
        _next_slot = slot + MIN_INTERVAL_SECONDS
    delay = slot - time.monotonic()
    if delay > 0:
        time.sleep(delay)


def reset() -> None:
    """Cho test: bỏ hàng chờ."""
    global _next_slot
    with _lock:
        _next_slot = 0.0
