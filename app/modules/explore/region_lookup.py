"""US-EXP-003: xác định tỉnh/thành của một tọa độ bằng ranh giới GeoJSON (không dựa vào tên Nominatim trả về).

Dữ liệu: data/provinces.geojson (34 tỉnh/thành sau sắp xếp 2025, dựng bằng scripts/tao_ranh_gioi_tinh.py).
Thuật toán: lọc theo khung bao rồi kiểm tra điểm-trong-đa-giác (ray casting, có xét lỗ). Ghim sát bờ biển hoặc
sát biên giới có thể lệch ra ngoài đường biên đã rút gọn, nên nếu không nằm trong tỉnh nào thì lấy tỉnh có
đường biên gần nhất trong phạm vi NEAR_DEGREES (~5 km). Ngoài phạm vi đó (vd Paris) → không gắn khu vực.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

DATA_FILE = Path(__file__).resolve().parent / "data" / "provinces.geojson"
NEAR_DEGREES = 0.05


class _Province:
    __slots__ = ("slug", "polygons", "bbox")

    def __init__(self, slug: str, polygons: list[list[list[tuple[float, float]]]]):
        self.slug = slug
        self.polygons = polygons
        xs = [x for polygon in polygons for x, _ in polygon[0]]
        ys = [y for polygon in polygons for _, y in polygon[0]]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))


@lru_cache(maxsize=1)
def _provinces() -> tuple[_Province, ...]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return tuple(
        _Province(
            feature["properties"]["slug"],
            [[[(x, y) for x, y in ring] for ring in polygon] for polygon in feature["geometry"]["coordinates"]],
        )
        for feature in data["features"]
    )


def _in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    x1, y1 = ring[-1]
    for x2, y2 in ring:
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
        x1, y1 = x2, y2
    return inside


def _in_polygon(x: float, y: float, polygon) -> bool:
    return _in_ring(x, y, polygon[0]) and not any(_in_ring(x, y, hole) for hole in polygon[1:])


def _segment_distance(x, y, x1, y1, x2, y2) -> float:
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return ((x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2) ** 0.5


def province_slug(latitude: float, longitude: float) -> str | None:
    """Slug tỉnh/thành chứa tọa độ (vd 'lam-dong'), hoặc None nếu ở ngoài Việt Nam."""
    x, y = float(longitude), float(latitude)
    near = [p for p in _provinces()
            if p.bbox[0] - NEAR_DEGREES <= x <= p.bbox[2] + NEAR_DEGREES
            and p.bbox[1] - NEAR_DEGREES <= y <= p.bbox[3] + NEAR_DEGREES]
    for province in near:
        if any(_in_polygon(x, y, polygon) for polygon in province.polygons):
            return province.slug

    best_slug, best = None, NEAR_DEGREES
    for province in near:
        for polygon in province.polygons:
            ring = polygon[0]
            for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
                distance = _segment_distance(x, y, x1, y1, x2, y2)
                if distance < best:
                    best_slug, best = province.slug, distance
    return best_slug


def region_id_for(db: Session, latitude: float, longitude: float) -> int | None:
    """regions.id của tọa độ; None nếu không thuộc tỉnh/thành nào (US-MEM-002 AC2)."""
    from app.modules.explore.models import Region  # tránh import vòng giữa các module

    slug = province_slug(latitude, longitude)
    if slug is None:
        return None
    return db.scalar(select(Region.id).where(Region.slug == slug))
