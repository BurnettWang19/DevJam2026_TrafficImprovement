"""路口分析主流程。

    輸入座標 + 正方形邊長
        │
        ├─ 1. OSM Overpass 抓人行道／斑馬線／道路（向量）
        ├─ 2. Google Static Maps 抓衛星影像
        ├─ 3. Gemini 視覺辨識補車道線等 OSM 沒有的向量
        ├─ 4. 合併成一份向量資料 → 畫成現況圖
        ├─ 5. 主評分 Agent（system prompt 來自 00_scorer_system_prompt.md）
        │      └─ 無重大問題 → verdict = no_problem，流程結束
        ├─ 6. 路口類型判斷
        │      └─ 非路口 → break，verdict = not_intersection，回傳給前端
        ├─ 7. 三個 Sub Agent 平行找問題（斑馬線／人行道／車道標線）→ 存入記憶體
        ├─ 8. 重繪符合標準的道路設計向量圖
        ├─ 9. 把向量圖生成圖片
        └─ 10. 讀回記憶體中的問題 + 查經典案例 → 產出說明文字
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid

from config import MAX_SIZE_M, MIN_SIZE_M, cases_dir, load_prompt, option
from services import cache, cases, memory, osm, render, vision
from services.gemini import call_image, call_json
from services.geo import ImageFrame, bbox_from_center
from services.imagery import attribution, fetch_satellite, to_data_url

# 畫面以易讀為優先：每類問題只留最嚴重的幾個，模型多給也會在這裡被截掉
MAX_ISSUES_PER_CATEGORY = 2
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "uncertain": 4}

REDESIGN_LAYERS = {
    "roadway", "sidewalk", "crossing", "lane_marking", "stop_line",
    "channelization", "median", "refuge_island", "bulb_out", "corner_radius",
}

# 評分標準與輸出格式都由使用者貼在 00_scorer_system_prompt.md，
# 後端不再附加任何格式契約 —— 兩份 schema 打架只會讓模型亂輸出。
# 路由所需的欄位改由 _normalize_score() 從模型輸出推導出來。
#
# 只有在該檔案是空的時候，才會退回下面這組暫用標準 + 格式契約。
_SCORER_FALLBACK = """
（注意：使用者尚未貼上評分標準，以下為暫用的最低限度標準。）
你是交通工程審查員，依下列準則評估路口設計品質：
1. 人行道是否退縮（轉角是否有外推段／庇護島，是否縮短穿越距離）
2. 車道線在路口是否有做偏心設計（進口道是否偏折，路口內是否有導引線）
3. 斑馬線是否退離路口一個車身
4. 緣石轉彎半徑是否過大
5. 人行道是否連續且有足夠淨寬

## 輸出格式

只輸出 JSON：

```json
{
  "overall_score": 62,
  "summary": "兩三句話總結",
  "criteria": [
    {"criterion": "C1", "name": "人行道退縮", "score": 20, "confidence": 0.8,
     "status": "HIGH_RISK",
     "issues": [{"issue": "四個轉角皆無退縮", "severity": "HIGH", "reason": "…"}]}
  ],
  "priority_issues": [{"criterion": "C1", "issue": "…", "severity": "HIGH", "reason": "…"}],
  "missing_data": []
}
```

