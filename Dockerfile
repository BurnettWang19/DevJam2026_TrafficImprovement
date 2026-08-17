# ---------------------------------------------------------------------------
# 單一容器：Vue build 產物由 FastAPI 直接 serve。
# 一個服務、一個網址、不用設 CORS。
#
# 本機建置與測試：
#   docker build -t intersection-audit .
#   docker run --rm -p 8080:8080 --env-file .env intersection-audit
#   → http://localhost:8080
#
# 這個映像是平台中立的，Cloud Run / Render / Fly.io / Railway 都能直接跑。
# ---------------------------------------------------------------------------

# ---- 階段 1：建前端 --------------------------------------------------------
FROM node:22-slim AS frontend

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
# 要裝含 devDependencies 的完整依賴 —— vite 本身就在 devDependencies 裡。
# 這一層是建置階段，不會進最終映像。
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build


# ---- 階段 2：執行 ---------------------------------------------------------
FROM python:3.13-slim

# Pillow 的 wheel 已含所需的原生庫，這裡只補中日韓字型 ——
# 沒有它，向量圖的中文圖例與改動標籤會變成一排空白方塊。
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-noto-cjk \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    HOST=0.0.0.0

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 程式碼與資料
COPY backend/ ./backend/
COPY example/ ./example/

# 前端 build 產物（main.py 會自動偵測並掛載）
COPY --from=frontend /app/frontend/dist ./frontend/dist

# 預熱快取（選用）。要打包就先在本機跑：
#   python prewarm.py --prune
# 目錄不存在時這行不會失敗，因為上面的 COPY backend/ 已經把它帶進來了。
# 不想打包的話，把 backend/.cache 加進 .dockerignore 即可。

EXPOSE 8080

# 分析單次要 2 分鐘，worker 逾時要放寬；Cloud Run 自己會做水平擴展，
# 所以這裡只跑單一 worker，避免同一個容器內搶 CPU。
CMD ["python", "-m", "uvicorn", "main:app", \
     "--host", "0.0.0.0", "--port", "8080", \
     "--app-dir", "backend", \
     "--timeout-keep-alive", "75", \
     "--workers", "1"]
