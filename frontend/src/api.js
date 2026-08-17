/**
 * API 位址解析。
 *
 * 兩種部署模式共用同一份程式碼：
 *
 *   單一容器（FastAPI 同時 serve 前端）
 *     VITE_API_BASE 留空 → 走相對路徑 /api/...，沒有跨網域問題。
 *
 *   前後端分離（例如 Firebase Hosting + Render）
 *     建置時給 VITE_API_BASE=https://your-backend.onrender.com
 *     → 打絕對網址，後端的 CORS 已允許跨來源。
 *
 * 開發時 vite.config.js 的 proxy 會把 /api 轉給 127.0.0.1:8000，
 * 所以本機開發也是留空即可。
 */
const BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/+$/, '')

export function apiUrl(path) {
  return BASE + (path.startsWith('/') ? path : `/${path}`)
}

export async function apiGet(path) {
  const res = await fetch(apiUrl(path))
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function apiPost(path, body) {
  const res = await fetch(apiUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
  return data
}
