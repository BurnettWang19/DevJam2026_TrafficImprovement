# Road Intersection AI Backend Implementation Plan

## 1. 目標與完成條件

建立一條可由 FastAPI 呼叫的路口分析工作流：

1. 接收中心點經緯度與正方形分析範圍。
2. 依範圍從 OpenStreetMap 擷取道路、人行道、斑馬線及其他既有向量資料。
3. 取得相同範圍的合法航空或衛星影像，交由 Gemini 補充 OSM 未涵蓋的車道線等向量資料。
4. 載入外部 system prompt，評估路口設計是否有重大問題。
5. 無重大問題時回傳 `NO_PROBLEM`。
6. 有問題時判斷路口類型；若不是路口則回傳 `NOT_INTERSECTION` 並停止後續流程。
7. 分別分析斑馬線、人行道、車道標線問題，保存各項問題與建議。
8. 重新產生符合標準的道路設計向量圖。
9. 將新版向量設計轉成成果圖片。
10. 查詢經典案例，回傳原有問題、相似案例、新版改善方式、向量資料與成果圖片。
11. FastAPI 容器可部署至 Google Cloud Run。

本計畫不包含自動化測試撰寫或測試執行。

## 2. 重要技術決策

### 2.1 正方形範圍

現有 `radiusMeters` 是圓形語意。新增 `sideLengthMeters` 作為正方形完整邊長，後端以中心點計算 WGS84 bounding box。為避免前後端同時存在兩種定義，新端點只接受 `sideLengthMeters`。

### 2.2 Gemini 模型

所有模型名稱由環境變數提供，不散落在程式碼中：

- `GEMINI_VISION_MODEL`：影像理解與缺漏向量抽取。
- `GEMINI_REASONING_MODEL`：品質評分、路口分類、三個問題 Agent 與向量重畫。
- `GEMINI_IMAGE_MODEL`：成果圖片生成。

需求指定的 `gemini-3.5-flash` 可處理文字、圖片輸入及 structured output，但不支援圖片生成，因此成果圖必須使用獨立的 image-capable 模型。`gemini-1.5-flash` 保留為可配置值，但部署前須用 Models API 確認專案仍可使用；若不可用，只更換環境變數，不改工作流程式碼。

### 2.3 影像來源

OSM 只提供向量，不提供可讓 Gemini 辨識車道線的航空影像。建立 `ImageryProvider` 介面，第一版選定一個具合法 API 與使用授權的來源。若使用 Google Static Maps，金鑰放在 Secret Manager；若使用其他供應商，只替換 adapter。

### 2.4 記憶體與 Cloud Run

不得使用 module-level dict 保存工作狀態。Cloud Run 可能同時處理多個請求、重啟或水平擴展。

MVP 採單次同步工作流：建立 `AnalysisContext` 物件，問題、模型輸出及中間向量都放在此物件，並顯式傳給下一個 Agent。資料只需存活到單次請求完成。若未來改為背景工作或前端輪詢，再導入 Firestore；不在本次 MVP 範圍內。

### 2.5 Agent 定義

本案的 Sub Agent 是後端內部、具固定輸入輸出 schema 的模型工作節點，不建立可自行無限循環或任意呼叫工具的自治 Agent。每個節點最多呼叫模型一次；JSON schema 驗證失敗時只允許一次格式修正呼叫。

## 3. 建議目錄結構

```text
backend/
  .env.example
  prompts/
    intersection_evaluation_system_prompt.md  # 空白，由使用者貼上評分 prompt
  classic_cases/
    README.md
    case-id/
      metadata.json
      before.webp
      after.webp
  app/
    api/
      analyses.py
    agents/
      evaluator.py
      intersection_classifier.py
      crosswalk_agent.py
      sidewalk_agent.py
      lane_marking_agent.py
      redesign_agent.py
      render_agent.py
    core/
      config.py
      prompt_loader.py
    schemas/
      analysis_request.py
      analysis_result.py
      agent_outputs.py
    services/
      analysis_orchestrator.py
      gemini/client.py
      geospatial/bounds.py
      imagery/provider.py
      imagery/google_static_maps.py
      osm/client.py
      osm/parser.py
      vector/fusion.py
      vector/validation.py
      cases/repository.py
      cases/matcher.py
  Dockerfile
```

