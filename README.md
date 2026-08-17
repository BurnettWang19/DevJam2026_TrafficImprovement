# 路口設計品質分析（Hackathon MVP）

輸入一組經緯度與正方形範圍，自動判斷「這個路口規劃得好不好」，並在有問題時重繪一份符合標準的設計圖。

```
使用者輸入 (lat, lng, 邊長 m)
   │
   ├─ ① OpenStreetMap (Overpass)  → 人行道 / 斑馬線 / 道路 / 緣石（現成向量）
   ├─ ② Google Static Maps        → 該範圍衛星影像
   ├─ ③ Gemini 視覺辨識            → 車道線 / 停止線 / 槽化線（OSM 沒有的）
   ├─ ④ 合併向量 → 畫成「現況向量圖」
   │
   ├─ ⑤ 評分 Agent（system prompt 由你提供）
   │       └─ 無重大問題 ──────────────────────→ verdict: no_problem ✅
   │
   ├─ ⑥ 路口類型 Agent（正交／圓環／多岔…）
   │       └─ 判定為「非路口」──── break ──────→ verdict: not_intersection 🚫
   │
   ├─ ⑦ 三個 Sub Agent 平行分析 → 問題存入記憶體
   │       斑馬線 · 人行道 · 車道標線
   │
   ├─ ⑧ 重繪 Agent → 新的道路設計向量圖
   ├─ ⑨ 繪圖 Agent → 生成 PNG
   └─ ⑩ 報告 Agent → 讀回記憶體的問題 + 查「經典案例」資料夾 + 說明如何改善
                                          → verdict: improved 🛠
```

---

## 你要做的兩件事

### 1. 填金鑰

`.env` 已經建好在專案根目錄，把金鑰貼在等號後面：

```
GEMINI_API_KEY=...          ← 必填
GOOGLE_MAPS_API_KEY=...     ← 選填
```

**`GEMINI_API_KEY`（必填）** 從 https://aistudio.google.com/apikey 取得。
免費、不需要 Google Cloud 專案、不需要帳單帳戶。六個 Agent 全部走這把。

**`GOOGLE_MAPS_API_KEY`（選填）** 留空的話會自動改用 Esri World Imagery（免金鑰），
整條流程照跑，只是影像解析度略低。詳見下面「衛星影像來源」。
要用 Google 的話：Google Cloud Console → APIs & Services → Library → 搜尋
"Maps Static API" → **Enable** → Credentials → Create API key。專案必須綁定帳單帳戶。

### 2. 貼上評分標準

打開 **`backend/prompts/00_scorer_system_prompt.md`**（目前是空白檔案），把你的評分依據與方法貼進去。

這個檔案的內容會**原封不動**當成評分 Agent 的 system prompt，而且**每次呼叫模型時都重新從磁碟讀取** —— 你改完存檔，下一次分析就生效，不用重啟 server。

> 檔案空白時系統會退回一組內建的暫用標準（人行道退縮、路口偏心等五項），前端「環境檢查」會標紅提醒你。
> 輸出的 JSON 格式由後端自動附加在你的 prompt 後面，你只要寫「怎麼評分」就好。

---

## Demo 流程

