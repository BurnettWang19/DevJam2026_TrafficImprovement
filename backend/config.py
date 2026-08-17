"""全域設定：讀 .env 與 models.yaml。

models.yaml 與 prompts/ 底下的檔案都是「每次呼叫時重讀」，
所以你可以在 server 跑著的時候直接改 prompt / 換模型，不用重啟。
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
PROMPTS_DIR = BACKEND_DIR / "prompts"
MODELS_YAML = BACKEND_DIR / "models.yaml"

# 經典案例資料夾。中英文名稱都認，且每次呼叫才解析 —— 資料夾改名不用改程式。
CASES_DIR_NAMES = ["example", "經典案例", "classic_cases"]


def cases_dir():
    for name in CASES_DIR_NAMES:
        path = ROOT_DIR / name
        if path.is_dir():
            return path
    return ROOT_DIR / CASES_DIR_NAMES[0]

load_dotenv(ROOT_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
GOOGLE_MAP_TILES_API_KEY = (
    os.getenv("GOOGLE_MAP_TILES_API_KEY", "").strip()
    or os.getenv("VITE_GOOGLE_MAP_TILES_API_KEY", "").strip()
)

# 依序嘗試，前一個失敗就換下一個。
# 注意：overpass-api.de 會用 406 擋掉沒有 User-Agent 的請求，見 services/osm.py。
# 只放「全球」實例。不要加 overpass.osm.ch —— 它只有瑞士的資料，
# 台灣的查詢會回 200 但 elements=0，安靜地給出空結果比直接失敗更難查。
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# 整份清單跑完算一輪；全掛就間隔重試，公共節點的 504 幾乎都是瞬間負載
OVERPASS_ROUNDS = 2

USER_AGENT = "IntersectionAudit/0.1 (hackathon MVP; OSM Overpass client)"

# Static Maps 一張圖最大 640x640（scale=2 拿到 1280x1280 的實際像素）
STATIC_MAP_BASE_PX = 640
STATIC_MAP_SCALE = 2

# 免金鑰備援：Esri World Imagery 圖磚，自己拼接成同尺寸的影像
ESRI_TILE_URL = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
                 "World_Imagery/MapServer/tile/{z}/{y}/{x}")
# 各地實際供圖層級差很多（實測：台灣都市 z19、阿姆斯特丹 z21、台灣鄉間 z18），
# 超出範圍時 Esri 不會回 404，而是回一張灰底寫著 "Map data not yet available"
# 的佔位圖 —— 所以 imagery.py 會偵測佔位圖並自動降階，這裡只是起始上限。
ESRI_MAX_ZOOM = 21
ESRI_MIN_ZOOM = 16
# 佔位圖幾乎沒有彩度；實測真實影像 ≤0.28、佔位圖 =1.00，取 0.9 有很大餘裕
ESRI_PLACEHOLDER_GRAYNESS = 0.9
# 影像涵蓋範圍 = 請求邊長 × 這個倍率（留一點路口周邊脈絡）
IMAGE_CONTEXT_RATIO = 1.25
# 拼接後若小於這個尺寸就放大，避免路口在畫面中太小不利模型判讀
IMAGE_TARGET_PX = 1024
ESRI_ATTRIBUTION = "Esri, Maxar, Earthstar Geographics"
OUTPUT_PX = STATIC_MAP_BASE_PX * STATIC_MAP_SCALE  # 1280

# 使用者可輸入的正方形邊長範圍（公尺）
MIN_SIZE_M = 40
MAX_SIZE_M = 400


def load_models() -> dict:
    """每次呼叫都重讀 models.yaml。"""
    with MODELS_YAML.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def model_for(role: str) -> str:
    cfg = load_models()
    roles = cfg.get("roles") or {}
    name = roles.get(role)
    if not name:
        raise KeyError(f"models.yaml 的 roles 底下找不到角色 '{role}'")
    return str(name)


def option(key: str, default=None):
    cfg = load_models()
    return (cfg.get("options") or {}).get(key, default)


def load_prompt(filename: str) -> str:
    """每次呼叫 model 時才從磁碟讀 prompt 檔（規格要求，不做快取）。"""
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"找不到 prompt 檔：{path}")
    return path.read_text(encoding="utf-8")
