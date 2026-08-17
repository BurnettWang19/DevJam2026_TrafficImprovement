# 專案架構

路口設計品質分析系統。輸入一組經緯度與正方形範圍，自動判斷該路口規劃是否完善，
有問題時重繪一份符合標準的設計並產生對照圖與改善說明。

---

## 目錄結構

```
DavJam_Project/
│
├── .env                        你的金鑰（gitignored，自行建立）
├── .env.example                金鑰範本
├── .gitattributes              統一 LF 換行
├── .gitignore
├── README.md                   安裝、啟動、demo 流程
├── ARCHITECTURE.md             本文件
├── README copy.md              團隊原有的架構與技術選型文件
│
├── backend/                    Python 3.14 · FastAPI
│   ├── main.py            (87)   HTTP 端點、CORS、金鑰前置檢查
│   ├── pipeline.py       (437)  ★ 主流程編排，十個階段都在這裡
│   ├── config.py          (70)   .env / models.yaml / prompts 的讀取
│   ├── models.yaml        (29)  ★ 角色 → Gemini 模型 ID，程式不寫死型號
│   ├── prewarm.py         (67)   Demo 前預熱快取的 CLI
│   ├── requirements.txt
│   │
│   ├── prompts/                  每次呼叫模型時重讀，改完存檔即生效
│   │   ├── 00_scorer_system_prompt.md  (320) ★ 使用者自訂的評分標準
│   │   ├── 10_vision_lane_extract.md    (30)  影像辨識車道標線
│   │   ├── 20_intersection_type.md      (26)  路口型態判斷
│   │   ├── 30_sub_crosswalk.md          (38)  子代理人：斑馬線
│   │   ├── 31_sub_sidewalk.md           (39)  子代理人：人行道
│   │   ├── 32_sub_lane_marking.md       (40)  子代理人：車道標線
│   │   ├── 40_redesign.md               (42)  重繪設計向量圖 + 改動標記
│   │   ├── 50_report.md                 (38)  彙整條列式說明
│   │   └── 60_image_gen.md               (4)  AI 擬真圖（選用）
│   │
│   ├── services/
│   │   ├── geo.py         (71)   Web Mercator：經緯度 ⇄ 影像像素
│   │   ├── osm.py        (120)   Overpass 查詢、圖層分類、多節點容錯
│   │   ├── imagery.py    (153)   Google Static Maps／Esri 圖磚拼接
│   │   ├── gemini.py     (115)   Gemini 呼叫封裝、JSON 修補、重試
│   │   ├── vision.py      (71)   影像辨識結果 → GeoJSON
│   │   ├── render.py     (256)   GeoJSON → PNG、圖例、改動標記佈局
│   │   ├── cases.py       (86)   經典案例比對與排序
│   │   ├── memory.py      (33)   子代理人問題的記憶體暫存
│   │   └── cache.py       (85)   結果磁碟快取（含內*容指紋）
│   │
│   ├── .venv/                    虛擬環境（gitignored）
│   └── .cache/                   分析結果快取（gitignored，單筆 3~7 MB）
│
├── example/                    經典案例資料庫
│   ├── index.json         (78)   案例清單（目前 4 筆）
│   └── README.md          (38)   欄位說明與新增方式
│
└── frontend/                   Vue 3 · Vite · Leaflet
    ├── index.html
    ├── package.json
    ├── vite.config.js     (15)   /api 代理到 :8000
    └── src/
        ├── main.js         (5)
        ├── style.css      (92)   米色底 + 深綠的設計 token
        ├── App.vue       (189)   座標輸入、地圖選點、環境檢查
        └── components/
            ├── MapPicker.vue      (64)  Leaflet 選點與範圍框
            ├── TraceTimeline.vue  (36)  流程進度時間軸
            └── ResultPanel.vue   (380)  結果版面：評級、對照圖、
                                          問題卡片、經典案例
```

---

## 分析流程