### 上台前（一定要做）

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python prewarm.py          # 把兩個示範路口跑過一次寫入快取，約 4 分鐘
```

跑完後現場點下去是 **0.3 秒**出結果，不是 2 分鐘。同時這也是斷網、
Overpass 被限流、Gemini 逾時時的保命符。

> 改過 `prompts/` 或 `models.yaml` 之後快取會自動失效（key 含內容指紋），
> 記得重跑 `python prewarm.py`。前端左下角「預熱快取 N 筆」可以確認。

### 建議順序

**① 先跑「非路口」** — 點預設按鈕 `台北 信義路五段（路段，測非路口）`。

系統會評分、發現問題、接著判斷這是不是路口 →「非路口」→ 中斷。
這證明它不是照單全收，而是會拒絕不該分析的輸入。

**② 再跑主秀** — 點 `台北 忠孝東路×敦化南路`，由上往下講：

| 畫面區塊 | 講點 |
|---|---|
| 左側「流程」時間軸 | 每一步的耗時都有記錄，證明是多 Agent 分工 |
| 評分卡 C1–C8 | 使用者自訂的評估標準，system prompt 熱讀取 |
| 前後對照圖 | 現況向量 vs 改善設計 |
| AI 擬真圖 | 外推段、退縮斑馬線、庇護島、車道偏心 |
| 問題清單 | 三個 Sub Agent 分頭找的，存記憶體再讀回 |
| 經典案例 | 同類型路口的良好設計對照 |
| 改善說明 | 問題 → 改動 → 效果逐條對應 |

**③ 被問「這是不是預錄的」** — 按左側「↻ 重新分析（跳過快取）」，
當場實際重跑一次所有 Agent。

### 快取指令

```powershell
python prewarm.py                      # 跑示範清單（已有快取就跳過）
python prewarm.py --force              # 全部重跑
python prewarm.py --list               # 列出現有快取
python prewarm.py --clear              # 清空
python prewarm.py 25.0417 121.549 140  # 預熱指定座標
```

對應的 API：`GET /api/cache`、`DELETE /api/cache`，
`POST /api/analyze` 帶 `"force": true` 可跳過快取。

### 現場注意

- **不要反覆試跑。** Overpass 公共節點依 IP 限流，觸發後全部節點會 504。
- **經典案例目前沒有圖。** `example/index.json` 有寫檔名但資料夾裡沒有圖檔，
  卡片只會顯示文字。丟四張圖進 `example/`（檔名對上 `image` 欄位）就會顯示。
- 需要連 Overpass、Esri 圖磚、Gemini。備一個手機熱點。

---

## 啟動

### 後端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 前端

```powershell
cd frontend
npm install
npm run dev
```

打開 http://localhost:5173 。Vite 已設好 proxy，前端打 `/api` 會自動轉給 8000 埠。

---

## 專案結構

```
DavJam_Project/
├─ .env                        ← 你的金鑰（自己建立）
├─ backend/
│  ├─ main.py                  FastAPI 端點
│  ├─ pipeline.py              ★ 主流程，上面那張圖就是它
│  ├─ prewarm.py               ★ Demo 前預熱快取
│  ├─ .cache/                  分析結果快取（gitignored）
│  ├─ config.py                讀 .env / models.yaml / prompts
│  ├─ models.yaml              ★ 角色 → Gemini 模型 ID（換模型改這裡）
│  ├─ prompts/
│  │  ├─ 00_scorer_system_prompt.md   ★ 空白，你貼評分標準
│  │  ├─ 10_vision_lane_extract.md    視覺辨識車道線
│  │  ├─ 20_intersection_type.md      路口類型判斷
│  │  ├─ 30_sub_crosswalk.md          Sub Agent：斑馬線
│  │  ├─ 31_sub_sidewalk.md           Sub Agent：人行道
│  │  ├─ 32_sub_lane_marking.md       Sub Agent：車道標線
│  │  ├─ 40_redesign.md               重繪設計向量圖
│  │  ├─ 50_report.md                 彙整報告
│  │  └─ 60_image_gen.md              （選用）AI 擬真圖
│  └─ services/
│     ├─ geo.py       Web Mercator 換算（經緯度 ⇄ 影像像素）
│     ├─ osm.py       Overpass 查詢與圖層分類
│     ├─ imagery.py   Google Static Maps
│     ├─ gemini.py    Gemini 呼叫封裝（每次重讀 prompt 與模型設定）
│     ├─ vision.py    視覺辨識 → GeoJSON
│     ├─ render.py    GeoJSON → PNG（Pillow）
│     ├─ memory.py    Sub Agent 問題的記憶體暫存
│     └─ cases.py     經典案例查詢
├─ example/           經典案例資料夾（`經典案例` / `classic_cases` 這兩個名字也認）
│  ├─ index.json      案例清單（已放 4 筆範例）
│  └─ README.md       怎麼新增案例
└─ frontend/          Vue 3 + Vite + Leaflet
```

---

## 模型設定

`backend/models.yaml` 把每個 Agent 角色對應到模型 ID，程式不寫死：

| 角色 | 預設模型 |
|---|---|
| `vision_lane_extract` | `gemini-3.7-flash` |
| `scorer` | `gemini-3.7-flash` |
| `intersection_type` | `gemini-3.5-flash` |
| `sub_crosswalk` / `sub_sidewalk` / `sub_lane_marking` | `gemini-3.5-flash` |
| `redesign` | `gemini-3.7-flash` |
| `report` | `gemini-3.5-flash` |
| `image_gen` | `gemini-3-pro-image` |

> 原規格寫的 `gemini-1.5-flash` 已停用，改用 3.x 系列；`gemini-3.5-flash` 則確實存在，路口類型判斷就用它。
>
> `options.use_gemini_image_gen: false` —— 預設用 Pillow 確定性地把向量圖畫成 PNG（快、穩、demo 不會翻車）。
> 改成 `true` 會**額外**呼叫 `gemini-3-pro-image` 生一張擬真圖，前端會多顯示一張。

---

## 衛星影像來源

`models.yaml` 的 `options.imagery_provider`：

| 值 | 行為 |
|---|---|
| `auto`（預設） | 有 `GOOGLE_MAPS_API_KEY` 就用 Google，沒有就退到 Esri |
| `google` | 強制 Google Static Maps。需 API key + 已啟用 Maps Static API + 帳單帳戶 |
| `esri` | 強制 Esri World Imagery。免金鑰、免帳單 |

兩種來源都會回傳一個 `ImageFrame`，所以「經緯度 ⇄ 影像像素」的換算完全共用，
Gemini 回傳的正規化座標換回經緯度的精度不受來源影響（實測往返誤差 < 1 cm）。

### Esri 的兩個實測坑

**1. 各地供圖層級差很多。** 實測：台灣都市最高 z19（約 0.27 m/px）、
阿姆斯特丹 z21、台灣鄉間 z18。

**2. 超出範圍時不回 404。** Esri 會回一張灰底寫著 "Map data not yet available"
的佔位圖，HTTP 200。`imagery.py` 用彩度偵測辨識它（實測真實影像的無彩度像素比例
≤0.28、佔位圖 =1.00，門檻取 0.9），偵測到就自動降一階重試。

所以你不用手動指定 zoom，程式會自己找到該地點實際可用的最高解析度。
超過 70% 的圖磚拿不到時會直接報錯，而不是把破圖送給 Gemini 辨識。

### OSM Overpass 的三個實測坑

1. **`overpass-api.de` 會用 406 擋掉沒有 User-Agent 的請求。** 已固定帶 UA。
2. **不要加 `overpass.osm.ch`。** 它是瑞士專用的區域實例，台灣的查詢會回
   200 但 `elements=0` —— 這種「成功但空」比直接失敗更難查。程式現在把空結果
   視為可疑，要多個節點一致回空才接受。
3. **公共節點依 IP 限流。** 短時間大量查詢會拿到 504 / timeout，等一下就恢復。
   已內建 3 個節點 × 2 輪重試，查詢本身也壓到 5 個 clause 降低被踢的機率。

---

## API

| 方法 | 路徑 | 說明 |
|---|---|---|
| `POST` | `/api/analyze` | `{lat, lng, size_m}` → 完整分析結果 |
| `GET` | `/api/health` | 金鑰、prompt、案例數的環境檢查 |
| `GET` | `/api/cases` | 經典案例清單 |
| `GET` | `/api/session/{id}` | 讀該次分析暫存在記憶體的內容 |
| `GET` | `/api/cache` | 目前 prompt／模型指紋下可用的快取 |
| `DELETE` | `/api/cache` | 清空快取 |

`/api/analyze` 回傳的 `verdict` 有三種：`no_problem`、`not_intersection`、`improved`。

---

## MVP 的已知簡化

- 記憶體用 process 內的 dict（TTL 1 小時），重啟就清空。要多機部署時把 `services/memory.py` 換成 Redis。
- Static Maps 單張上限 640×640（scale=2 → 1280×1280 實際像素），所以邊長超過約 400 公尺時解析度會不足以看清標線 —— 前端滑桿已限制在 40~400 m。
- 重繪 Agent 輸出的是折線示意，不是可施工的 CAD 圖。
- 快取是整份結果的磁碟 JSON（單筆 3~6 MB），沒有淘汰機制，佔太多空間就 `--clear`。
