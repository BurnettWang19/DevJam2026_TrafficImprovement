"""用 Gemini 視覺辨識補上 OSM 沒有的線形資料（車道線、停止線、槽化線…）。

模型看的是 Static Maps 衛星影像，回傳影像上的正規化座標(0~1)，
這裡再用 ImageFrame 換算回經緯度，才能跟 OSM 資料疊成同一份向量圖層。
"""

from __future__ import annotations

import json

from services.gemini import call_json
from services.geo import ImageFrame

_ALLOWED = {
    "lane_marking",     # 車道分隔線 / 標線
    "stop_line",        # 停止線
    "channelization",   # 槽化線、導引線、路口偏心導引
    "crosswalk",        # 影像上看得到但 OSM 沒有的斑馬線
    "median",           # 中央分隔島 / 庇護島
    "corner_radius",    # 路口轉角緣石弧線
}


async def extract_lane_features(image_png: bytes, frame: ImageFrame,
                                osm_summary: dict) -> dict:
    """回傳 GeoJSON FeatureCollection，properties.source = 'gemini_vision'。"""
    user_text = json.dumps({
        "image_size_px": {"width": frame.width, "height": frame.height},
        "meters_per_pixel": round(frame.meters_per_pixel, 4),
        "square_center": {"lat": frame.center_lat, "lng": frame.center_lng},
        "osm_already_has": osm_summary,
        "allowed_layers": sorted(_ALLOWED),
    }, ensure_ascii=False)

    raw = await call_json(
        role="vision_lane_extract",
        prompt_file="10_vision_lane_extract.md",
        user_text=user_text,
        image_png=image_png,
        temperature=0.1,
    )

    items = raw.get("features", raw) if isinstance(raw, dict) else raw
    return norm_features_to_geojson(items, frame, _ALLOWED, source="gemini_vision")


def norm_features_to_geojson(items, frame: ImageFrame, allowed: set[str],
                             source: str) -> dict:
    """把模型回傳的「正規化影像座標折線」轉成經緯度 GeoJSON。

    視覺辨識與重繪 Agent 用的是同一套座標約定，所以共用這支。
    """
    features = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        layer = str(item.get("layer", "")).strip()
        if layer not in allowed:
            continue
        coords = []
        for p in item.get("points") or []:
            try:
                nx, ny = float(p[0]), float(p[1])
            except (TypeError, ValueError, IndexError, KeyError):
                continue
            if not (0.0 <= nx <= 1.0 and 0.0 <= ny <= 1.0):
                continue
            lat, lng = frame.norm_to_latlng(nx, ny)
            coords.append([lng, lat])
        if len(coords) < 2:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "layer": layer,
                "source": source,
                "confidence": item.get("confidence"),
                "note": item.get("note"),
                "label": item.get("label"),
                "addresses": item.get("addresses") or [],
            },
        })
    return {"type": "FeatureCollection", "features": features}


def merge(*collections: dict) -> dict:
    out: list[dict] = []
    for fc in collections:
        out.extend(fc.get("features", []))
    return {"type": "FeatureCollection", "features": out}