## 4. API 契約

新增端點：

```http
POST /api/analyses
```

Request：

```json
{
  "latitude": 25.033,
  "longitude": 121.5654,
  "sideLengthMeters": 200
}
```

Response 的 `status` 固定為以下其中之一：

- `NO_PROBLEM`
- `NOT_INTERSECTION`
- `IMPROVEMENT_PROPOSED`
- `ANALYSIS_FAILED`

成功改善結果至少包含：

```json
{
  "analysisId": "uuid",
  "status": "IMPROVEMENT_PROPOSED",
  "intersectionType": "ORTHOGONAL",
  "bounds": {},
  "originalGeojson": {},
  "enrichedGeojson": {},
  "redesignedGeojson": {},
  "findings": [],
  "score": {},
  "matchedCases": [],
  "problemSummary": "",
  "improvementSummary": "",
  "renderedImage": {
    "mimeType": "image/webp",
    "dataUrl": "data:image/webp;base64,..."
  }
}
```

MVP 可直接回傳 data URL。若圖片超過 Cloud Run／代理層可接受大小，再改為上傳 Cloud Storage 並回傳 signed URL；此時才新增儲存服務。

## 5. 分階段實作

### Phase 1：設定、schema 與 prompt 載入

1. 在 `pyproject.toml` 加入官方 Google Gen AI Python SDK 與圖片處理套件。
2. 擴充 `Settings`，加入 Gemini、影像來源、模型名稱、prompt 路徑與請求限制。
3. 建立空白 `backend/prompts/intersection_evaluation_system_prompt.md`。
4. 建立 `PromptLoader`：每次模型評分呼叫前從檔案讀取，不做常駐快取。
5. 若 prompt 為空白，回傳明確的 `EVALUATION_PROMPT_EMPTY`，不得使用內建替代評分規則。
6. 建立請求、工作流 context、各 Agent structured output 及最終回應 schema。

完成條件：所有工作流資料都有明確 Pydantic 型別，模型輸出不可直接以自由文字傳入下一階段。

### Phase 2：正方形邊界與 OSM 向量擷取

1. 依中心點與邊長計算正方形 bounding box。
2. 將現有 Overpass 查詢改為 bbox，並擷取：
   - `highway` 道路中心線
   - `highway=footway/path/pedestrian`
   - `footway=sidewalk/crossing`
   - `crossing=*`
   - `sidewalk=*`
   - `traffic_signals`
   - `stop`、`give_way`
   - `traffic_calming`
   - `cycleway=*`
   - `lanes`、`turn:lanes`、`width`
3. 將 OSM node、way 與 tag 正規化為現有 `IntersectionScene`／GeoJSON。
4. 每個 feature 保留 `sources=["OSM"]`、OSM ID、原始 tags 與 confidence。

完成條件：API 可以用正方形範圍回傳分類後的道路、人行道、斑馬線及輔助設施。

### Phase 3：影像取得與 Gemini 向量補全

1. 以相同 bbox 取得固定尺寸、固定縮放比例的影像。
2. 將影像、bbox、像素尺寸與 OSM GeoJSON 一起送入 vision model。
3. 要求 structured output，只補充可被影像支持的項目：車道線、停止線、導流線、轉向箭頭、缺漏斑馬線及可見道路邊界。
4. 模型先輸出 pixel coordinates，再由後端依影像投影資訊轉回 WGS84；不可要求模型直接猜經緯度。
5. `VectorFusionService` 合併 OSM 與模型結果：
   - OSM 幾何優先。
   - 模型不得覆寫來源明確的 OSM feature。
   - 模型新增 feature 標記 `sources=["GEMINI_VISION"]` 與 confidence。
   - 低於門檻的 feature 保留為 warning，不進入自動設計依據。

完成條件：取得含來源與 confidence 的 `enrichedGeojson`，且像素至地理座標轉換可追溯。

### Phase 4：總評分與流程分支

