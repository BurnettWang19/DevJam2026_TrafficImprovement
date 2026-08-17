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

# 米色底 + 深綠主調；琥珀與磚紅只用在需要一眼分辨的少數圖層。
# layer -> (顏色 RGBA, 線寬 px, 是否虛線, 圖例文字)
STYLES: dict[str, tuple[tuple[int, int, int, int], int, bool, str]] = {
    "roadway":        ((128, 138, 132, 210), 3, False, "車道中心線"),
    "sidewalk":       ((47, 93, 69, 255), 6, False, "人行道"),
    "crossing":       ((22, 49, 37, 255), 7, True, "斑馬線"),
    "crosswalk":      ((22, 49, 37, 255), 7, True, "斑馬線(影像辨識)"),
    "kerb":           ((184, 114, 28, 255), 4, False, "緣石"),
    "corner_radius":  ((184, 114, 28, 255), 4, False, "轉角緣石"),
    "lane_marking":   ((201, 143, 46, 255), 3, True, "車道標線"),
    "stop_line":      ((168, 65, 44, 255), 6, False, "停止線"),
    "channelization": ((79, 125, 140, 255), 3, True, "槽化／導引"),
    "median":         ((122, 92, 116, 255), 5, False, "分隔島／庇護島"),
    "traffic":        ((168, 65, 44, 255), 0, False, "號誌／標誌"),
    "refuge_island":  ((122, 92, 116, 255), 5, False, "行人庇護島"),
    "bulb_out":       ((69, 135, 106, 255), 5, False, "人行道端點外推"),
}
_DEFAULT = ((92, 102, 95, 220), 3, False, "其他")

# 介面用的米色 / 深綠
_CREAM = (244, 243, 238)
_INK = (30, 58, 43)
_INK_SOFT = (92, 102, 95)

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
    """米色的圖例卡片，樣式對齊前端。"""
    draw = ImageDraw.Draw(img, "RGBA")
    f_item = _font(19)

    items = [(l, STYLES.get(l, _DEFAULT)) for l in
             [k for k in STYLES if k in layers]]

    # 標題長度不定（重繪 Agent 自己命名），字級與卡片寬度都要跟著長度縮放
    max_w = max(320, int(img.width * 0.62))
    f_title = _font(25)
    for size in (25, 22, 19, 17):
        f_title = _font(size)
        if draw.textlength(title, font=f_title) <= max_w - 40:
            break
    title_w = draw.textlength(title, font=f_title)

    box_w = int(min(max(310, title_w + 40), max_w))
    box_h = 54 + len(items) * 28
    x0, y0 = 20, 20
    draw.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=16,
                           fill=(*_CREAM, 240), outline=(226, 223, 214, 255), width=2)
    draw.text((x0 + 20, y0 + 14), title, font=f_title, fill=(*_INK, 255))

    y = y0 + 52
    for layer, (color, width, dash, label) in items:
        if dash:
            _dashed(draw, [(x0 + 22, y + 9), (x0 + 60, y + 9)], color, 5, dash=9, gap=6)
        else:
            draw.line([(x0 + 22, y + 9), (x0 + 60, y + 9)], fill=color, width=6)
        draw.text((x0 + 72, y), label, font=f_item, fill=(*_INK_SOFT, 255))
        y += 28


