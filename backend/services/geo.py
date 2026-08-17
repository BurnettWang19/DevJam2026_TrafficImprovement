"""Web Mercator 座標換算。

負責三件事：
1. 由「中心點 + 正方形邊長(公尺)」算出 bbox。
2. 挑一個能把整個正方形塞進 Static Map 的 zoom。
3. 經緯度 <-> 影像像素 的雙向換算 —— Gemini 視覺辨識回傳的是影像上的
   正規化座標，必須換回經緯度才能跟 OSM 向量資料疊在一起。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

TILE = 256.0
_MPP_EQUATOR = 156543.03392804097  # zoom 0 時赤道上每 pixel 幾公尺


def latlng_to_world(lat: float, lng: float) -> tuple[float, float]:
    siny = math.sin(math.radians(lat))
    siny = min(max(siny, -0.9999), 0.9999)
    x = TILE * (0.5 + lng / 360.0)
    y = TILE * (0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi))
    return x, y


def world_to_latlng(x: float, y: float) -> tuple[float, float]:
    lng = (x / TILE - 0.5) * 360.0
    siny = math.tanh((0.5 - y / TILE) * 2 * math.pi)
    lat = math.degrees(math.asin(siny))
    return lat, lng


def meters_per_pixel(lat: float, zoom: float) -> float:
    return _MPP_EQUATOR * math.cos(math.radians(lat)) / (2.0 ** zoom)


def bbox_from_center(lat: float, lng: float, size_m: float) -> tuple[float, float, float, float]:
    """回傳 (south, west, north, east)。size_m 是正方形邊長。"""
    half = size_m / 2.0
    dlat = half / 111320.0
    dlng = half / (111320.0 * max(math.cos(math.radians(lat)), 1e-6))
    return (lat - dlat, lng - dlng, lat + dlat, lng + dlng)


def pick_zoom(lat: float, size_m: float, base_px: int) -> int:
    """挑最大的 zoom，同時保證 size_m 仍能塞進 base_px 個 base pixel。"""
    target_mpp = size_m / base_px
    z = math.floor(math.log2(_MPP_EQUATOR * math.cos(math.radians(lat)) / target_mpp))
    return int(min(max(z, 1), 21))


@dataclass
class ImageFrame:
    """一張已下載影像的地理參照資訊。"""

    center_lat: float
    center_lng: float
    zoom: int
    width: int   # 最終像素寬（已含 scale）
    height: int
    scale: float  # 相對於該 zoom 原生圖磚的像素密度倍率

    def __post_init__(self) -> None:
        self._pps = (2.0 ** self.zoom) * self.scale  # world unit -> pixel
        self._cx, self._cy = latlng_to_world(self.center_lat, self.center_lng)

    def to_px(self, lat: float, lng: float) -> tuple[float, float]:
        x, y = latlng_to_world(lat, lng)
        return (
            (x - self._cx) * self._pps + self.width / 2.0,
            (y - self._cy) * self._pps + self.height / 2.0,
        )

    def to_latlng(self, px: float, py: float) -> tuple[float, float]:
        x = (px - self.width / 2.0) / self._pps + self._cx
        y = (py - self.height / 2.0) / self._pps + self._cy
        return world_to_latlng(x, y)

    def norm_to_latlng(self, nx: float, ny: float) -> tuple[float, float]:
        """Gemini 回傳的 0..1 正規化影像座標 -> 經緯度。"""
        return self.to_latlng(nx * self.width, ny * self.height)

    def latlng_to_norm(self, lat: float, lng: float) -> tuple[float, float]:
        px, py = self.to_px(lat, lng)
        return px / self.width, py / self.height

    @property
    def meters_per_pixel(self) -> float:
        return _MPP_EQUATOR * math.cos(math.radians(self.center_lat)) / self._pps


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """兩個 (lat, lng) 之間的距離（公尺）。"""
    r = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = p2 - p1
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))
