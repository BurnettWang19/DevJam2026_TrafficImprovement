# 部署

單一容器：Vue 的 build 產物由 FastAPI 直接 serve，一個服務、一個網址、不用設 CORS。
映像是平台中立的 —— Cloud Run、Render、Fly.io、Railway 都能直接跑同一個 image。

---

## 本機驗證（已通過）

```powershell
docker build -t intersection-audit .
docker run --rm -p 8080:8080 --env-file .env intersection-audit
```

開 http://localhost:8080 。實測：映像 509 MB、快取命中 448 ms、中文字型正常。

---

## Cloud Run

### 前置

1. **專案要綁定帳單帳戶。** Cloud Run 沒有免帳單的方案，這是硬性要求。
2. **安裝 gcloud CLI**（https://cloud.google.com/sdk/docs/install），
   或改用 Cloud Shell（https://shell.cloud.google.com，瀏覽器內建、免安裝）。

### 建立專案卡在 organization 時

Console 的 organization 欄位不會告訴你原因。用 CLI 診斷：

```bash
gcloud projects list          # 主辦方可能已經開好專案了，有就直接用
gcloud organizations list     # 空的就代表本來就該選「No organization」
gcloud beta billing accounts list
gcloud projects create probe-$RANDOM   # 失敗訊息會明確指出是權限還是政策
```

### 部署

```bash
PROJECT=你的專案ID
REGION=asia-east1

gcloud config set project $PROJECT
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
                       artifactregistry.googleapis.com

# 金鑰放 Secret Manager，不要用 --set-env-vars 直接寫在指令裡
gcloud services enable secretmanager.googleapis.com
printf '%s' "你的GEMINI金鑰" | gcloud secrets create gemini-api-key --data-file=-

gcloud run deploy intersection-audit \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --concurrency 4 \
  --min-instances 1 \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest
```

拿到 Google Maps 金鑰之後再加：

```bash
printf '%s' "你的MAPS金鑰" | gcloud secrets create google-maps-api-key --data-file=-
gcloud run services update intersection-audit --region $REGION \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest,GOOGLE_MAPS_API_KEY=google-maps-api-key:latest
```

### 為什麼是這些參數

| 參數 | 原因 |
|---|---|
| `--timeout 600` | 單次分析約 120 秒，預設 300 秒餘裕不足。上限 3600 |
| `--memory 2Gi` | Pillow 圖磚拼接 + 6~7 MB 的回應 payload |
| `--cpu 2` | 三個子代理人平行呼叫時不要卡住 |
| `--concurrency 4` | 請求又長又吃記憶體，塞太多同一個實例會 OOM |
| `--min-instances 1` | 避免冷啟動。demo 期間開著，結束後改回 0 省錢 |

---

## 快取在雲端的行為

Cloud Run 是無狀態的，容器重啟 `.cache/` 就沒了。目前的做法是**把預熱快取打包進映像**：

```powershell
# 部署前先在本機跑
cd backend
python prewarm.py --prune    # 清掉舊指紋的垃圾（實測可省 88 MB）
python prewarm.py            # 產生現行版本的快取
cd ..
docker build -t intersection-audit .
```

映像裡的快取是唯讀的起始狀態。線上跑出來的新結果會寫進容器的暫存層，
**實例回收就消失**，這對 demo 沒有影響（示範座標已經預熱好了）。

不想打包快取的話，把 `.dockerignore` 裡的 `backend/.cache/` 那行取消註解。

> 注意：`cache.fingerprint()` 涵蓋 `prompts/`、`models.yaml` 與後端所有 `.py`。
> 改過任何一個就要重跑 `prewarm.py` 再重建映像，否則線上會是 cache miss（等 2 分鐘）。

---

## 不用 GCP 的備援

帳單卡住時，同一個 Dockerfile 可以直接用在：

| 平台 | 免費方案 | 注意 |
|---|---|---|
| **Render** | 有，不需信用卡 | 免費方案會休眠，冷啟動約 50 秒 |
| **Fly.io** | 有額度 | 需綁卡驗證 |
| **Railway** | 試用額度 | 用完要付費 |

Render 為例：連 GitHub repo → New Web Service → 選 Docker → 環境變數填 `GEMINI_API_KEY` → Deploy。
不需要改任何程式碼。

---

## 環境變數

| 變數 | 必填 | 說明 |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | 七個代理人角色都用這把 |
| `GOOGLE_MAPS_API_KEY` | | 留空會自動改用 Esri World Imagery（免金鑰） |
| `PORT` | | 平台會自動注入，預設 8080 |
| `HOST` | | 容器內為 `0.0.0.0`，本機開發預設 `127.0.0.1` |
