"""從重繪後的向量資料估算標線工程費用。

作法：把每條線的實際地理長度算出來（haversine），乘上該類標線的施作寬度
與塗佈率得到面積，再套單價表。

單價表校準自使用者提供的實務報價（單一路口島頭）：

    熱拌塑膠標線（槽化線）  15cm 外框 + 45 度斜紋，約 20 ㎡   $650 / ㎡
    玻璃珠與防滑骨材        BPN 50                          已內含
    施工交通維持費          三角錐 / LED / 爆閃燈車          $5,000~8,000 / 日
    反光導標、彈性防撞桿    島頭警示 3~5 根                  $400~600 / 根
    既有標線磨除            銑刨，約 20 ㎡                   $250~350 / ㎡
    ------------------------------------------------------------------
    單一路口島頭合計                                        $24,800~31,000

重要限制：**這張表只涵蓋標線工程。** 人行道外推、緣石重做、實體庇護島
屬於土木構造物，單價差一個量級，本模組只計算數量並標示「未涵蓋」，
不會硬套價格去產生一個假的總額。
"""

from __future__ import annotations

import math

from services.geo import haversine_m

CURRENCY = "TWD"

# 熱拌塑膠標線單價（元 / ㎡），玻璃珠與防滑骨材已內含
MARKING_RATE = 650

# ---------------------------------------------------------------------------
# 各圖層的施作規格
#   width_m   施作寬度或深度（公尺）
#   coverage  實際塗佈比例（虛線、斑馬線條紋之間有空隙）
#   note      給前端顯示的計算依據
# ---------------------------------------------------------------------------
SPECS: dict[str, dict] = {
    "crossing": {
        "label": "行人穿越道線",
        "width_m": 3.0,      # 穿越道深度，國內常見 3~8 m，取保守值
        "coverage": 0.40,    # 40 cm 條紋 / 60 cm 間隔
        "note": "線長 × 穿越深度 3.0 m × 塗佈率 40%（40 cm 條紋、60 cm 間隔）",
    },
    "crosswalk": {
        "label": "行人穿越道線",
        "width_m": 3.0,
        "coverage": 0.40,
        "note": "線長 × 穿越深度 3.0 m × 塗佈率 40%",
    },
    "stop_line": {
        "label": "停止線",
        "width_m": 0.40,
        "coverage": 1.0,
        "note": "線長 × 線寬 40 cm，實線滿塗",
    },
    "lane_marking": {
        "label": "車道標線",
        "width_m": 0.15,
        "coverage": 0.50,
        "note": "線長 × 線寬 15 cm × 塗佈率 50%（虛線）",
    },
    "channelization": {
        "label": "槽化線",
        # 校準自報價表：單一島頭約 17 m 外框 ≈ 20 ㎡，等效塗佈寬度 1.2 m
        "width_m": 1.20,
        "coverage": 1.0,
        "note": "線長 × 等效塗佈寬度 1.2 m（15 cm 外框加內部 45 度斜紋）",
    },
}

# 屬於土木構造物，不在標線單價表範圍內 —— 只報數量，不報價
UNCOVERED = {
    "sidewalk": "人行道",
    "bulb_out": "人行道端點外推",
    "corner_radius": "轉角緣石",
    "median": "中央分隔島",
    "refuge_island": "行人庇護島",
}

# 不是施工項目，只是設計參考線
IGNORED = {"roadway", "traffic", "kerb"}

# ---- 固定項目 -------------------------------------------------------------
TRAFFIC_CONTROL_PER_DAY = (5_000, 8_000)   # 交維，按日計費
REMOVAL_RATE = (250, 350)                  # 既有標線磨除，元 / ㎡
DELINEATOR_RATE = (400, 600)               # 反光導標 / 彈性防撞桿，元 / 根

# 熱拌標線班組日產能（㎡），用來估交維天數
MARKING_PER_DAY = 100
# 新標線中屬於「取代既有標線」需先磨除的比例
REMOVAL_RATIO = 0.70
# 每座實體島設置的防撞桿數量（報價表為單一島頭 3~5 根）
DELINEATORS_PER_ISLAND = 4


def _length_m(geom: dict) -> float:
    """折線的實際地理長度（公尺）。"""
    if geom.get("type") != "LineString":
        return 0.0
    coords = geom.get("coordinates") or []
    total = 0.0
    for i in range(len(coords) - 1):
        lng1, lat1 = coords[i][0], coords[i][1]
        lng2, lat2 = coords[i + 1][0], coords[i + 1][1]
        total += haversine_m((lat1, lng1), (lat2, lng2))
    return total


def _money(v: float) -> int:
    """無條件進位到百元，避免給出假精確的數字。"""
    return int(math.ceil(v / 100.0) * 100)


