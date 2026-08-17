<script setup>
import { onMounted, reactive, ref } from 'vue'
import MapPicker from './components/MapPicker.vue'
import TraceTimeline from './components/TraceTimeline.vue'
import ResultPanel from './components/ResultPanel.vue'

const form = reactive({ lat: 25.041629, lng: 121.543205, sizeM: 120 })
const latText = ref(String(form.lat))
const lngText = ref(String(form.lng))

const loading = ref(false)
const forcing = ref(false)
const error = ref('')
const result = ref(null)
const health = ref(null)
const mapRef = ref(null)

const PRESETS = [
  { name: '台北 忠孝東路×敦化南路', lat: 25.0417, lng: 121.549, size: 140 },
  { name: '台北 信義路五段（路段，測非路口）', lat: 25.033139, lng: 121.564469, size: 120 },
  { name: '台中 台灣大道×文心路', lat: 24.163889, lng: 120.646111, size: 160 },
  { name: '阿姆斯特丹', lat: 52.350556, lng: 4.868889, size: 140 },
]

onMounted(async () => {
  try {
    health.value = await (await fetch('/api/health')).json()
  } catch {
    health.value = { ok: false }
  }
})

function onPick(lat, lng) {
  form.lat = +lat.toFixed(6)
  form.lng = +lng.toFixed(6)
  latText.value = String(form.lat)
  lngText.value = String(form.lng)
}

function applyText() {
  const la = parseFloat(latText.value)
  const ln = parseFloat(lngText.value)
  if (Number.isFinite(la) && Number.isFinite(ln)) {
    form.lat = la
    form.lng = ln
    mapRef.value?.flyTo(la, ln)
  }
}

function usePreset(p) {
  onPick(p.lat, p.lng)
  if (p.size) form.sizeM = p.size
  mapRef.value?.flyTo(p.lat, p.lng)
}

async function analyze(force = false) {
  loading.value = true
  forcing.value = force
  error.value = ''
  result.value = null
  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lat: form.lat, lng: form.lng, size_m: form.sizeM, force }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
    result.value = data
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
    forcing.value = false
    try { health.value = await (await fetch('/api/health')).json() } catch { /* 非關鍵 */ }
  }
}
</script>

