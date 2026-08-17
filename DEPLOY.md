# 部署

**採用方案：前端 Firebase Hosting ＋ 後端 Render。** 兩邊都是免費方案，不需要帳單帳戶。

```
Firebase Hosting            Render
（Vue 前端 · 免費 · CDN）  →  （Python 後端 · 免費 · Docker）
   your-app.web.app              your-api.onrender.com
```

> **為什麼不用 Firebase 跑後端？** Cloud Functions 與 App Hosting 都只在 Blaze 方案提供，
> 而 Blaze 需要綁定帳單帳戶 —— 跟 Cloud Run 是同一道牆。
> Firebase 的免費 Spark 方案只能放靜態檔。

---

## 一、後端上 Render

### 1. 建立服務

到 https://render.com 用 GitHub 登入，授權存取這個 repo，然後：

**New + → Blueprint → 選這個 repo**

根目錄的 `render.yaml` 會自動帶入設定（Docker、singapore 區域、free 方案、
健康檢查指向 `/api/health`）。

> 找不到 Blueprint 也可以用 **New + → Web Service**，Language 選 **Docker**，
> Branch 選 `main`，Region 選 **Singapore**，Instance Type 選 **Free**。

### 2. 填金鑰

Environment → Add Environment Variable：

```
GEMINI_API_KEY = 你在 AI Studio 取得的金鑰
```

`GOOGLE_MAPS_API_KEY` 不用填，會自動改用 Esri World Imagery（免金鑰）。

### 3. 等建置

第一次約 5~10 分鐘（npm 依賴 + Python 套件 + 中文字型 + 快取）。

完成後開 `https://你的服務.onrender.com/api/health`，確認：

```json
{
  "gemini_api_key": true,
  "imagery_ready": true,
  "scorer_prompt_filled": true,
  "cache_entries": 8      ← 這項是關鍵，代表預熱快取有進映像
}
```

> **這個網址本身就是完整可用的 App。** 映像裡也包含前端 build 產物，
> FastAPI 會直接 serve。所以就算 Firebase 那邊出狀況，這個網址仍然能 demo。

---

## 二、前端上 Firebase Hosting

### 1. 安裝與登入

```powershell
npm install -g firebase-tools
firebase login
```

### 2. 綁定專案

你已經有一個專案 `gen-lang-client-0359154585`（AI Studio 自動建的），直接用：

```powershell
cd C:\Users\ianli\OneDrive\Desktop\DavJam_Project
firebase use --add gen-lang-client-0359154585
```

第一次會要你在 Firebase Console（https://console.firebase.google.com）
把這個 GCP 專案加入 Firebase —— 免費、不需要帳單。

### 3. 指向後端並建置

建立 `frontend/.env.production`（範本見 `.env.production.example`）：

```
VITE_API_BASE=https://你的服務.onrender.com
```

然後建置：

```powershell
cd frontend
npm run build
cd ..
```

### 4. 部署

```powershell
firebase deploy --only hosting
```

拿到 `https://<專案>.web.app`。

---

## 三、免費方案的三個限制（demo 前務必知道）

**1. Render 免費方案閒置 15 分鐘會休眠。**
冷啟動要拉 500 MB 映像，約 50 秒。**上台前 5 分鐘先開一次 `/api/health` 把它叫醒。**

**2. 免費實例只有 0.1 CPU / 512 MB RAM。**
- 快取命中的請求只是讀 JSON、回傳，資源需求極低 —— 示範座標不受影響。
- **「↻ 重新分析（跳過快取）」會真的跑 Pillow 圖磚拼接與四張圖繪製**，在 0.1 CPU 上
  會比本機慢很多，也有 OOM 的風險。部署後務必實測一次這個按鈕；
  真的跑不動就在現場改用本機跑，或升級到 Starter 方案（$7/月）。

**3. 快取是唯讀的起始狀態。**
線上跑出的新結果寫在容器暫存層，**實例休眠或重啟就消失**。
示範座標已經預熱進映像，所以不受影響。