```
                    使用者輸入 (lat, lng, 邊長 m)
                              │
                    ┌─────────┴──────────┐
                    │  cache.get() 命中？ │──── 是 ──→ 0.3 秒回傳
                    └─────────┬──────────┘
                              │ 否
              ┌───────────────┴───────────────┐
              │                               │
    ① OpenStreetMap                 ② 衛星影像
       Overpass API                    Google Static Maps
       人行道／斑馬線                    或 Esri World Imagery
       道路／緣石                        （免金鑰備援）
              │                               │
              └───────────────┬───────────────┘
                              │
                    ③ Gemini 影像辨識
                       補上 OSM 沒有的
                       車道線／停止線／槽化線
                              │
                    ④ 合併向量 → 現況圖
                              │
                    ⑤ 評分代理人
                       system prompt 來自
                       00_scorer_system_prompt.md
                              │
                    ┌─────────┴─────────┐
                    │                   │
              無重大問題            有重大問題
                    │                   │
            verdict:            ⑥ 路口型態判斷
            no_problem                  │
                              ┌─────────┴─────────┐
                              │                   │
                          非路口               是路口
                              │                   │
                    verdict:          ⑦ 三個子代理人（平行）
                    not_intersection     斑馬線 · 人行道 · 車道標線
                    ← break                     │
                                        問題存入記憶體
                                                │
                                      ⑧ 重繪設計向量圖
                                         + 改動位置標記
                                                │
                                      ⑨ 繪製圖面
                                         設計圖 · 改動標示圖
                                         ·（選用）AI 擬真圖
                                                │
                                      ⑩ 讀回記憶體 + 比對經典案例
                                         → 條列式說明
                                                │
                                         verdict: improved
                                                │
                                         cache.put()
```

---

## 模型分工

`backend/models.yaml` 定義，程式不寫死型號。

| 階段 | 角色 | 預設模型 |
|---|---|---|
| ③ | `vision_lane_extract` | `gemini-3.7-flash` |
| ⑤ | `scorer` | `gemini-3.7-flash` |
| ⑥ | `intersection_type` | `gemini-3.5-flash` |
| ⑦ | `sub_crosswalk` / `sub_sidewalk` / `sub_lane_marking` | `gemini-3.5-flash` |
| ⑧ | `redesign` | `gemini-3.7-flash` |
| ⑨ | `image_gen` | `gemini-3-pro-image` |
| ⑩ | `report` | `gemini-3.5-flash` |

---

## 關鍵設計

**評分標準完全外部化。** `00_scorer_system_prompt.md` 的內容原封不動作為評分代理人的
system prompt，後端不附加任何格式契約，只從模型輸出推導流程分歧
（`pipeline._normalize_score`）。改標準不必動程式。

**兩種影像來源共用同一套座標系。** `geo.ImageFrame` 讓 Google 與 Esri 兩條路徑的
「經緯度 ⇄ 影像像素」換算完全一致，模型回傳的正規化座標換回經緯度的往返誤差 < 1 cm。

**熱讀取。** `prompts/` 與 `models.yaml` 每次呼叫模型時重新從磁碟讀取，
改完存檔下一次分析就生效，不必重啟服務。

**快取指紋涵蓋程式碼。** `cache.fingerprint()` 對 `models.yaml`、`prompts/*.md`
與後端所有 `.py` 取雜湊。改了評分標準或繪圖配色，舊快取自動失效，
不會拿與現行程式不符的舊結果去 demo。

---

## API

| 方法 | 路徑 | 說明 |
|---|---|---|
| `POST` | `/api/analyze` | `{lat, lng, size_m, force}` → 完整分析結果 |
| `GET` | `/api/health` | 金鑰、影像來源、prompt、案例數、快取狀態 |
| `GET` | `/api/cases` | 經典案例清單 |
| `GET` | `/api/session/{id}` | 該次分析暫存在記憶體的內容 |
| `GET` | `/api/cache` | 目前指紋下可用的快取 |
| `DELETE` | `/api/cache` | 清空快取 |

`verdict` 三種：`no_problem`、`not_intersection`、`improved`。

---

## 外部依賴

| 服務 | 用途 | 需要金鑰 |
|---|---|---|
| Gemini API | 全部七個代理人角色 | ✅ `GEMINI_API_KEY` |
| Overpass API | OSM 向量資料 | ❌ 公共節點，依 IP 限流 |
| Google Static Maps | 衛星影像（首選） | ⭕ `GOOGLE_MAPS_API_KEY`，可省略 |
| Esri World Imagery | 衛星影像（備援） | ❌ 免金鑰 |
| OpenStreetMap 圖磚 | 前端選點地圖 | ❌ |
