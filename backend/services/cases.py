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


def _blob(case: dict) -> str:
    return " ".join([
        str(case.get("name", "")),
        str(case.get("summary", "")),
        " ".join(case.get("tags", []) or []),
        " ".join(case.get("problems_addressed", []) or []),
    ])


def _score(case: dict, intersection_type: str, keywords: list[str]) -> float:
    score = 0.0
    if intersection_type and case.get("intersection_type") == intersection_type:
        score += 5.0
    blob = _blob(case)
    for kw in keywords:
        kw = str(kw).strip()
        if kw and kw in blob:
            score += 1.0
    return score


def _match_reason(case: dict, intersection_type: str, keywords: list[str]) -> str:
    """給前端顯示的一句「為什麼挑這個案例」。"""
    bits = []
    if intersection_type and case.get("intersection_type") == intersection_type:
        bits.append("路口型態相近")

    blob = _blob(case)
    hits = []
    for kw in keywords:
        kw = str(kw).strip()
        if kw and kw in blob and kw not in hits:
            hits.append(kw)
    if hits:
        bits.append("且同樣涉及" + "、".join(hits[:3]) + "問題")

    if bits:
        return "，".join(bits)
    return f"路口型態為{case.get('intersection_type', '其他')}，改善手法可供參考"


def find_cases(intersection_type: str, keywords: list[str],
               limit: int = 3) -> list[dict]:
    """回傳最多 limit 個相符的經典案例，依相似度排序。"""
    cases = load_index()
    if not cases:
        return []

    scored = [(c, _score(c, intersection_type, keywords)) for c in cases]
    scored.sort(key=lambda x: x[1], reverse=True)

    picked = [c for c, s in scored if s > 0]
    if not picked:
        return []          # 一個都沒命中就不硬湊

    # 命中的不足 limit 時，用剩下分數最高的補滿版面，但理由會誠實標明型態不同
    if len(picked) < limit:
        rest = [c for c, s in scored if s <= 0]
        picked += rest[: limit - len(picked)]

    out = []
    for case in picked[:limit]:
        item = dict(case)
        item["image_data_url"] = _image_data_url(case.get("image"))
        item["match_reason"] = _match_reason(case, intersection_type, keywords)
        out.append(item)
    return out


def find_case(intersection_type: str, keywords: list[str]) -> dict | None:
    """挑一個最相符的經典案例（報告 Agent 用），找不到就回 None。"""
    found = find_cases(intersection_type, keywords, limit=1)
    return found[0] if found else None