<template>
  <div class="app">
    <aside>
      <header>
        <h1>路口設計品質分析</h1>
        <p class="muted">OSM 向量 + Gemini 視覺辨識 → 多 Agent 評估 → 重繪改善設計</p>
      </header>

      <div class="card">
        <label>中心點座標</label>
        <div class="grid2">
          <input v-model="latText" placeholder="緯度 lat" @change="applyText" />
          <input v-model="lngText" placeholder="經度 lng" @change="applyText" />
        </div>

        <label>正方形範圍邊長：<b class="mono">{{ form.sizeM }} m</b></label>
        <input type="range" min="40" max="400" step="10" v-model.number="form.sizeM" class="range" />

        <button class="primary full" :disabled="loading" @click="analyze(false)">
          {{ loading && !forcing ? '分析中…' : '開始分析' }}
        </button>
        <button class="full rerun" :disabled="loading" @click="analyze(true)"
                title="忽略快取，實際重新呼叫所有 Agent（約 2 分鐘）">
          {{ forcing ? '重新分析中…（約 2 分鐘）' : '↻ 重新分析（跳過快取）' }}
        </button>

        <div class="presets">
          <button v-for="p in PRESETS" :key="p.name" @click="usePreset(p)">{{ p.name }}</button>
        </div>
      </div>

      <div class="card map-card">
        <MapPicker ref="mapRef" :lat="form.lat" :lng="form.lng" :size-m="form.sizeM"
                   @pick="onPick" />
        <p class="muted hint">點地圖任一處即可設定中心點</p>
      </div>

      <div class="card" v-if="result?.trace?.length">
        <h3>流程</h3>
        <TraceTimeline :trace="result.trace" />
      </div>

      <div class="card status" v-if="health">
        <h3>環境檢查</h3>
        <ul>
          <li :class="health.gemini_api_key ? 'ok' : 'no'">
            GEMINI_API_KEY
            <small v-if="!health.gemini_api_key">（必填，aistudio.google.com/apikey）</small>
          </li>
          <li :class="health.imagery_ready ? 'ok' : 'no'">
            衛星影像：{{ health.imagery_provider }}
            <small v-if="health.imagery_provider === 'esri'">（免金鑰備援）</small>
          </li>
          <li :class="health.scorer_prompt_filled ? 'ok' : 'no'">
            評分 system prompt
            <small v-if="!health.scorer_prompt_filled">（空白，使用內建暫用標準）</small>
          </li>
          <li :class="health.classic_cases ? 'ok' : 'no'">
            經典案例 {{ health.classic_cases }} 筆
          </li>
          <li :class="health.cache_entries ? 'ok' : 'no'">
            預熱快取 {{ health.cache_entries }} 筆
            <small v-if="!health.cache_entries">（跑 python prewarm.py）</small>
          </li>
        </ul>
      </div>
    </aside>

    <main>
      <div v-if="error" class="card err">分析失敗：{{ error }}</div>

      <div v-else-if="loading" class="card placeholder">
        <div class="spinner"></div>
        <p v-if="forcing">
          正在實際重新分析：擷取 OSM 向量與衛星影像 → Gemini 視覺辨識 →
          評分 Agent → 路口分類 → 三個 Sub Agent 平行找問題 → 重繪設計 →
          生成設計圖 → 彙整報告。約需 2 分鐘。
        </p>
        <p v-else>正在分析…</p>
      </div>

      <ResultPanel v-else-if="result" :result="result" />

      <div v-else class="card placeholder">
        <h2>輸入一組經緯度，開始分析</h2>
        <ol>
          <li>後端向 OpenStreetMap 擷取範圍內的人行道、斑馬線等現成向量資料</li>
          <li>Gemini 從衛星影像辨識 OSM 沒有的車道線、停止線、槽化線</li>
          <li>評分 Agent 依你提供的 system prompt 判斷是否為「好的道路設計」</li>
          <li>有問題 → 判斷路口類型（非路口則中斷）→ 三個 Sub Agent 分頭找問題</li>
          <li>重繪符合標準的設計向量圖 → 生成圖片 → 對照經典案例產出說明</li>
        </ol>
      </div>
    </main>
  </div>
</template>

<style scoped>
.app { display: grid; grid-template-columns: 380px 1fr; height: 100%; }

aside {
  border-right: 1px solid var(--line);
  padding: 18px;
  overflow-y: auto;
  display: flex; flex-direction: column; gap: 14px;
  background: #0d1117;
}
header h1 { margin: 0 0 4px; font-size: 19px; }
header p { margin: 0; font-size: 12.5px; }

main { padding: 18px; overflow-y: auto; }

label { display: block; font-size: 12.5px; color: var(--muted); margin: 10px 0 6px; }
label:first-child { margin-top: 0; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.range { padding: 0; accent-color: var(--accent); }
.full { width: 100%; margin-top: 14px; }
.rerun { margin-top: 8px; font-size: 12.5px; }

.presets { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
.presets button { font-size: 12px; padding: 5px 10px; }

.map-card { padding: 10px; }
.map-card > :deep(.map) { height: 260px; }
.hint { font-size: 12px; margin: 8px 0 0; text-align: center; }

h3 { margin: 0 0 10px; font-size: 14px; }

.status ul { list-style: none; padding: 0; margin: 0; font-size: 13px; }
.status li::before { content: '✕'; display: inline-block; width: 18px; color: var(--bad); }
.status li.ok::before { content: '✓'; color: var(--accent); }
.status li small { color: var(--muted); }

.err { border-left: 3px solid var(--bad); color: #fca5a5; }

.placeholder { color: var(--muted); }
.placeholder h2 { color: var(--text); font-size: 17px; margin: 0 0 12px; }
.placeholder ol { padding-left: 20px; margin: 0; display: flex; flex-direction: column; gap: 6px; }

.spinner {
  width: 26px; height: 26px; border-radius: 50%;
  border: 3px solid var(--line); border-top-color: var(--accent);
  animation: spin 0.9s linear infinite; margin-bottom: 12px;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 900px) {
  .app { grid-template-columns: 1fr; height: auto; }
  aside { border-right: none; border-bottom: 1px solid var(--line); }
}
</style>
