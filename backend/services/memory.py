"""流程中的記憶體暫存。

規格要求：Sub Agent 找到的問題要「暫存在記憶體」，
最後產出報告時再讀回來，用文字描述該路口原有的問題。

MVP 用 process 內的 dict；正式環境換 Redis 只要改這個檔。
"""

from __future__ import annotations

import threading
import time
from typing import Any

_LOCK = threading.Lock()
_STORE: dict[str, dict[str, Any]] = {}
_TTL_SECONDS = 60 * 60


def _gc() -> None:
    now = time.time()
    dead = [k for k, v in _STORE.items() if now - v.get("_ts", now) > _TTL_SECONDS]
    for k in dead:
        _STORE.pop(k, None)


def put(session_id: str, key: str, value: Any) -> None:
    with _LOCK:
        _gc()
        slot = _STORE.setdefault(session_id, {"_ts": time.time()})
        slot["_ts"] = time.time()
        slot[key] = value


def get(session_id: str, key: str, default: Any = None) -> Any:
    with _LOCK:
        return (_STORE.get(session_id) or {}).get(key, default)


def dump(session_id: str) -> dict[str, Any]:
    with _LOCK:
        slot = dict(_STORE.get(session_id) or {})
    slot.pop("_ts", None)
    return slot


def clear(session_id: str) -> None:
    with _LOCK:
        _STORE.pop(session_id, None)
