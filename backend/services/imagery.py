"""取得該範圍的衛星影像，作為 Gemini 視覺辨識的底圖。

兩個來源：
  google  Google Static Maps —— 影像品質最好，需要 API key + 帳單帳戶
  esri    Esri World Imagery 圖磚 —— 免金鑰免帳單，自己拼接

由 models.yaml 的 options.imagery_provider 決定（auto / google / esri）。
auto 表示：有 GOOGLE_MAPS_API_KEY 就用 Google，沒有就退到 Esri。

兩者都回傳 (PNG bytes, ImageFrame)，ImageFrame 讓後續的
「經緯度 ⇄ 影像像素」換算對兩種來源完全一致。
"""

from __future__ import annotations

import asyncio
import base64
import io
import math

import httpx
from PIL import Image

from config import (ESRI_ATTRIBUTION, ESRI_MAX_ZOOM, ESRI_MIN_ZOOM,
                    ESRI_PLACEHOLDER_GRAYNESS, ESRI_TILE_URL,
                    GOOGLE_MAPS_API_KEY, IMAGE_CONTEXT_RATIO, IMAGE_TARGET_PX,
                    OUTPUT_PX, STATIC_MAP_BASE_PX, STATIC_MAP_SCALE,
                    USER_AGENT, option)
from services.geo import ImageFrame, latlng_to_world, meters_per_pixel, pick_zoom

_STATIC_MAPS = "https://maps.googleapis.com/maps/api/staticmap"
_TILE = 256


def resolve_provider() -> str:
    """回傳實際會用的來源：'google' 或 'esri'。"""
    choice = str(option("imagery_provider", "auto") or "auto").lower()
    if choice == "google":
        return "google"
    if choice == "esri":
        return "esri"
    return "google" if GOOGLE_MAPS_API_KEY else "esri"


def attribution(provider: str) -> str:
    return ("Map data ©2026 Google" if provider == "google"
            else f"Imagery © {ESRI_ATTRIBUTION}")


async def fetch_satellite(lat: float, lng: float,
                          size_m: float) -> tuple[bytes, ImageFrame, str]:
    """回傳 (PNG bytes, 影像的地理參照, 實際使用的來源)。"""
    provider = resolve_provider()
    if provider == "google":
        png, frame = await _fetch_google(lat, lng, size_m)
    else:
        png, frame = await _fetch_esri(lat, lng, size_m)
    return png, frame, provider


# ---------------------------------------------------------------- Google ---

async def _fetch_google(lat: float, lng: float,
                        size_m: float) -> tuple[bytes, ImageFrame]:
    if not GOOGLE_MAPS_API_KEY:
        raise RuntimeError("缺少 GOOGLE_MAPS_API_KEY，請在專案根目錄的 .env 填入")

    zoom = pick_zoom(lat, size_m, STATIC_MAP_BASE_PX)
    params = {
        "center": f"{lat},{lng}",
        "zoom": str(zoom),
        "size": f"{STATIC_MAP_BASE_PX}x{STATIC_MAP_BASE_PX}",
        "scale": str(STATIC_MAP_SCALE),
        "maptype": "satellite",
        "format": "png",
        "key": GOOGLE_MAPS_API_KEY,
    }

    async with httpx.AsyncClient(timeout=40.0) as client:
        r = await client.get(_STATIC_MAPS, params=params)
        if r.status_code != 200:
            raise RuntimeError(
                f"Static Maps 回傳 {r.status_code}：{r.text[:300]}\n"
                "（403 通常代表專案沒啟用 Maps Static API 或沒綁帳單帳戶）")
        png = r.content

    img = Image.open(io.BytesIO(png))
    frame = ImageFrame(lat, lng, zoom, img.width, img.height, STATIC_MAP_SCALE)
    return png, frame


# ------------------------------------------------------------------ Esri ---

def _grayness(img: Image.Image) -> float:
    """回傳「幾乎沒有彩度」的像素比例。

    Esri 超出供圖範圍時不會回 404，而是回一張灰底寫著
    "Map data not yet available" 的佔位圖 —— 這種圖的彩度接近 0。
    實測：真實影像 ≤0.28、佔位圖 =1.00。
    """
    small = img.convert("RGB").resize((48, 48))
    px = list(small.getdata())
    flat = sum(1 for r, g, b in px if max(r, g, b) - min(r, g, b) <= 6)
    return flat / len(px)