def estimate(design_geojson: dict) -> dict:
    """回傳結構化的費用估算。"""
    lengths: dict[str, float] = {}
    counts: dict[str, int] = {}

    for f in (design_geojson or {}).get("features", []):
        layer = (f.get("properties") or {}).get("layer")
        if not layer or layer in IGNORED:
            continue
        lengths[layer] = lengths.get(layer, 0.0) + _length_m(f.get("geometry") or {})
        counts[layer] = counts.get(layer, 0) + 1

    # ---- 標線項目 ---------------------------------------------------------
    items: list[dict] = []
    total_area = 0.0
    for layer, spec in SPECS.items():
        length = lengths.get(layer, 0.0)
        if length <= 0:
            continue
        area = length * spec["width_m"] * spec["coverage"]
        total_area += area
        cost = area * MARKING_RATE
        items.append({
            "key": layer,
            "label": spec["label"],
            "length_m": round(length, 1),
            "area_m2": round(area, 1),
            "rate": f"${MARKING_RATE:,} / ㎡",
            "low": _money(cost),
            "high": _money(cost),
            "basis": spec["note"],
        })

    # 同一個 label 可能對應多個 layer（crossing / crosswalk），合併
    merged: dict[str, dict] = {}
    for it in items:
        key = it["label"]
        if key in merged:
            m = merged[key]
            m["length_m"] = round(m["length_m"] + it["length_m"], 1)
            m["area_m2"] = round(m["area_m2"] + it["area_m2"], 1)
            m["low"] += it["low"]
            m["high"] += it["high"]
        else:
            merged[key] = dict(it)
    items = sorted(merged.values(), key=lambda x: -x["high"])

    # ---- 固定項目 ---------------------------------------------------------
    fixed: list[dict] = []

    if total_area > 0:
        removal_area = total_area * REMOVAL_RATIO
        fixed.append({
            "label": "既有標線磨除",
            "quantity": f"{removal_area:.1f} ㎡",
            "rate": f"${REMOVAL_RATE[0]}~{REMOVAL_RATE[1]} / ㎡",
            "low": _money(removal_area * REMOVAL_RATE[0]),
            "high": _money(removal_area * REMOVAL_RATE[1]),
            "basis": f"新標線面積的 {int(REMOVAL_RATIO * 100)}% 視為取代既有標線，需先銑刨",
        })

        days = max(1, math.ceil(total_area / MARKING_PER_DAY))
        fixed.append({
            "label": "施工交通維持",
            "quantity": f"{days} 日",
            "rate": f"${TRAFFIC_CONTROL_PER_DAY[0]:,}~{TRAFFIC_CONTROL_PER_DAY[1]:,} / 日",
            "low": _money(days * TRAFFIC_CONTROL_PER_DAY[0]),
            "high": _money(days * TRAFFIC_CONTROL_PER_DAY[1]),
            "basis": f"三角錐、LED 指揮棒、移動式爆閃燈車；"
                     f"以班組日產能 {MARKING_PER_DAY} ㎡ 推估工期",
        })

    islands = counts.get("median", 0) + counts.get("refuge_island", 0)
    if islands:
        n = islands * DELINEATORS_PER_ISLAND
        fixed.append({
            "label": "反光導標／彈性防撞桿",
            "quantity": f"{n} 根",
            "rate": f"${DELINEATOR_RATE[0]}~{DELINEATOR_RATE[1]} / 根",
            "low": _money(n * DELINEATOR_RATE[0]),
            "high": _money(n * DELINEATOR_RATE[1]),
            "basis": f"{islands} 座實體島 × 每座 {DELINEATORS_PER_ISLAND} 根島頭警示",
        })

    # ---- 未涵蓋項目（土木構造物）------------------------------------------
    uncovered = []
    for layer, label in UNCOVERED.items():
        length = lengths.get(layer, 0.0)
        if length <= 0:
            continue
        uncovered.append({
            "label": label,
            "length_m": round(length, 1),
            "count": counts.get(layer, 0),
        })

    low = sum(i["low"] for i in items) + sum(f["low"] for f in fixed)
    high = sum(i["high"] for i in items) + sum(f["high"] for f in fixed)

    return {
        "currency": CURRENCY,
        "items": items,
        "fixed": fixed,
        "uncovered": sorted(uncovered, key=lambda x: -x["length_m"]),
        "total_area_m2": round(total_area, 1),
        "total": {"low": _money(low), "high": _money(high)},
        "assumptions": [
            f"標線長度由重繪後的向量資料實際量測（haversine），非概估。",
            f"熱拌塑膠標線 ${MARKING_RATE}/㎡，玻璃珠與防滑骨材（BPN 50）已內含。",
            "行人穿越道以深度 3.0 m、塗佈率 40% 計算（40 cm 條紋、60 cm 間隔）。",
            "槽化線等效塗佈寬度 1.2 m，校準自「單一島頭約 20 ㎡」的實務報價。",
            "人行道、緣石、實體島屬土木構造物，單價差一個量級，未納入總額。",
            "本估算為數量級參考，不能取代正式的工程數量計算與詢價。",
        ],
    }
