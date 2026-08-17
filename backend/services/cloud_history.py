"""Firestore 歷史索引 + Google Cloud Storage 完整分析檔案。"""

from __future__ import annotations

import base64
import copy
import json
import logging
import re
from datetime import datetime, timezone

from config import (GCP_PROJECT_ID, GCS_BUCKET, HISTORY_COLLECTION,
                    HISTORY_STORAGE_PREFIX)

logger = logging.getLogger(__name__)

_DATA_URL = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", re.DOTALL)
_IMAGE_FIELDS = (
    "satellite_image", "current_image", "design_image", "annotated_image",
    "design_image_ai",
)
_RECORD_ID = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


def enabled() -> bool:
    return bool(GCP_PROJECT_ID and GCS_BUCKET)


def status() -> dict:
    return {
        "enabled": enabled(),
        "project_id": GCP_PROJECT_ID or None,
        "bucket": GCS_BUCKET or None,
        "collection": HISTORY_COLLECTION,
    }


def _clients():
    if not enabled():
        raise RuntimeError("尚未設定 GCP_PROJECT_ID 與 GCS_BUCKET")
    from google.cloud import firestore, storage

    return firestore.Client(project=GCP_PROJECT_ID), storage.Client(project=GCP_PROJECT_ID)


def _record_id(result: dict) -> str:
    session_id = str(result.get("session_id") or "").strip()
    if not _RECORD_ID.fullmatch(session_id):
        raise ValueError("分析結果缺少 session_id")
    return session_id


def _valid_record_id(record_id: str) -> bool:
    return bool(_RECORD_ID.fullmatch(record_id))


def _summary(record_id: str, result: dict, result_object: str,
             image_objects: dict[str, str]) -> dict:
    inp = result.get("input") or {}
    score = result.get("score") or {}
    severity = score.get("severity_counts") or {}
    if not severity:
        for finding in (result.get("findings") or {}).values():
            for issue in finding.get("issues") or []:
                key = str(issue.get("severity") or "uncertain").lower()
                severity[key] = severity.get(key, 0) + 1

    roads = ((result.get("vector_summary") or {}).get("osm") or {}).get("road_names") or []
    location = " × ".join(roads[:2]) if roads else (
        f"{float(inp.get('lat', 0)):.5f}, {float(inp.get('lng', 0)):.5f}"
    )
    numeric_score = score.get("score")
    if not isinstance(numeric_score, (int, float)):
        numeric_score = None

    return {
        "id": record_id,
        "location": location,
        "lat": inp.get("lat"),
        "lng": inp.get("lng"),
        "size_m": inp.get("size_m"),
        "analyzed_at": datetime.now(timezone.utc),
        "verdict": result.get("verdict"),
        "score": numeric_score,
        "severity": {
            "critical": int(severity.get("CRITICAL", severity.get("critical", 0))),
            "high": int(severity.get("HIGH", severity.get("high", 0))),
            "medium": int(severity.get("MEDIUM", severity.get("medium", 0))),
            "low": int(severity.get("LOW", severity.get("low", 0))),
        },
        "osm_available": (result.get("vector_summary") or {}).get("osm_available", True),
        "result_object": result_object,
        "image_objects": image_objects,
    }


def save(result: dict) -> str:
    """拆出圖片上傳 GCS，再寫入完整 JSON 與 Firestore 索引。"""
    firestore_client, storage_client = _clients()
    bucket = storage_client.bucket(GCS_BUCKET)
    record_id = _record_id(result)
    prefix = f"{HISTORY_STORAGE_PREFIX}/{record_id}"
    stored = copy.deepcopy(result)
    image_objects: dict[str, str] = {}

    for field in _IMAGE_FIELDS:
        value = stored.get(field)
        if not isinstance(value, str):
            continue
        match = _DATA_URL.match(value)
        if not match:
            continue
        mime_type, encoded = match.groups()
        extension = "jpg" if mime_type == "image/jpeg" else mime_type.split("/")[1]
        object_name = f"{prefix}/images/{field}.{extension}"
        bucket.blob(object_name).upload_from_string(
            base64.b64decode(encoded), content_type=mime_type
        )
        image_objects[field] = object_name
        stored[field] = f"gs://{GCS_BUCKET}/{object_name}"

    result_object = f"{prefix}/result.json"
    bucket.blob(result_object).upload_from_string(
        json.dumps(stored, ensure_ascii=False), content_type="application/json; charset=utf-8"
    )
    summary = _summary(record_id, result, result_object, image_objects)
    firestore_client.collection(HISTORY_COLLECTION).document(record_id).set(summary)
    return record_id


def entries() -> list[dict]:
    firestore_client, _ = _clients()
    documents = firestore_client.collection(HISTORY_COLLECTION).stream()
    out = []
    for document in documents:
        item = document.to_dict() or {}
        item["id"] = document.id
        analyzed_at = item.get("analyzed_at")
        if hasattr(analyzed_at, "astimezone"):
            item["analyzed_at"] = analyzed_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        item.pop("image_objects", None)
        item.pop("result_object", None)
        out.append(item)
    return sorted(out, key=lambda item: item.get("analyzed_at") or "", reverse=True)


def get(record_id: str) -> dict | None:
    if not _valid_record_id(record_id):
        return None
    firestore_client, storage_client = _clients()
    snapshot = firestore_client.collection(HISTORY_COLLECTION).document(record_id).get()
    if not snapshot.exists:
        return None
    metadata = snapshot.to_dict() or {}
    bucket = storage_client.bucket(GCS_BUCKET)
    result_object = metadata.get("result_object")
    if not result_object:
        return None
    data = json.loads(bucket.blob(result_object).download_as_text(encoding="utf-8"))
    for field, object_name in (metadata.get("image_objects") or {}).items():
        blob = bucket.blob(object_name)
        raw = blob.download_as_bytes()
        mime_type = blob.content_type or "image/png"
        data[field] = f"data:{mime_type};base64,{base64.b64encode(raw).decode('ascii')}"
    return data


def delete(record_id: str) -> bool:
    if not _valid_record_id(record_id):
        return False
    firestore_client, storage_client = _clients()
    document = firestore_client.collection(HISTORY_COLLECTION).document(record_id)
    if not document.get().exists:
        return False
    bucket = storage_client.bucket(GCS_BUCKET)
    prefix = f"{HISTORY_STORAGE_PREFIX}/{record_id}/"
    for blob in storage_client.list_blobs(GCS_BUCKET, prefix=prefix):
        blob.delete()
    document.delete()
    return True


def save_safely(result: dict) -> bool:
    """雲端歷史不可用時保留分析結果與本地快取，不讓主流程失敗。"""
    if not enabled():
        return False
    try:
        save(result)
        return True
    except Exception:
        logger.exception("寫入 Firestore / GCS 歷史紀錄失敗")
        return False
