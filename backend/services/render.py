"""把 GeoJSON 向量圖畫成 PNG。

兩種輸出：
  render_overlay()  現況：衛星底圖 + OSM/視覺辨識向量（給使用者確認抓到什麼）
  render_design()   改善後：深色底圖 + 重繪的道路設計向量
"""

from __future__ import annotations

import base64
import io

from PIL import Image, ImageDraw, ImageFont

from services.geo import ImageFrame

# layer -> (顏色 RGBA, 線寬 px, 是否虛線, 圖例文字)
STYLES: dict[str, tuple[tuple[int, int, int, int], int, bool, str]] = {
    "roadway":        ((150, 150, 160, 200), 3, False, "車道中心線"),
    "sidewalk":       ((60, 200, 120, 255), 6, False, "人行道"),
    "crossing":       ((255, 255, 255, 255), 7, True, "斑馬線"),
    "crosswalk":      ((255, 255, 255, 255), 7, True, "斑馬線(視覺辨識)"),
    "kerb":           ((255, 160, 60, 255), 4, False, "緣石"),
    "corner_radius":  ((255, 160, 60, 255), 4, False, "轉角緣石"),
    "lane_marking":   ((255, 220, 60, 255), 3, True, "車道標線"),
    "stop_line":      ((255, 70, 70, 255), 6, False, "停止線"),
    "channelization": ((120, 200, 255, 255), 3, True, "槽化／導引"),
    "median":         ((190, 120, 255, 255), 5, False, "分隔島／庇護島"),
    "traffic":        ((255, 90, 200, 255), 0, False, "號誌／標誌"),
    "refuge_island":  ((190, 120, 255, 255), 5, False, "行人庇護島"),
    "bulb_out":       ((60, 255, 200, 255), 5, False, "人行道端點外推"),
}
_DEFAULT = ((200, 200, 200, 220), 3, False, "其他")

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msjh.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _iter_lines(geom: dict) -> list[list[list[float]]]:
    t = geom.get("type")
    c = geom.get("coordinates") or []
    if t == "LineString":
        return [c]
    if t == "MultiLineString":
        return list(c)
    if t == "Polygon":
        return [ring for ring in c]
    if t == "MultiPolygon":
        return [ring for poly in c for ring in poly]
    return []


def _dashed(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]],
            color, width: int, dash: int = 14, gap: int = 10) -> None:
    import math
    for i in range(len(pts) - 1):
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        seg = math.hypot(x2 - x1, y2 - y1)
        if seg < 1e-6:
            continue
        ux, uy = (x2 - x1) / seg, (y2 - y1) / seg
        pos = 0.0
        while pos < seg:
            end = min(pos + dash, seg)
            draw.line(
                [(x1 + ux * pos, y1 + uy * pos), (x1 + ux * end, y1 + uy * end)],
                fill=color, width=width,
            )
            pos = end + gap


def _draw_features(overlay: Image.Image, fc: dict, frame: ImageFrame) -> set[str]:
    draw = ImageDraw.Draw(overlay, "RGBA")
    used: set[str] = set()

    # 先畫底層（車道），再畫上層（人行道、標線），避免被蓋掉
    order = ["roadway", "kerb", "corner_radius", "median", "refuge_island",
             "channelization", "lane_marking", "stop_line", "sidewalk",
             "bulb_out", "crossing", "crosswalk", "traffic"]
    rank = {k: i for i, k in enumerate(order)}
    feats = sorted(fc.get("features", []),
                   key=lambda f: rank.get(f["properties"].get("layer", ""), 99))

    for f in feats:
        layer = f["properties"].get("layer", "")
        color, width, dash, _ = STYLES.get(layer, _DEFAULT)
        geom = f.get("geometry") or {}

        if geom.get("type") == "Point":
            lng, lat = geom["coordinates"]
            x, y = frame.to_px(lat, lng)
            draw.ellipse([x - 7, y - 7, x + 7, y + 7], fill=color,
                         outline=(0, 0, 0, 200), width=2)
            used.add(layer)
            continue

        for line in _iter_lines(geom):
            pts = []
            for lng, lat in line:
                pts.append(frame.to_px(lat, lng))
            if len(pts) < 2:
                continue
            if dash:
                _dashed(draw, pts, color, max(width, 1))
            else:
                draw.line(pts, fill=color, width=max(width, 1), joint="curve")
            used.add(layer)

    return used


def _legend(img: Image.Image, layers: set[str], title: str) -> None:
    draw = ImageDraw.Draw(img, "RGBA")
    f_title, f_item = _font(26), _font(20)

    items = [(l, STYLES.get(l, _DEFAULT)) for l in
             [k for k in STYLES if k in layers]]
    box_h = 52 + len(items) * 28
    box_w = 300
    x0, y0 = 16, 16
    draw.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=12,
                           fill=(12, 14, 20, 215), outline=(255, 255, 255, 60))
    draw.text((x0 + 16, y0 + 14), title, font=f_title, fill=(255, 255, 255, 255))

    y = y0 + 50
    for layer, (color, width, dash, label) in items:
        if dash:
            _dashed(draw, [(x0 + 18, y + 9), (x0 + 58, y + 9)], color, 5, dash=9, gap=6)
        else:
            draw.line([(x0 + 18, y + 9), (x0 + 58, y + 9)], fill=color, width=6)
        draw.text((x0 + 70, y), label, font=f_item, fill=(230, 232, 240, 255))
        y += 28


def _to_data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def render_overlay(base_png: bytes, fc: dict, frame: ImageFrame,
                   title: str = "現況向量圖") -> str:
    base = Image.open(io.BytesIO(base_png)).convert("RGBA")
    # 把衛星圖壓暗一點，向量線才看得清楚
    base = Image.blend(base, Image.new("RGBA", base.size, (0, 0, 0, 255)), 0.35)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    used = _draw_features(overlay, fc, frame)
    out = Image.alpha_composite(base, overlay)
    _legend(out, used, title)
    return _to_data_url(out)


def render_design(fc: dict, frame: ImageFrame, base_png: bytes | None = None,
                  title: str = "改善設計") -> str:
    if base_png is not None:
        base = Image.open(io.BytesIO(base_png)).convert("RGBA")
        base = Image.blend(base, Image.new("RGBA", base.size, (10, 12, 18, 255)), 0.72)
    else:
        base = Image.new("RGBA", (frame.width, frame.height), (14, 16, 22, 255))

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    used = _draw_features(overlay, fc, frame)
    out = Image.alpha_composite(base, overlay)
    _legend(out, used, title)
    return _to_data_url(out)