def _annotate(img: Image.Image, annotations: list[dict]) -> None:
    """在圖上畫編號圓標 + 短標籤，讓不看工程圖的人也知道哪裡改了。

    annotations 每筆 {"point": [nx, ny], "label": "轉角外推"}，
    nx/ny 是 0~1 的正規化影像座標。
    """
    draw = ImageDraw.Draw(img, "RGBA")

    # 這張圖是唯一的說明來源（旁邊沒有對照清單），所以字要夠大。
    # 依影像寬度等比縮放，換底圖尺寸也不會跑掉。
    k = img.width / 1024.0
    R = int(34 * k)
    f_num, f_lab = _font(int(42 * k)), _font(int(36 * k))
    pad_x, pad_y = int(20 * k), int(15 * k)
    gap = int(14 * k)
    bh = f_lab.size + pad_y * 2          # 標籤高度固定，寬度才隨字數變
    W, H = img.width, img.height

    def overlaps(a, b) -> bool:
        return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

    def usable(box, taken) -> bool:
        if box[0] < 4 or box[1] < 4 or box[2] > W - 4 or box[3] > H - 4:
            return False
        return not any(overlaps(box, t) for t in taken)

    # 先解析出所有有效的標記，並把圓標本身佔的位置全部登記起來
    marks = []
    for i, a in enumerate(annotations, start=1):
        try:
            nx, ny = float(a["point"][0]), float(a["point"][1])
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        cx = min(max(nx, 0.04), 0.96) * W
        cy = min(max(ny, 0.04), 0.96) * H
        marks.append((i, cx, cy, str(a.get("label") or "")[:12]))

    taken = [(cx - R - 2, cy - R - 2, cx + R + 2, cy + R + 2)
             for _, cx, cy, _ in marks]

    # 由上而下、由左而右安排標籤，先到先得
    placed: list[tuple] = []
    for i, cx, cy, label in sorted(marks, key=lambda m: (m[2], m[1])):
        if not label:
            placed.append((i, cx, cy, None, ""))
            continue

        bw = draw.textlength(label, font=f_lab) + pad_x * 2

        # 右 → 左 → 下 → 上 → 四個斜角，取第一個不撞到東西的位置
        cands = [
            (cx + R + gap, cy - bh / 2), (cx - R - gap - bw, cy - bh / 2),
            (cx - bw / 2, cy + R + gap), (cx - bw / 2, cy - R - gap - bh),
            (cx + R * .7, cy + R * .7 + gap), (cx - bw - R * .7, cy + R * .7 + gap),
            (cx + R * .7, cy - R * .7 - gap - bh), (cx - bw - R * .7, cy - R * .7 - gap - bh),
        ]
        box = None
        for bx, by in cands:
            cand = (bx, by, bx + bw, by + bh)
            if usable(cand, taken):
                box = cand
                break

        # 都被佔滿就往上下逐步挪開，仍找不到位置才放棄標籤（編號還是會畫）
        if box is None:
            for step in range(1, 9):
                for dy in (step * (bh + gap * .6), -step * (bh + gap * .6)):
                    for bx in (cx + R + gap, cx - R - gap - bw, cx - bw / 2):
                        cand = (bx, cy - bh / 2 + dy, bx + bw, cy + bh / 2 + dy)
                        if usable(cand, taken):
                            box = cand
                            break
                    if box:
                        break
                if box:
                    break

        if box:
            taken.append((box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3))
        placed.append((i, cx, cy, box, label))

    # 先畫引線，再畫標籤與圓標，圖層順序才對
    for _, cx, cy, box, _ in placed:
        if box is None:
            continue
        bxc, byc = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        # 標籤沒有緊貼圓標時補一條細引線，避免看不出對應關係
        if abs(byc - cy) > bh * .7 or min(abs(box[0] - cx), abs(box[2] - cx)) > R + gap * 2:
            draw.line([(cx, cy), (bxc, byc)], fill=(*_INK, 130),
                      width=max(2, int(3 * k)))

    for i, cx, cy, box, label in placed:
        if box is not None:
            draw.rounded_rectangle(box, radius=(box[3] - box[1]) / 2,
                                   fill=(*_CREAM, 248), outline=(*_INK, 120),
                                   width=max(2, int(2 * k)))
            draw.text((box[0] + pad_x, box[1] + pad_y - f_lab.size * 0.12),
                      label, font=f_lab, fill=(*_INK, 255))

        draw.ellipse([cx - R, cy - R, cx + R, cy + R],
                     fill=(*_INK, 255), outline=(*_CREAM, 255),
                     width=max(3, int(4 * k)))
        n = str(i)
        nw = draw.textlength(n, font=f_num)
        draw.text((cx - nw / 2, cy - f_num.size * 0.62), n,
                  font=f_num, fill=(*_CREAM, 255))


def _to_data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def render_overlay(base_png: bytes, fc: dict, frame: ImageFrame,
                   title: str = "現況向量圖") -> str:
    base = Image.open(io.BytesIO(base_png)).convert("RGBA")
    # 往米色調淡，深綠的向量線才壓得住衛星影像的雜訊
    base = Image.blend(base, Image.new("RGBA", base.size, (*_CREAM, 255)), 0.34)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    used = _draw_features(overlay, fc, frame)
    out = Image.alpha_composite(base, overlay)
    _legend(out, used, title)
    return _to_data_url(out)


def render_annotated(base_png: bytes, fc: dict, frame: ImageFrame,
                     annotations: list[dict], title: str = "改動位置") -> str:
    """給一般民眾看的「哪裡改了」圖：淡底 + 設計向量 + 編號標記。"""
    base = Image.open(io.BytesIO(base_png)).convert("RGBA")
    base = Image.blend(base, Image.new("RGBA", base.size, (*_CREAM, 255)), 0.74)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    _draw_features(overlay, fc, frame)
    out = Image.alpha_composite(base, overlay)
    _annotate(out, annotations or [])
    return _to_data_url(out)


def render_design(fc: dict, frame: ImageFrame, base_png: bytes | None = None,
                  title: str = "改善設計",
                  annotations: list[dict] | None = None) -> str:
    if base_png is not None:
        base = Image.open(io.BytesIO(base_png)).convert("RGBA")
        # 設計圖淡得更多，讓重繪的幾何成為主角
        base = Image.blend(base, Image.new("RGBA", base.size, (*_CREAM, 255)), 0.68)
    else:
        base = Image.new("RGBA", (frame.width, frame.height), (*_CREAM, 255))

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    used = _draw_features(overlay, fc, frame)
    out = Image.alpha_composite(base, overlay)
    _legend(out, used, title)
    if annotations:
        _annotate(out, annotations)
    return _to_data_url(out)
