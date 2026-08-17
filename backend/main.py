"""FastAPI 進入點。

啟動（在 backend/ 目錄底下）：
    uvicorn main:app --reload --port 8000
或
    python main.py
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import pipeline
from config import (GEMINI_API_KEY, GOOGLE_MAPS_API_KEY, MAX_SIZE_M, MIN_SIZE_M,
                    ROOT_DIR, load_models, load_prompt)
from services import cache, cases, imagery, memory

app = FastAPI(title="路口設計品質分析 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # MVP：開發方便，正式環境請收斂
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="中心點緯度")
    lng: float = Field(..., ge=-180, le=180, description="中心點經度")
    size_m: float = Field(120, ge=MIN_SIZE_M, le=MAX_SIZE_M,
                          description="以中心點為中心的正方形邊長（公尺）")
    force: bool = Field(False, description="True 就跳過磁碟快取，強制重新分析")


@app.get("/api/health")
def health() -> dict:
    scorer = load_prompt("00_scorer_system_prompt.md").strip()
    provider = imagery.resolve_provider()
    return {
        "ok": True,
        "gemini_api_key": bool(GEMINI_API_KEY),
        "google_maps_api_key": bool(GOOGLE_MAPS_API_KEY),
        "imagery_provider": provider,
        "imagery_ready": provider == "esri" or bool(GOOGLE_MAPS_API_KEY),
        "scorer_prompt_filled": bool(scorer),
        "scorer_prompt_chars": len(scorer),
        "models": load_models(),
        "classic_cases": len(cases.load_index()),
        "cache_entries": len(cache.entries()),
        "cache_fingerprint": cache.fingerprint(),
    }


@app.get("/api/cache")
def list_cache() -> dict:
    """目前 prompt / 模型設定下可用的快取。改了 prompt 舊快取就不算數。"""
    return {"fingerprint": cache.fingerprint(), "entries": cache.entries()}


@app.delete("/api/cache")
def clear_cache() -> dict:
    return {"deleted": cache.clear()}


@app.get("/api/cases")
def list_cases() -> dict:
    return {"cases": cases.load_index()}


@app.get("/api/session/{session_id}")
def session_memory(session_id: str) -> dict:
    data = memory.dump(session_id)
    if not data:
        raise HTTPException(404, "找不到這個 session（可能已過期）")
    return data


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest) -> dict:
    if not GEMINI_API_KEY:
        raise HTTPException(
            400,
            "尚未設定 GEMINI_API_KEY。請到 https://aistudio.google.com/apikey 取得"
            "（免費、不需要 Google Cloud 專案或帳單帳戶），填入專案根目錄的 .env。",
        )
    # imagery_provider 若解析成 esri 就不需要 Google 金鑰
    if imagery.resolve_provider() == "google" and not GOOGLE_MAPS_API_KEY:
        raise HTTPException(
            400,
            "models.yaml 指定使用 Google Static Maps，但沒有 GOOGLE_MAPS_API_KEY。"
            "請填入金鑰，或把 options.imagery_provider 改成 esri（免金鑰）。",
        )
    try:
        return await pipeline.analyze(req.lat, req.lng, req.size_m, force=req.force)
    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(500, f"分析失敗：{exc}") from exc


# ---------------------------------------------------------------------------
# 前端靜態檔。開發時用 vite dev server（走 /api proxy），這段不會生效；
# 容器裡則由 FastAPI 直接 serve build 產物，一個服務、一個網址、不用設 CORS。
# 必須掛在所有 /api 路由「之後」，否則會把 API 請求吃掉。
# ---------------------------------------------------------------------------
_DIST = ROOT_DIR / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    # Cloud Run 等平台會用 PORT 環境變數指定埠號，並要求綁 0.0.0.0
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "127.0.0.1" if os.getenv("PORT") is None else "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port,
                reload=os.getenv("RELOAD", "").lower() in ("1", "true"))
