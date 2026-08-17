"""把既有快取搬到目前的指紋，並補上新增的欄位。

用途：只加了純計算欄位（例如費用估算）時，不需要重跑模型 ——
直接讀舊快取、補欄位、以新指紋另存即可，省下每筆 2 分鐘的 API 呼叫。

用法（在 backend/ 目錄）：
    python migrate_cache.py            # 預覽會做什麼
    python migrate_cache.py --apply    # 實際寫入

注意：只有在「輸出結構的差異純粹是可由既有資料重算的欄位」時才適用。
改過 prompt 或模型設定的話，還是要老實重跑 prewarm.py。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from services import cache, costing

APPLY = "--apply" in sys.argv


def main() -> None:
    fp = cache.fingerprint()
    src = sorted(cache.CACHE_DIR.glob("*.json")) if cache.CACHE_DIR.is_dir() else []
    if not src:
        print("沒有任何快取檔")
        return

    print(f"目前指紋 {fp}｜掃描 {len(src)} 個檔案"
          f"{'' if APPLY else '（預覽模式，加 --apply 才會寫入）'}\n")

    # 同一組座標可能有多個舊指紋的版本，取最新的那個
    latest: dict[str, Path] = {}
    for path in src:
        stem = path.stem
        key = stem.rsplit("_", 1)[0]          # 去掉指紋，剩 lat_lng_size
        if key not in latest or path.stat().st_mtime > latest[key].stat().st_mtime:
            latest[key] = path

    done = skipped = 0
    for key, path in sorted(latest.items()):
        target = cache.CACHE_DIR / f"{key}_{fp}.json"
        if target.exists() and target != path:
            print(f"  [跳過] {key} —— 目前指紋已有快取")
            skipped += 1
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  [壞檔] {key}: {exc}")
            skipped += 1
            continue

        geojson = (data.get("design") or {}).get("geojson")
        if data.get("verdict") == "improved" and geojson:
            data["cost"] = costing.estimate(geojson)
            t = data["cost"]["total"]
            note = (f"標線 {data['cost']['total_area_m2']} ㎡，"
                    f"${t['low']:,}~${t['high']:,}")
        else:
            data.pop("cost", None)
            note = f"verdict={data.get('verdict')}，無設計圖，不估費用"

        print(f"  [搬移] {key}  {note}")
        if APPLY:
            target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        done += 1

    print(f"\n處理 {done} 筆、跳過 {skipped} 筆")
    if APPLY:
        n, mb = cache.prune()
        print(f"清掉 {n} 個舊指紋的檔案，釋放 {mb} MB")
        print(f"\n目前指紋 {fp} 底下共 {len(cache.entries())} 筆")
    else:
        print("加上 --apply 才會實際寫入")


if __name__ == "__main__":
    main()