---

## 四、改過東西之後要重跑什麼

| 你改了 | 要做什麼 |
|---|---|
| 前端（`frontend/src/**`） | `npm run build` → `firebase deploy --only hosting` |
| 後端程式碼、`prompts/`、`models.yaml` | **先 `python prewarm.py --prune` 再 `prewarm.py`**，然後 push 到 GitHub，Render 會自動重建 |
| 只改 `example/index.json`（經典案例） | push 即可，不必重跑 prewarm（案例是回應時才讀的） |

> `cache.fingerprint()` 涵蓋 `models.yaml`、`prompts/*.md` 與後端所有 `.py`。
> 改了任何一個而沒重跑 prewarm，線上會變成 cache miss，每次點都要等 2 分鐘。

---

## 五、本機驗證

```powershell
docker build -t intersection-audit .
docker run --rm -p 8080:8080 --env-file .env intersection-audit
```

開 http://localhost:8080 。實測：映像 509 MB、快取命中 448 ms、
中文字型 NotoSansCJK 正常、映像內不含 `.env`。

---

## Cloud Run 的快取陷阱

`gcloud run deploy --source .` 預設會拿 `.gitignore` 當作上傳的排除規則。
而 `backend/.cache/`（43 MB）刻意不進版控，於是**預熱快取不會跟著部署上去** ——
線上 `cache_entries` 會是 0，每次分析都得等兩分鐘。

根目錄的 `.gcloudignore` 就是為了解決這件事：它一旦存在，gcloud 就不再參考
`.gitignore`，而該檔案刻意「不」排除 `backend/.cache/`。

部署前務必先確認本機快取是最新的：

```powershell
cd backend
python prewarm.py --prune     # 清掉舊指紋的垃圾
python prewarm.py             # 補齊現行版本
python prewarm.py --list      # 確認筆數
cd ..
gcloud run deploy ...
```

部署完開 `/api/health` 對照 `cache_entries` 是否與本機一致。

> 若是走 GitHub 觸發 Cloud Build 而非 `--source .`，`.gcloudignore` 沒有作用 ——
> 那條路必須把 `backend/.cache/` 加入版控才會有快取。

---

## 附錄：改用 Cloud Run（需要帳單帳戶）

之後拿到帳單帳戶想搬過去的話：

```bash
PROJECT=你的專案ID
REGION=asia-east1

gcloud config set project $PROJECT
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
                       artifactregistry.googleapis.com secretmanager.googleapis.com

printf '%s' "你的GEMINI金鑰" | gcloud secrets create gemini-api-key --data-file=-

gcloud run deploy intersection-audit \
  --source . --region $REGION --allow-unauthenticated \
  --memory 2Gi --cpu 2 --timeout 600 --concurrency 4 --min-instances 1 \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest
```

| 參數 | 原因 |
|---|---|
| `--timeout 600` | 單次分析約 120 秒，預設 300 秒餘裕不足 |
| `--memory 2Gi` | Pillow 圖磚拼接 + 6~7 MB 的回應 payload |
| `--cpu 2` | 三個子代理人平行呼叫時不要卡住 |
| `--min-instances 1` | 避免冷啟動；demo 結束改回 0 停止計費 |

搬過去之後前端的 `VITE_API_BASE` 改成 Cloud Run 網址，重新 build 與 deploy 即可。

---

## 環境變數

| 變數 | 位置 | 必填 | 說明 |
|---|---|---|---|
| `GEMINI_API_KEY` | Render 後台 | ✅ | 七個代理人角色都用這把 |
| `GOOGLE_MAPS_API_KEY` | Render 後台 | | 留空自動改用 Esri（免金鑰） |
| `VITE_API_BASE` | `frontend/.env.production` | ✅ | 後端網址；留空則走相對路徑 |
| `PORT` / `HOST` | 平台自動注入 | | 容器內為 `8080` / `0.0.0.0` |
