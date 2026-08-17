"""分析結果的磁碟快取 —— demo 保命用。

用途：
  1. 上台前先把示範路口跑過一次，現場點下去 1 秒內出結果，不用等 2 分鐘。
  2. 現場斷網、Overpass 被限流、Gemini 逾時時，仍然放得出東西。

快取 key 包含 prompts/ 與 models.yaml 的指紋 —— 你改了評分標準或換了模型，
舊結果就自動失效，不會拿跟現行標準不符的內容去 demo。
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from config import BACKEND_DIR, MODELS_YAML, PROMPTS_DIR

CACHE_DIR = BACKEND_DIR / ".cache"


def fingerprint() -> str:
    """會影響輸出內容的所有檔案的指紋。

    涵蓋 models.yaml、prompts/、以及後端程式碼 —— 改了繪圖配色或流程結構，
    舊快取就必須失效，否則 demo 會拿到跟現行程式不符的舊圖。
    """
    h = hashlib.sha256()
    try:
        h.update(MODELS_YAML.read_bytes())
        sources = sorted(PROMPTS_DIR.glob("*.md"))
        sources += sorted(BACKEND_DIR.glob("*.py"))
        sources += sorted((BACKEND_DIR / "services").glob("*.py"))
        for p in sources:
            if p.name == "prewarm.py":      # 只是入口腳本，不影響結果
                continue
            h.update(p.name.encode("utf-8"))
            h.update(p.read_bytes())
    except OSError:
        return "nofp"
    return h.hexdigest()[:12]


def _path(lat: float, lng: float, size_m: float) -> Path:
    return CACHE_DIR / f"{lat:.6f}_{lng:.6f}_{int(size_m)}m_{fingerprint()}.json"


def get(lat: float, lng: float, size_m: float) -> dict | None:
    path = _path(lat, lng, size_m)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def put(lat: float, lng: float, size_m: float, result: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = dict(result)
    payload["cached_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    path = _path(lat, lng, size_m)
    try:
        # 先寫暫存檔再 replace，避免中途失敗留下半截 JSON
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def entries() -> list[dict]:
    """列出目前指紋下可用的快取。"""
    if not CACHE_DIR.is_dir():
        return []
    fp = fingerprint()
    out = []
    for path in sorted(CACHE_DIR.glob(f"*_{fp}.json")):
        stem = path.stem[: -(len(fp) + 1)]
        parts = stem.rsplit("_", 2)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append({
            "lat": float(parts[0]),
            "lng": float(parts[1]),
            "size_m": int(parts[2].rstrip("m")),
            "verdict": data.get("verdict"),
            "cached_at": data.get("cached_at"),
            "size_mb": round(path.stat().st_size / 1024 / 1024, 2),
        })
    return out


def clear() -> int:
    """清掉所有快取（含舊指紋的），回傳刪除數量。"""
    if not CACHE_DIR.is_dir():
        return 0
    n = 0
    for path in CACHE_DIR.glob("*.json"):
        try:
            path.unlink()
            n += 1
        except OSError:
            pass
    return n


def prune() -> tuple[int, float]:
    """只刪掉「舊指紋」的快取，保留目前這一版。

    每次改 prompt 或程式都會產生一組新指紋，舊的檔案就變成純垃圾。
    要把快取打包進 Docker 映像時，這一步能省下大量體積。
    回傳 (刪除檔數, 釋放的 MB)。
    """
    if not CACHE_DIR.is_dir():
        return 0, 0.0
    keep = f"_{fingerprint()}.json"
    n, freed = 0, 0
    for path in CACHE_DIR.glob("*.json"):
        if path.name.endswith(keep):
            continue
        try:
            freed += path.stat().st_size
            path.unlink()
            n += 1
        except OSError:
            pass
    return n, round(freed / 1024 / 1024, 1)