`score` 為 0~100（越高越好），`status` 為 GOOD / ACCEPTABLE / PROBLEMATIC /
HIGH_RISK / CRITICAL / INSUFFICIENT_DATA，`severity` 為 LOW / MEDIUM / HIGH / CRITICAL。
文字全部用繁體中文。
"""

_MAJOR_SEVERITY = {"HIGH", "CRITICAL"}
_MAJOR_STATUS = {"PROBLEMATIC", "HIGH_RISK", "CRITICAL"}


def _normalize_score(raw: dict) -> dict:
    """把評分 Agent 的輸出轉成流程分歧需要的欄位。

    使用者的 system prompt 自己定義了輸出 schema，後端不強加格式，
    所以這裡負責從它推導 has_major_problem / verdict，並容忍
    `overall_score` 或 `score` 兩種鍵名。
    """
    out = dict(raw) if isinstance(raw, dict) else {}
    score = out.get("overall_score", out.get("score"))
    if not isinstance(score, (int, float)):
        score = None
    out["score"] = score

    severities: list[str] = []
    statuses: list[str] = []
    for c in out.get("criteria") or []:
        if not isinstance(c, dict):
            continue
        statuses.append(str(c.get("status", "")).upper())
        for iss in c.get("issues") or []:
            if isinstance(iss, dict):
                severities.append(str(iss.get("severity", "")).upper())
    for pi in out.get("priority_issues") or []:
        if isinstance(pi, dict):
            severities.append(str(pi.get("severity", "")).upper())

    major = bool(set(severities) & _MAJOR_SEVERITY)
    major = major or bool(set(statuses) & _MAJOR_STATUS)
    if score is not None and score < 60:
        major = True
    if score is None:
        # 證據不足不等於沒問題 —— 無法判定合格就往下走診斷流程
        major = True

    out["has_major_problem"] = major
    out["verdict"] = "problem" if major else "good"
    out["severity_counts"] = {s: severities.count(s)
                              for s in sorted(set(severities)) if s}
    out["data_sufficient"] = score is not None
    return out


class Trace:
    def __init__(self) -> None:
        self.items: list[dict] = []
        self._t0 = time.perf_counter()

    def add(self, step: str, status: str, detail: str = "", **extra) -> None:
        self.items.append({
            "step": step,
            "status": status,
            "detail": detail,
            "at_ms": int((time.perf_counter() - self._t0) * 1000),
            **extra,
        })


def _scorer_system_extra() -> tuple[str, bool]:
    """回傳 (要附加在 system prompt 後的內容, 使用者是否已貼上標準)。"""
    if load_prompt("00_scorer_system_prompt.md").strip():
        return "", True          # 使用者的 prompt 就是全部，後端不加料
    return _SCORER_FALLBACK, False


async def analyze(lat: float, lng: float, size_m: float,
                  force: bool = False) -> dict:
    """對外入口。預設會走磁碟快取；force=True 強制重新分析。"""
    size_m = float(min(max(size_m, MIN_SIZE_M), MAX_SIZE_M))

    if not force:
        hit = cache.get(lat, lng, size_m)
        if hit is not None:
            hit["cached"] = True
            _restore_memory(hit)   # 讓 /api/session/{id} 對快取結果也查得到
            return hit

    result = await _analyze(lat, lng, size_m)
    result["cached"] = False
    cache.put(lat, lng, size_m, result)
    return result


async def _analyze(lat: float, lng: float, size_m: float) -> dict:
    session_id = uuid.uuid4().hex
    trace = Trace()
    bbox = bbox_from_center(lat, lng, size_m)

    result: dict = {
        "session_id": session_id,
        "input": {"lat": lat, "lng": lng, "size_m": size_m},
        "bbox": {"south": bbox[0], "west": bbox[1], "north": bbox[2], "east": bbox[3]},
        "trace": trace.items,
    }

    # ---- 1 & 2：OSM 與衛星影像平行抓 -------------------------------------
    trace.add("擷取資料", "running", "同時向 OpenStreetMap 與衛星影像來源取資料")
    osm_task = asyncio.create_task(osm.fetch_osm(bbox))
    img_task = asyncio.create_task(fetch_satellite(lat, lng, size_m))
    osm_fc, (base_png, frame, provider) = await asyncio.gather(osm_task, img_task)

    osm_summary = osm.summarize(osm_fc)
    trace.add("擷取資料", "done",
              f"OSM 取得 {len(osm_fc['features'])} 筆向量；"
              f"{provider} 衛星影像 {frame.width}x{frame.height}px"
              f"（zoom {frame.zoom}，{frame.meters_per_pixel:.2f} m/px）",
              counts=osm_summary["counts"])

    result["satellite_image"] = to_data_url(base_png)
    result["imagery"] = {"provider": provider, "attribution": attribution(provider),
                         "zoom": frame.zoom,
                         "meters_per_pixel": round(frame.meters_per_pixel, 3)}

    # ---- 3：Gemini 視覺辨識補車道線 --------------------------------------
    trace.add("視覺辨識補資料", "running", "Gemini 從衛星影像辨識 OSM 沒有的車道線／停止線")
    try:
        vision_fc = await vision.extract_lane_features(base_png, frame, osm_summary)
        trace.add("視覺辨識補資料", "done", f"補上 {len(vision_fc['features'])} 條線形")
    except Exception as exc:
        vision_fc = {"type": "FeatureCollection", "features": []}
        trace.add("視覺辨識補資料", "failed", str(exc)[:300])

    merged = vision.merge(osm_fc, vision_fc)
    result["vectors"] = merged
    result["vector_summary"] = {
        "osm": osm_summary,
        "vision_added": len(vision_fc["features"]),
        "total": len(merged["features"]),
    }
    result["current_image"] = render.render_overlay(base_png, merged, frame, "現況向量圖")

    # ---- 4：主評分 Agent -------------------------------------------------
    trace.add("評分 Agent", "running", "依 00_scorer_system_prompt.md 的標準評分")
    extra_system, has_user_prompt = _scorer_system_extra()
    if not has_user_prompt:
        trace.add("評分 Agent", "warning",
                  "prompts/00_scorer_system_prompt.md 是空的，先用內建的暫用標準。"
                  "請把你的評分標準貼進該檔案。")

    scorer_input = json.dumps({
        "intersection_id": session_id[:12],
        "center": {"lat": lat, "lng": lng},
        "square_size_m": size_m,
        "meters_per_pixel": round(frame.meters_per_pixel, 4),
        "imagery_source": provider,
        # 沒有的資料就明講，避免模型把「沒給」當成「不存在」
        "available_data": ["satellite_imagery", "openstreetmap_vectors",
                           "gemini_vision_lane_extraction"],
        "unavailable_data": ["street_level_imagery", "TDX", "traffic_volume",
                             "speed_data", "signal_timing", "accident_history"],
        "osm_summary": osm_summary,
        "vector_features": _compact(merged, frame),
    }, ensure_ascii=False)

    raw_score = await call_json(
        role="scorer",
        prompt_file="00_scorer_system_prompt.md",
        user_text=scorer_input,
        image_png=base_png,
        temperature=0.2,
        extra_system=extra_system,
    )
    score_res = _normalize_score(raw_score)
    result["score"] = score_res
    memory.put(session_id, "score", score_res)
    trace.add("評分 Agent", "done",
              f"得分 {score_res.get('score')}／100，判定 {score_res.get('verdict')}"
              + ("（證據不足，無法判定合格）" if not score_res["data_sufficient"] else ""))

    # ---- 分流 A：沒有重大問題 -------------------------------------------
    if not score_res["has_major_problem"]:
        result["verdict"] = "no_problem"
        result["message"] = score_res.get("summary") or "此路口未發現重大設計問題。"
        trace.add("流程結束", "done", "無重大問題，進入 no problem 流程")
        return result

    # ---- 5：路口類型判斷（非路口就 break）-------------------------------
    trace.add("路口類型判斷", "running", "判斷正交／圓環／多岔，或根本不是路口")
    type_res = await call_json(
        role="intersection_type",
        prompt_file="20_intersection_type.md",
        user_text=json.dumps({
            "osm_summary": osm_summary,
            "square_size_m": size_m,
            "vector_features": _compact(merged, frame),
        }, ensure_ascii=False),
        image_png=base_png,
        temperature=0.1,
    )
    result["intersection_type"] = type_res
    memory.put(session_id, "intersection_type", type_res)

    itype = str(type_res.get("type", "")).strip()
    if itype == "非路口" or type_res.get("is_intersection") is False:
        result["verdict"] = "not_intersection"
        result["message"] = type_res.get("reason") or "此範圍不是路口，可能是路段或非道路空間。"
        trace.add("路口類型判斷", "done", "判定為非路口，中斷判斷迴圈")
        trace.add("流程結束", "done", "回傳「非路口」給前端")
        return result

    trace.add("路口類型判斷", "done", f"{itype}（{type_res.get('leg_count')} 岔）")

    # ---- 6：三個 Sub Agent 平行找問題 ------------------------------------
    trace.add("Sub Agent 分析", "running", "斑馬線／人行道／車道標線 三路平行")
    sub_input = json.dumps({
        "intersection_type": itype,
        "square_size_m": size_m,
        "meters_per_pixel": round(frame.meters_per_pixel, 4),
        "osm_summary": osm_summary,
        "vector_features": _compact(merged, frame),
        "scorer_summary": score_res.get("summary"),
        "scorer_criteria": score_res.get("criteria"),
        "scorer_priority_issues": score_res.get("priority_issues"),
        "scorer_missing_data": score_res.get("missing_data"),
    }, ensure_ascii=False)

    subs = await asyncio.gather(
        _sub("sub_crosswalk", "30_sub_crosswalk.md", "斑馬線", sub_input, base_png),
        _sub("sub_sidewalk", "31_sub_sidewalk.md", "人行道", sub_input, base_png),
        _sub("sub_lane_marking", "32_sub_lane_marking.md", "車道標線", sub_input, base_png),
    )
    findings = {s["category"]: s for s in subs}
    memory.put(session_id, "findings", findings)   # ← 暫存在記憶體

    n_issues = sum(len(s.get("issues", [])) for s in subs)
    trace.add("Sub Agent 分析", "done",
              f"共 {n_issues} 個問題（每類最多 {MAX_ISSUES_PER_CATEGORY} 個），已存入記憶體")

    # ---- 7：重繪符合標準的設計向量圖 -------------------------------------
    trace.add("重繪設計", "running", "依三份問題清單重畫路口向量圖")
    redesign_res = await call_json(
        role="redesign",
        prompt_file="40_redesign.md",
        user_text=json.dumps({
            "intersection_type": itype,
            "meters_per_pixel": round(frame.meters_per_pixel, 4),
            "current_vectors": _compact(merged, frame),
            "findings": findings,
        }, ensure_ascii=False),
        image_png=base_png,
        temperature=0.35,
    )
    design_fc = vision.norm_features_to_geojson(
        redesign_res.get("features"), frame, REDESIGN_LAYERS, source="redesign_agent"
    )
    annotations = _clean_annotations(redesign_res.get("annotations"))
    result["design"] = {
        "name": redesign_res.get("design_name"),
        "summary": redesign_res.get("design_summary"),
        "key_changes": redesign_res.get("key_changes", [])[:4],
        "annotations": annotations,
        "geojson": design_fc,
    }
    memory.put(session_id, "design", result["design"])
    trace.add("重繪設計", "done",
              f"產生 {len(design_fc['features'])} 條設計線形、{len(annotations)} 個改動標記")

    # ---- 8：向量圖生成圖片 ----------------------------------------------
    trace.add("生成設計圖", "running", "繪製設計圖與改動標示圖")
    result["design_image"] = render.render_design(
        design_fc, frame, base_png, redesign_res.get("design_name") or "改善設計"
    )
    # 給看不懂工程圖的人：淡底 + 編號標記，直接指出哪裡改了
    result["annotated_image"] = render.render_annotated(
        base_png, design_fc, frame, annotations
    )
    note = "向量圖與改動標示圖完成"
    if option("use_gemini_image_gen", False):
        gen, why = await call_image(
            "image_gen", "60_image_gen.md",
            user_text=redesign_res.get("design_summary") or "",
            ref_images=[base_png],
        )
        if gen:
            import base64
            result["design_image_ai"] = "data:image/png;base64," + base64.b64encode(gen).decode()
            note += "；另附一張 AI 擬真圖"
        else:
            note += f"；AI 擬真圖失敗（{why}），改用向量繪圖"
            trace.add("生成設計圖", "warning", f"image_gen 失敗：{why}")
    trace.add("生成設計圖", "done", note)

    # ---- 9：讀回記憶體 + 查經典案例 + 產出說明 ---------------------------
    trace.add("彙整報告", "running", "讀回記憶體中的問題並比對經典案例")
    stored = memory.dump(session_id)
    stored_findings = stored.get("findings", {})

    keywords: list[str] = []
    for cat in stored_findings.values():
        for issue in cat.get("issues", []):
            keywords += [issue.get("title", ""), issue.get("standard_violated", "")]
    matched = cases.find_cases(itype, keywords, limit=3)
    case = matched[0] if matched else None
    result["classic_cases"] = matched      # 前端顯示三欄
    result["classic_case"] = case          # 報告 Agent 只吃最相符的那一個
    if case is None:
        trace.add("彙整報告", "warning",
                  f"經典案例資料夾（{cases_dir().name}/）沒有符合「{itype}」的案例，"
                  "報告會略過案例段落")

    report = await call_json(
        role="report",
        prompt_file="50_report.md",
        user_text=json.dumps({
            "intersection_type": itype,
            "memory_findings": stored_findings,
            "design_summary": result["design"]["summary"],
            "key_changes": result["design"]["key_changes"],
            "classic_case": _case_for_prompt(case),
        }, ensure_ascii=False),
        temperature=0.4,
    )

    result["findings"] = stored_findings
    result["report"] = report
    result["verdict"] = "improved"
    trace.add("彙整報告", "done", "完成")
    trace.add("流程結束", "done", "回傳結果給前端")
    return result


def _restore_memory(result: dict) -> None:
    """快取命中時把當初存進記憶體的內容補回去（伺服器重啟後記憶體是空的）。"""
    sid = result.get("session_id")
    if not sid:
        return
    for key, value in (("score", result.get("score")),
                       ("intersection_type", result.get("intersection_type")),
                       ("findings", result.get("findings")),
                       ("design", result.get("design"))):
        if value is not None:
            memory.put(sid, key, value)


def _coerce_sub(res, category: str) -> dict:
    """把 Sub Agent 的輸出整形成固定結構。

    模型有時會直接回一個 issue 陣列、或把陣列包在別的鍵名底下，
    不能假設一定是 {"category":…, "issues":[…]}。
    """
    if isinstance(res, list):
        return {"category": category, "overall_note": "",
                "issues": [x for x in res if isinstance(x, dict)]}

    if isinstance(res, dict):
        if not isinstance(res.get("issues"), list):
            # 找出第一個「看起來像 issue 清單」的值
            for value in res.values():
                if isinstance(value, list) and any(isinstance(x, dict) for x in value):
                    res["issues"] = [x for x in value if isinstance(x, dict)]
                    break
            else:
                res["issues"] = []
        res.setdefault("category", category)
        res.setdefault("overall_note", "")
        return res

    return {"category": category, "issues": [],
            "overall_note": "模型回傳的格式無法解析"}


def _clean_annotations(raw, limit: int = 4) -> list[dict]:
    """整理改動標記：座標必須在畫面內，標籤要短，彼此不能疊在一起。"""
    out: list[dict] = []
    for a in raw or []:
        if not isinstance(a, dict):
            continue
        try:
            nx, ny = float(a["point"][0]), float(a["point"][1])
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if not (0.0 <= nx <= 1.0 and 0.0 <= ny <= 1.0):
            continue
        nx, ny = min(max(nx, 0.06), 0.94), min(max(ny, 0.06), 0.94)
        # 標記與標籤都放大之後，太近的兩個標籤會擠成一團，後來的直接丟掉
        if any(abs(nx - o["point"][0]) < 0.14 and abs(ny - o["point"][1]) < 0.14
               for o in out):
            continue
        label = str(a.get("label") or "").strip()[:12]
        if not label:
            continue
        out.append({"point": [round(nx, 3), round(ny, 3)], "label": label,
                    "addresses": a.get("addresses") or []})
        if len(out) >= limit:
            break
    return out


def _trim_issues(res: dict) -> dict:
    """只留最嚴重的幾個問題 —— 畫面塞太多條使用者根本讀不完。"""
    issues = res.get("issues") or []
    issues.sort(key=lambda i: _SEVERITY_RANK.get(
        str(i.get("severity", "")).lower(), 9))
    res["issues"] = issues[:MAX_ISSUES_PER_CATEGORY]
    return res


async def _sub(role: str, prompt_file: str, category: str,
               user_text: str, image_png: bytes) -> dict:
    try:
        res = await call_json(role=role, prompt_file=prompt_file,
                              user_text=user_text, image_png=image_png,
                              temperature=0.25)
        return _trim_issues(_coerce_sub(res, category))
    except Exception as exc:
        return {"category": category, "overall_note": f"分析失敗：{exc}",
                "issues": [], "error": str(exc)[:300]}


def _compact(fc: dict, frame: ImageFrame, limit: int = 160) -> list[dict]:
    """把 GeoJSON 壓成給 LLM 看的精簡描述（正規化影像座標，最多取樣 6 點）。

    Overpass 的 `out geom;` 會回傳整條 way 而不是裁切到 bbox，所以要先把
    落在畫面外的點濾掉 —— 否則模型會收到 -1.2 這種座標，位置判斷全亂。
    """
    margin = 0.05
    out = []
    for f in fc.get("features", []):
        if len(out) >= limit:
            break
        geom = f.get("geometry") or {}
        coords = geom.get("coordinates") or []
        gtype = geom.get("type")
        if gtype == "Point":
            pts = [coords]
        elif gtype == "LineString":
            pts = coords
        elif gtype == "Polygon":
            pts = coords[0] if coords else []
        else:
            continue

        inside = []
        for lng, lat in pts:
            nx, ny = frame.latlng_to_norm(lat, lng)
            if -margin <= nx <= 1 + margin and -margin <= ny <= 1 + margin:
                inside.append([round(min(max(nx, 0.0), 1.0), 3),
                               round(min(max(ny, 0.0), 1.0), 3)])
        if not inside or (gtype != "Point" and len(inside) < 2):
            continue

        step = max(1, len(inside) // 6)
        p = f["properties"]
        out.append({
            "layer": p.get("layer"),
            "source": p.get("source"),
            "name": p.get("name"),
            "points": inside[::step][:6],
        })
    return out


def _case_for_prompt(case: dict | None) -> dict | None:
    if not case:
        return None
    return {k: v for k, v in case.items() if k != "image_data_url"}