1. `EvaluatorAgent` 每次呼叫時讀取空白 prompt 檔案的最新內容，作為 system instruction。
2. User message 只放路口向量、可計算指標與要求的 JSON schema，不重複或改寫評分標準。
3. 輸出整體分數、各準則分數、重大問題布林值、證據 feature IDs 與簡短理由。
4. 若無重大問題，立即組裝 `NO_PROBLEM` 回應，不呼叫後續 Agent。
5. 若有重大問題，呼叫 `IntersectionClassifierAgent`，分類 enum：
   - `ORTHOGONAL`
   - `T_JUNCTION`
   - `SKEWED`
   - `ROUNDABOUT`
   - `MULTI_LEG`
   - `OTHER_INTERSECTION`
   - `NOT_INTERSECTION`
6. 若為 `NOT_INTERSECTION`，立即回傳並停止工作流，不使用迴圈重試分類。

完成條件：`NO_PROBLEM` 與 `NOT_INTERSECTION` 都能在正確節點提前結束，不產生改善圖。

### Phase 5：三個專責問題 Agent

三個 Agent 可用 `asyncio.gather` 平行呼叫，但只讀取同一份 immutable context：

1. `CrosswalkAgent`：檢查位置、退縮距離、穿越距離、連續性、庇護空間與車流衝突。
2. `SidewalkAgent`：檢查連續性、有效寬度、轉角停等空間、無障礙銜接與障礙物。
3. `LaneMarkingAgent`：檢查偏心左轉、導流、停止線、轉向車道、路口內軌跡與行人／自行車衝突。

每個 Agent 輸出：問題、嚴重度、證據 feature IDs、適用限制、建議 geometry operations。結果寫入當次請求的 `AnalysisContext.findings`，禁止寫入全域狀態。

完成條件：三類結果互相獨立、格式一致，並能追溯到原始或 Gemini 補充的 feature。

### Phase 6：向量重畫與幾何驗證

1. `RedesignAgent` 讀取 enriched scene、評分 prompt、路口類型及三個問題結果。
2. Agent 不直接輸出任意 GeoJSON，而是輸出受限操作指令，例如：
   - move crosswalk
   - shorten crossing
   - add refuge island
   - extend sidewalk corner
   - offset lane centerline
   - add or move stop line
   - add protected bike segment
3. `GeometryPlanner` 以 Shapely／PyProj 執行操作，確保尺度使用當地投影公尺單位。
4. `VectorValidator` 檢查幾何有效性、範圍越界、線段自交、跨越不可行區域及 feature 關聯。
5. 無法安全套用的操作保留成文字建議，不強行產生幾何。

完成條件：`redesignedGeojson` 是後端幾何運算結果，不是未驗證的模型座標。

### Phase 7：成果圖、經典案例與文字說明

1. `ClassicCaseRepository` 掃描 `backend/classic_cases/*/metadata.json`。
2. 經典案例 metadata 至少包含路口類型、問題標籤、解法標籤、適用條件、限制、來源 URL、圖片檔名與授權資訊。
3. `CaseMatcher` 第一版使用可解釋的加權匹配：路口類型、問題標籤、道路規模及解法相似度；不為 MVP 引入向量資料庫。
4. 回傳最多 3 個案例，且每個案例附上匹配原因，不只給圖片。
5. `RenderAgent` 接收原始影像、新版向量疊圖與問題摘要，呼叫 image-capable model 生成成果圖。
6. 最終文字由已保存的 findings 組裝：
   - 原路口有哪些問題。
   - 對應哪些證據。
   - 哪個經典案例相似。
   - 新版設計做了什麼改變。
   - 哪些事項仍需現勘或交通工程師確認。
7. 成果圖必須標記為「概念示意」，不得表述為施工圖或正式交通工程核定成果。

完成條件：前端一次取得問題文字、經典案例、新版向量及可顯示的成果圖片。

### Phase 8：FastAPI 整合與錯誤處理

1. 新增 `/api/analyses` router，交由 `AnalysisOrchestrator` 執行固定工作流。
2. 保留既有 `/api/intersections`，避免破壞目前功能；前端完成遷移後再決定是否移除。
3. 定義穩定錯誤碼：
   - `INVALID_ANALYSIS_BOUNDS`
   - `NO_OSM_DATA`
   - `IMAGERY_FETCH_FAILED`
   - `GEMINI_MODEL_UNAVAILABLE`
   - `EVALUATION_PROMPT_EMPTY`
   - `MODEL_OUTPUT_INVALID`
   - `VECTOR_REDESIGN_FAILED`
   - `IMAGE_GENERATION_FAILED`
