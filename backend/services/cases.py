"""「經典案例」資料夾查詢。

資料夾位置：<專案根>/經典案例/
  index.json   案例清單（見 README.md 的欄位說明）
  *.jpg/png    對應的圖片（可省略）

比對邏輯：先看路口類型是否吻合，再看 tags 與問題關鍵字的重疊程度。
"""

from __future__ import annotations

import base64
import json
import mimetypes

from config import cases_dir

_INDEX = "index.json"


def load_index() -> list[dict]:
    path = cases_dir() / _INDEX
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else data.get("cases", [])


def _image_data_url(filename: str | None) -> str | None:
    if not filename:
        return None
    path = cases_dir() / filename
    if not path.exists():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _score(case: dict, intersection_type: str, keywords: list[str]) -> float:
    score = 0.0
    if intersection_type and case.get("intersection_type") == intersection_type:
        score += 5.0
    blob = " ".join([
        str(case.get("name", "")),
        str(case.get("summary", "")),
        " ".join(case.get("tags", []) or []),
        " ".join(case.get("problems_addressed", []) or []),
    ])
    for kw in keywords:
        kw = str(kw).strip()
        if kw and kw in blob:
            score += 1.0
    return score


def find_case(intersection_type: str, keywords: list[str]) -> dict | None:
    """挑一個最相符的經典案例，找不到就回 None。"""
    cases = load_index()
    if not cases:
        return None

    ranked = sorted(cases, key=lambda c: _score(c, intersection_type, keywords), reverse=True)
    best = ranked[0]
    if _score(best, intersection_type, keywords) <= 0:
        # 完全沒有相關的就不硬湊，只在同類型裡挑第一個
        same = [c for c in cases if c.get("intersection_type") == intersection_type]
        if not same:
            return None
        best = same[0]

    out = dict(best)
    out["image_data_url"] = _image_data_url(best.get("image"))
    return out
