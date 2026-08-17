"""從 OpenStreetMap（Overpass API）擷取路口範圍內的現成向量資料。

輸出統一成 GeoJSON FeatureCollection，每個 feature 的
properties.layer 會是下列其中之一：
    roadway     車道中心線（highway=*）
    sidewalk    人行道
    crossing    斑馬線 / 行人穿越
    kerb        緣石、退縮線索
    traffic     號誌、停讓標誌等點位
"""

from __future__ import annotations

import asyncio

import httpx

from config import OVERPASS_ENDPOINTS, OVERPASS_ROUNDS, USER_AGENT

# 刻意壓到 5 個 clause：way["footway"] 與 way["crossing"] 都是
# highway=footway 的子標籤，已被 way["highway"] 涵蓋，多寫只會拖慢查詢。
# 公共 Overpass 節點很容易 504，查詢越輕越不會被踢掉。
_QUERY = """
[out:json][timeout:30];
(
  way["highway"]({s},{w},{n},{e});
  way["area:highway"]({s},{w},{n},{e});
  way["kerb"]({s},{w},{n},{e});
  node["highway"~"^(crossing|traffic_signals|stop|give_way)$"]({s},{w},{n},{e});
  node["kerb"]({s},{w},{n},{e});
);
out geom;
"""

_ROAD_VALUES = {
    "motorway", "trunk", "primary", "secondary", "tertiary", "unclassified",
    "residential", "service", "living_street", "motorway_link", "trunk_link",
    "primary_link", "secondary_link", "tertiary_link", "road",
}


def _classify(tags: dict) -> str | None:
    highway = tags.get("highway")
    footway = tags.get("footway")

    if highway == "crossing" or footway == "crossing" or "crossing" in tags:
        return "crossing"
    if highway == "footway" and footway == "sidewalk":
        return "sidewalk"
    if highway in ("footway", "path", "pedestrian", "steps"):
        return "sidewalk"
    if highway == "kerb" or "kerb" in tags:
        return "kerb"
    if highway in ("traffic_signals", "stop", "give_way"):
        return "traffic"
    if highway in _ROAD_VALUES:
        return "roadway"
    if tags.get("area:highway"):
        return "roadway"
    return None


async def fetch_osm(bbox: tuple[float, float, float, float]) -> dict:
    """bbox = (south, west, north, east)。回傳 GeoJSON FeatureCollection。"""
    s, w, n, e = bbox
    query = _QUERY.format(s=s, w=w, n=n, e=e)

    data = None
    saw_valid_empty = False
    errors: list[str] = []
    # 沒有 User-Agent 的話 overpass-api.de 會直接回 406，一定要帶。
    headers = {"User-Agent": USER_AGENT}

    # 公共節點的 504／timeout 多半是瞬間負載，整輪跑完再重試一次比原地重試有效
    async with httpx.AsyncClient(timeout=45.0, headers=headers) as client:
        for attempt in range(OVERPASS_ROUNDS):
            for url in OVERPASS_ENDPOINTS:
                try:
                    r = await client.post(url, data={"data": query})
                    r.raise_for_status()
                    payload = r.json()
                    if "elements" not in payload:
                        raise ValueError("回應中沒有 elements 欄位")
                    # 空結果先當成可疑（可能是區域性實例或殘缺的鏡像），
                    # 換下一個節點確認；真的到處都空才接受。
                    if not payload["elements"]:
                        saw_valid_empty = True
                        errors.append(f"[第{attempt + 1}輪] {url}: 回傳 0 筆，換下一個節點確認")
                        continue
                    data = payload
                    break
                except Exception as exc:
                    errors.append(f"[第{attempt + 1}輪] {url}: "
                                  f"{type(exc).__name__} {exc}"[:180])
            if data is not None:
                break
            await asyncio.sleep(1.5 * (attempt + 1))

    if data is None:
        if saw_valid_empty:
            # 所有節點一致回空 —— 這個範圍在 OSM 上真的沒有道路資料
            return {"type": "FeatureCollection", "features": []}
        raise RuntimeError("所有 Overpass 節點都失敗了（公共節點會依 IP 限流，"
                           "短時間大量查詢後稍等一下通常就會恢復）：\n" + "\n".join(errors))

    features = []
    for el in data.get("elements", []):
        tags = el.get("tags") or {}
        layer = _classify(tags)
        if layer is None:
            continue

        if el["type"] == "way" and el.get("geometry"):
            coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
            if len(coords) < 2:
                continue
            closed = coords[0] == coords[-1] and len(coords) >= 4
            geom = (
                {"type": "Polygon", "coordinates": [coords]}
                if closed and tags.get("area:highway")
                else {"type": "LineString", "coordinates": coords}
            )
        elif el["type"] == "node":
            geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
        else:
            continue

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "layer": layer,
                "source": "osm",
                "osm_id": f"{el['type']}/{el['id']}",
                "name": tags.get("name"),
                "tags": tags,
            },
        })

    return {"type": "FeatureCollection", "features": features}


def summarize(fc: dict) -> dict:
    """給 LLM 看的簡短統計（避免整包 GeoJSON 灌進 prompt）。"""
    counts: dict[str, int] = {}
    road_names: set[str] = set()
    for f in fc.get("features", []):
        p = f["properties"]
        counts[p["layer"]] = counts.get(p["layer"], 0) + 1
        if p["layer"] == "roadway" and p.get("name"):
            road_names.add(p["name"])
    return {"counts": counts, "road_names": sorted(road_names)}
