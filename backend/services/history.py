"""分析歷史紀錄 → Google Cloud Storage。

只存輕量摘要（1~2 KB / 筆）：座標、路名、verdict、分數、問題標題、費用區間。
不存任何圖片 —— 完整結果本來就在磁碟快取裡，歷史紀錄只回答
「我們曾經分析過哪些路口、結果大概如何」。

設計原則：**這個功能永遠不准弄壞主流程。**
- 未設定 GCS_HISTORY_BUCKET → 停用
- google-cloud-storage 沒安裝 → 停用
- 憑證／網路失敗 → 當次寫入靜默放棄，下次再試
寫入走背景 thread，不佔 /api/analyze 的回應時間。
"""

from __future__ import annotations

import json
import time

from config import GCS_HISTORY_BUCKET, GCS_PROJECT

_PREFIX = "history/"
_client = None
_import_failed = False


def _bucket():
    """拿 bucket handle；任何一步失敗都回 None（= 功能停用）。"""
    global _client, _import_failed
    if not GCS_HISTORY_BUCKET or _import_failed:
        return None
    try:
        from google.cloud import storage
    except ImportError:
        _import_failed = True
        return None
    try:
        if _client is None:
            _client = storage.Client(project=GCS_PROJECT)
        return _client.bucket(GCS_HISTORY_BUCKET)
    except Exception:
        return None


def summarize(result: dict) -> dict:
    """從完整分析結果抓重點，壓成一筆歷史紀錄。"""
    inp = result.get("input") or {}
    score = result.get("score") or {}
    osm_sum = ((result.get("vector_summary") or {}).get("osm")) or {}

    issues = []
    for cat in (result.get("findings") or {}).values():
        for iss in cat.get("issues") or []:
            issues.append({"title": iss.get("title"),
                           "severity": iss.get("severity")})

    cost = result.get("cost") or {}
    return {
        "id": result.get("session_id"),
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "lat": inp.get("lat"),
        "lng": inp.get("lng"),
        "size_m": inp.get("size_m"),
        "roads": (osm_sum.get("road_names") or [])[:4],
        "verdict": result.get("verdict"),
        "score": score.get("score"),
        "intersection_type": (result.get("intersection_type") or {}).get("type"),
        "issues": issues[:5],
        "cost_total": cost.get("total"),
        "cached": bool(result.get("cached")),
    }


def record_sync(result: dict) -> None:
    """寫入一筆紀錄。同步版本，請丟進 thread 跑。"""
    bucket = _bucket()
    if bucket is None:
        return
    rec = summarize(result)
    # 檔名以時間開頭 → 列出後倒序排就是最新在前
    name = (f"{_PREFIX}{time.strftime('%Y%m%dT%H%M%S')}"
            f"_{(rec.get('id') or 'unknown')[:8]}.json")
    try:
        bucket.blob(name).upload_from_string(
            json.dumps(rec, ensure_ascii=False),
            content_type="application/json; charset=utf-8",
        )
    except Exception:
        pass                          # 歷史紀錄失敗不值得吵醒任何人


def list_sync(limit: int = 30) -> list[dict] | None:
    """最新的 N 筆紀錄。功能停用回 None，正常但沒資料回 []。"""
    bucket = _bucket()
    if bucket is None:
        return None
    try:
        blobs = list(_client.list_blobs(bucket, prefix=_PREFIX))
    except Exception:
        return None
    blobs.sort(key=lambda b: b.name, reverse=True)
    out: list[dict] = []
    for blob in blobs[:limit]:
        try:
            out.append(json.loads(blob.download_as_text()))
        except Exception:
            continue
    return out