def _tile_xy(lat: float, lng: float, zoom: int) -> tuple[int, int]:
    wx, wy = latlng_to_world(lat, lng)
    f = 2 ** zoom / _TILE
    return int(wx * f), int(wy * f)


async def _fetch_tile(client: httpx.AsyncClient, zoom: int, tx: int, ty: int):
    """回傳 PIL Image；HTTP 失敗或拿到佔位圖都回 None。"""
    n = 2 ** zoom
    if not (0 <= ty < n):
        return None
    try:
        r = await client.get(ESRI_TILE_URL.format(z=zoom, y=ty, x=tx % n))
        if r.status_code != 200:
            return None
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        if _grayness(img) >= ESRI_PLACEHOLDER_GRAYNESS:
            return None
        return img
    except Exception:
        return None


async def _best_zoom(client: httpx.AsyncClient, lat: float, lng: float,
                     start: int) -> int:
    """從 start 往下找第一個真的有影像的層級（用中心圖磚探測）。"""
    for zoom in range(start, ESRI_MIN_ZOOM - 1, -1):
        tx, ty = _tile_xy(lat, lng, zoom)
        if await _fetch_tile(client, zoom, tx, ty) is not None:
            return zoom
    raise RuntimeError(
        f"Esri 在此位置（{lat}, {lng}）從 zoom {start} 到 {ESRI_MIN_ZOOM} 都沒有影像。")


async def _fetch_esri(lat: float, lng: float,
                      size_m: float) -> tuple[bytes, ImageFrame]:
    """抓 Esri 圖磚拼成一張圖。

    ImageFrame 的 pps = 2^zoom * scale，scale 就是最後放大的倍率，
    所以座標換算跟 Google 那條路共用同一套邏輯。
    """
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        want = min(pick_zoom(lat, size_m, OUTPUT_PX), ESRI_MAX_ZOOM)
        zoom = await _best_zoom(client, lat, lng, want)

        # 只取「請求範圍 × 脈絡倍率」，讓路口填滿版面而不是縮在一大片市景中間
        mpp = meters_per_pixel(lat, zoom)
        native = int(math.ceil(size_m * IMAGE_CONTEXT_RATIO / mpp))
        native = max(256, min(native, 2048))

        f = 2 ** zoom
        cx, cy = (v * f for v in latlng_to_world(lat, lng))
        left, top = cx - native / 2, cy - native / 2

        tx0, ty0 = math.floor(left / _TILE), math.floor(top / _TILE)
        tx1 = math.floor((left + native - 1) / _TILE)
        ty1 = math.floor((top + native - 1) / _TILE)

        grid = [(tx, ty) for tx in range(tx0, tx1 + 1)
                for ty in range(ty0, ty1 + 1)]
        sem = asyncio.Semaphore(8)

        async def one(tx: int, ty: int):
            async with sem:
                return tx, ty, await _fetch_tile(client, zoom, tx, ty)

        tiles = await asyncio.gather(*[one(tx, ty) for tx, ty in grid])

    canvas = Image.new("RGB", (native, native), (20, 22, 28))
    got = 0
    for tx, ty, img in tiles:
        if img is None:
            continue
        canvas.paste(img, (int(tx * _TILE - left), int(ty * _TILE - top)))
        got += 1

    # 破圖的底圖會讓 Gemini 辨識出一堆不存在的線，寧可直接失敗也不要默默送出去
    if got < len(grid) * 0.7:
        raise RuntimeError(
            f"Esri 圖磚只拼到 {got}/{len(grid)} 張（zoom {zoom}），影像不完整。"
            "請稍後重試，或改用 Google Static Maps。")

    # 原生解析度不足時放大，讓模型看得清楚（不會多出細節，但版面一致）
    upscale = 1.0
    if native < IMAGE_TARGET_PX:
        upscale = min(IMAGE_TARGET_PX / native, 4.0)
        out_px = int(round(native * upscale))
        canvas = canvas.resize((out_px, out_px), Image.LANCZOS)
    else:
        out_px = native

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    frame = ImageFrame(lat, lng, zoom, out_px, out_px, scale=upscale)
    return buf.getvalue(), frame


def to_data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")