4. 模型與外部 API 設定個別 timeout；不得無限重試。
5. 日誌只記 analysis ID、階段、耗時、模型名稱與錯誤碼，不記 API key、完整 prompt 或 base64 圖片。

完成條件：任一階段失敗都回傳可供前端顯示的結構化錯誤。

### Phase 9：Cloud Run 部署

1. Dockerfile 改為 production dependencies，不安裝 `.[dev]`。
2. 啟動指令監聽 `0.0.0.0:$PORT`；Cloud Run 預設注入 `PORT`。
3. 建立 Artifact Registry，建置並推送 backend image。
4. 建立 Cloud Run service，設定 region、memory、CPU、request timeout、concurrency 與 max instances。
5. API key 放入 Secret Manager，再以 Cloud Run secret reference 注入；非敏感模型名稱與 URL 使用一般環境變數。
6. 設定 `CORS_ORIGINS` 為實際前端網域。
7. 若 API 對公開前端開放，Cloud Run 可允許 unauthenticated invoke；若要限制使用者，再另行加入 Firebase Auth 或 Identity Platform，不在 MVP 自動假設登入機制。

完成條件：Cloud Run URL 可提供 `/api/health` 與 `/api/analyses`，且程式不依賴容器本機的持久資料。

## 6. `.env.example` 規格

實作時加入下列欄位，只放假值，不填入真實憑證：

```dotenv
APP_NAME=Road Intersection AI
CORS_ORIGINS=["http://localhost:5173"]

OVERPASS_URL=https://overpass-api.de/api/interpreter
OSM_TIMEOUT_SECONDS=25

GEMINI_API_KEY=
GEMINI_VISION_MODEL=gemini-1.5-flash
GEMINI_REASONING_MODEL=gemini-3.5-flash
GEMINI_IMAGE_MODEL=
GEMINI_API_VERSION=v1
GEMINI_TIMEOUT_SECONDS=60

EVALUATION_PROMPT_PATH=prompts/intersection_evaluation_system_prompt.md

IMAGERY_PROVIDER=google_static_maps
GOOGLE_MAPS_API_KEY=
IMAGERY_WIDTH=1024
IMAGERY_HEIGHT=1024

CLASSIC_CASES_PATH=classic_cases
MAX_CLASSIC_CASE_MATCHES=3
```

Cloud Run 正式部署時，`GEMINI_API_KEY` 與 `GOOGLE_MAPS_API_KEY` 不應直接設為一般環境變數，而應由 Secret Manager 注入。

## 7. 需先確認的外部條件

開始實作前只需要確認以下事項：

1. 航空／衛星影像供應商及其影像能否送至 Gemini 處理、保存與展示。
2. Google Cloud project ID、部署 region 與 billing 是否已啟用。
3. Gemini API 使用 AI Studio API key 或 Vertex AI；本計畫預設 Gemini API key，若改 Vertex AI，設定與身分驗證需調整。
4. 帳號是否能使用指定的三個模型；以 Models API 結果為準。
5. `sideLengthMeters` 的產品允許範圍；建議 MVP 限制 20–500 公尺。
6. 經典案例圖片的著作權、引用方式與可否提供給模型處理。

## 8. 不納入本次 MVP

- 正式交通流量模擬與事故預測。
- 可直接施工的工程圖或法規核定。
- 長期跨請求 Agent 記憶。
- 向量資料庫及語意搜尋。
- 使用者登入、權限與付費。
- 背景佇列及工作進度輪詢。
- 自動化測試與測試執行。

## 9. 建議實作順序

依序完成 Phase 1 至 Phase 9。不得先做成果圖片再補向量資料，因為問題說明、案例匹配與圖片生成都依賴同一份已驗證的 `redesignedGeojson`。最先可交付的垂直切片是：正方形輸入 → OSM bbox → prompt 評分 → `NO_PROBLEM`／`NOT_INTERSECTION`／問題 JSON；其後再加入三 Agent、向量重畫、案例與圖片。
