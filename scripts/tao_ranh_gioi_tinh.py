"""Dựng app/modules/explore/data/provinces.geojson (ranh giới 34 tỉnh/thành, đã rút gọn) cho US-EXP-003.

Nguồn: ThangLeQuoc/vietnamese-provinces-database (giấy phép MIT), thư mục
dataset-generation-scripts/resources/gis/geojson_11Mar2026/<số>_<tên>/province.geojson.
Tải 34 file province.geojson vào một thư mục, đặt tên <số>_<tên>.geojson (vd 26_tinh_lam_đong.geojson), rồi chạy:

    python scripts/tao_ranh_gioi_tinh.py <thư-mục-chứa-34-file>

Đường biên được rút gọn bằng Douglas-Peucker (sai số ~300 m) để file nhỏ, đủ để biết một tọa độ thuộc tỉnh nào.
Không cần thư viện ngoài.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "modules" / "explore" / "data" / "provinces.geojson"
SEED = ROOT / "database" / "seed_regions.sql"
TOLERANCE = 0.003  # độ (~300 m)
SOURCE = "ThangLeQuoc/vietnamese-provinces-database (MIT), geojson_11Mar2026"


def slugify(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def file_slug(name: str) -> str:
    """26_tinh_lam_đong → lam-dong; 1_thu_đo_ha_noi → ha-noi; 29_ho_chi_minh → tp-ho-chi-minh."""
    base = re.sub(r"^\d+_", "", name)
    base = re.sub(r"^(tinh|thu_đo)_", "", base)
    slug = slugify(base)
    return "tp-ho-chi-minh" if slug == "ho-chi-minh" else slug


def _perpendicular(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    return abs(dy * x - dx * y + x2 * y1 - y2 * x1) / (dx * dx + dy * dy) ** 0.5


def simplify(points, tolerance):
    """Douglas-Peucker không đệ quy (vòng ranh giới có thể hàng chục nghìn điểm)."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        best, index = 0.0, None
        for i in range(start + 1, end):
            distance = _perpendicular(points[i], points[start], points[end])
            if distance > best:
                best, index = distance, i
        if index is not None and best > tolerance:
            keep[index] = True
            stack += [(start, index), (index, end)]
    return [p for p, k in zip(points, keep) if k]


def simplify_ring(ring):
    # Vòng khép kín: tách đôi để Douglas-Peucker không gộp mất cả vòng
    half = len(ring) // 2
    out = simplify(ring[: half + 1], TOLERANCE)[:-1] + simplify(ring[half:], TOLERANCE)
    out = [[round(x, 4), round(y, 4)] for x, y in out]
    if out[0] != out[-1]:
        out.append(out[0])
    return out if len(out) >= 4 else None


def main(source_dir: str) -> None:
    names = dict(re.findall(r"\('([^']+)', '([^']+)'", SEED.read_text(encoding="utf-8")))
    slug_to_name = {slug: name for name, slug in names.items()}
    features, before, after = [], 0, 0
    for path in sorted(Path(source_dir).glob("*.geojson")):
        slug = file_slug(path.stem)
        if slug not in slug_to_name:
            raise SystemExit(f"Không khớp tỉnh/thành trong seed_regions.sql: {path.name} → {slug}")
        polygons = []
        for feature in json.loads(path.read_text(encoding="utf-8"))["features"]:
            geometry = feature["geometry"]
            parts = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
            for polygon in parts:
                before += sum(len(r) for r in polygon)
                outer = simplify_ring(polygon[0])
                if outer is None:
                    continue  # đảo quá nhỏ so với sai số
                holes = [h for h in (simplify_ring(r) for r in polygon[1:]) if h]
                polygons.append([outer, *holes])
                after += sum(len(r) for r in [outer, *holes])
        features.append({
            "type": "Feature",
            "properties": {"slug": slug, "name": slug_to_name[slug]},
            "geometry": {"type": "MultiPolygon", "coordinates": polygons},
        })
    if len(features) != len(slug_to_name):
        missing = sorted(set(slug_to_name) - {f["properties"]["slug"] for f in features})
        raise SystemExit(f"Thiếu {len(missing)} tỉnh/thành: {missing}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "source": SOURCE, "features": features},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(features)} tỉnh/thành, {before} → {after} điểm, {OUT.stat().st_size / 1024:.0f} KB → {OUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
