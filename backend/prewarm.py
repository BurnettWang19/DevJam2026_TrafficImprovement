"""Demo 前先把示範路口跑過一次，把結果寫進磁碟快取。

用法（在 backend/ 目錄，venv 已啟動）：

    python prewarm.py                 # 跑內建的示範清單
    python prewarm.py 25.0417 121.549 140
    python prewarm.py --force         # 忽略既有快取，全部重跑
    python prewarm.py --list          # 只列出目前有哪些快取
    python prewarm.py --prune         # 只刪舊指紋的垃圾，保留現行版本
    python prewarm.py --clear         # 清掉全部快取

上台前跑一次，現場點下去就是 1 秒內出結果。
注意：改過 prompts/ 或 models.yaml 之後快取會自動失效，記得重跑。
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# Windows 主控台預設 cp950，印「・」「✓」這類字元會直接 UnicodeEncodeError
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pipeline
from services import cache

# 前端 PRESETS 的同一組座標
DEMO_SPOTS = [
    ("台北 忠孝東路×敦化南路（主秀・正交路口）", 25.0417, 121.549, 140),
    ("台北 信義路五段（示範「非路口」中斷）", 25.033139, 121.564469, 120),
    ("台北 公館圓環（多岔・圓環優先示範）", 25.0111, 121.5367, 180),
    ("台中 台灣大道×文心路（正交大路口）", 24.163889, 120.646111, 160),
    ("阿姆斯特丹（no_problem 對照組）", 52.350556, 4.868889, 140),
]


def show_list() -> None:
    entries = cache.entries()
    print(f"指紋 {cache.fingerprint()} 底下共 {len(entries)} 筆快取：")
    for e in entries:
        print(f"  {e['lat']:.6f}, {e['lng']:.6f}  {e['size_m']}m  "
              f"{e['verdict']:<17} {e['size_mb']}MB  {e['cached_at']}")
    if not entries:
        print("  （空的 —— 直接跑 python prewarm.py 就會建立）")


async def warm(spots, force: bool) -> None:
    print(f"指紋 {cache.fingerprint()}｜共 {len(spots)} 個地點｜"
          f"force={force}\n")
    for name, lat, lng, size in spots:
        hit = cache.get(lat, lng, size)
        if hit is not None and not force:
            print(f"[skip] {name}  已有快取（{hit.get('cached_at')}）")
            continue

        print(f"[run ] {name}  ({lat}, {lng}) {size}m …", flush=True)
        t0 = time.perf_counter()
        try:
            r = await pipeline.analyze(lat, lng, size, force=True)
        except Exception as exc:
            print(f"[FAIL] {name}: {type(exc).__name__} {exc}\n")
            continue
        dt = time.perf_counter() - t0
        imgs = [k for k in ("current_image", "design_image", "design_image_ai")
                if r.get(k)]
        n_issues = sum(len(v.get("issues", []))
                       for v in (r.get("findings") or {}).values())
        print(f"[ok  ] {dt:.0f}s  verdict={r['verdict']}  "
              f"score={(r.get('score') or {}).get('score')}  "
              f"issues={n_issues}  images={len(imgs)}\n")

    print("-" * 60)
    show_list()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]

    if "--list" in args:
        show_list()
        sys.exit(0)

    if "--prune" in args:
        n, mb = cache.prune()
        print(f"已清掉 {n} 個舊指紋的快取檔，釋放 {mb} MB\n")
        show_list()
        sys.exit(0)

    if "--clear" in args:
        print(f"已刪除 {cache.clear()} 個快取檔")
        sys.exit(0)

    force = "--force" in args
    nums = [a for a in args if not a.startswith("--")]

    if len(nums) >= 3:
        spots = [("自訂座標", float(nums[0]), float(nums[1]), float(nums[2]))]
    else:
        spots = DEMO_SPOTS

    asyncio.run(warm(spots, force))
