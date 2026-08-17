<script setup>
import { onMounted, reactive, ref } from 'vue'
import HistoryView from './components/HistoryView.vue'
import MapPicker from './components/MapPicker.vue'
import TraceTimeline from './components/TraceTimeline.vue'
import ResultPanel from './components/ResultPanel.vue'

const page = ref(window.location.hash === '#history' ? 'history' : 'analysis')
const form = reactive({ lat: 25.0417, lng: 121.549, sizeM: 140 })
const latText = ref(String(form.lat))
const lngText = ref(String(form.lng))

const loading = ref(false)
const forcing = ref(false)
const error = ref('')
const result = ref(null)
const health = ref(null)
const mapRef = ref(null)

const PRESETS = [
  { name: '忠孝東路×敦化南路', lat: 25.0417, lng: 121.549, size: 140 },
  { name: '信義路五段（測非路口）', lat: 25.033139, lng: 121.564469, size: 120 },
  { name: '台灣大道×文心路', lat: 24.163889, lng: 120.646111, size: 160 },
  { name: '阿姆斯特丹', lat: 52.350556, lng: 4.868889, size: 140 },
]

async function refreshHealth() {
  try { health.value = await (await fetch('/api/health')).json() } catch { health.value = { ok: false } }
}
onMounted(refreshHealth)

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

function navigate(target) {
  page.value = target
  window.location.hash = target === 'history' ? 'history' : ''
}

function openHistoryResult(saved) {
  result.value = saved
  navigate('analysis')
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
    refreshHealth()
  }
}
</script>

<template>
  <HistoryView v-if="page === 'history'" @open-result="openHistoryResult" />

  <div v-else class="app">
    <aside>
      <header>
        <p class="eyebrow">Road Design Review</p>
        <h1>路口設計品質分析</h1>
        <p class="lede">OSM 向量與影像辨識彙整，經多重代理人評估後重繪改善設計。</p>
        <button class="history-link" @click="navigate('history')">查看分析歷史</button>
      </header>

      <div class="card">
        <label>中心點座標</label>
        <div class="grid2">
          <input v-model="latText" placeholder="緯度" @change="applyText" />
          <input v-model="lngText" placeholder="經度" @change="applyText" />
        </div>

        <label>範圍邊長 <b class="mono">{{ form.sizeM }} m</b></label>
        <input type="range" min="40" max="400" step="10" v-model.number="form.sizeM" class="range" />

        <button class="primary full" :disabled="loading" @click="analyze(false)">
          {{ loading && !forcing ? '分析中…' : '開始分析' }}
        </button>
        <button class="full rerun" :disabled="loading" @click="analyze(true)"
                title="忽略快取，實際重新呼叫所有代理人（約 2 分鐘）">
          {{ forcing ? '重新分析中…（約 2 分鐘）' : '↻ 重新分析（跳過快取）' }}
        </button>

        <div class="presets">
          <button v-for="p in PRESETS" :key="p.name" @click="usePreset(p)">{{ p.name }}</button>
        </div>
      </div>

      <div class="card map-card">
        <MapPicker ref="mapRef" :lat="form.lat" :lng="form.lng" :size-m="form.sizeM"
                   @pick="onPick" />
        <p class="hint">點地圖任一處即可設定中心點</p>
      </div>

      <div class="card" v-if="result?.trace?.length">
        <p class="eyebrow">Pipeline</p>
        <TraceTimeline :trace="result.trace" />
      </div>

      <div class="card status" v-if="health">
        <p class="eyebrow">Status</p>
        <ul>
          <li :class="health.gemini_api_key ? 'ok' : 'no'">Gemini 金鑰</li>
          <li :class="health.imagery_ready ? 'ok' : 'no'">
            衛星影像 · {{ health.imagery_provider }}
          </li>
          <li :class="health.scorer_prompt_filled ? 'ok' : 'no'">評分標準</li>
          <li :class="health.classic_cases ? 'ok' : 'no'">經典案例 {{ health.classic_cases }} 筆</li>
          <li :class="health.cache_entries ? 'ok' : 'no'">預熱快取 {{ health.cache_entries }} 筆</li>
        </ul>
      </div>
    </aside>

    <main>
      <div v-if="error" class="card err">分析失敗：{{ error }}</div>

      <div v-else-if="loading" class="card placeholder">
        <div class="spinner"></div>
        <p v-if="forcing">
          正在實際重新分析：擷取 OSM 向量與衛星影像 → 影像辨識補上車道標線 →
          評分 → 路口分類 → 三個代理人平行診斷 → 重繪設計 → 生成圖面 → 彙整說明。
          約需 2 分鐘。
        </p>
        <p v-else>正在分析…</p>
      </div>

      <ResultPanel v-else-if="result" :result="result" @back="result = null" />

      <div v-else class="card placeholder intro">
        <p class="eyebrow">Getting Started</p>
        <h2>輸入一組經緯度，開始分析</h2>
        <ol>
          <li>自 OpenStreetMap 擷取範圍內的人行道、斑馬線與道路向量</li>
          <li>由影像辨識補上 OSM 未涵蓋的車道標線、停止線與槽化線</li>
          <li>依評分標準判斷此路口是否為良好的道路設計</li>
          <li>有問題則判斷路口型態，非路口即中斷並回報</li>
          <li>三個代理人分頭診斷斑馬線、人行道與車道標線</li>
          <li>重繪符合標準的設計、生成圖面，並對照經典案例產出說明</li>
        </ol>
      </div>
    </main>
  </div>
</template>

<style scoped>
.app { display: grid; grid-template-columns: 340px 1fr; height: 100%; }

aside {
  border-right: 1px solid var(--line);
  background: var(--bg-sunken);
  padding: 24px 20px;
  overflow-y: auto;
  display: flex; flex-direction: column; gap: 16px;
}
aside header h1 {
  margin: 0 0 8px; font-size: 22px; font-weight: 800;
  color: var(--green-900); letter-spacing: -.01em;
}
.lede { margin: 0; font-size: 13px; color: var(--text-2); }
.history-link { margin-top: 12px; font-size: 12.5px; }

main { padding: 32px 36px 64px; overflow-y: auto; }

label { display: block; font-size: 12.5px; color: var(--text-2); margin: 14px 0 7px; }
label:first-child { margin-top: 0; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.range { padding: 0; accent-color: var(--green-700); }
.full { width: 100%; margin-top: 16px; }
.rerun { margin-top: 8px; font-size: 12.5px; }

.presets { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 14px; }
.presets button { font-size: 12px; padding: 5px 11px; border-radius: 999px; }

.map-card { padding: 10px; }
.map-card > :deep(.map) { height: 250px; }
.hint { font-size: 12px; margin: 9px 0 2px; text-align: center; color: var(--muted); }

.status ul { list-style: none; padding: 0; margin: 0; font-size: 13px; }
.status li { color: var(--text-2); }
.status li::before {
  content: '✕'; display: inline-block; width: 18px; color: #a8412c; font-weight: 700;
}
.status li.ok::before { content: '✓'; color: var(--green-600); }

.err { border-left: 3px solid #a8412c; color: #8c3826; }

.placeholder { color: var(--text-2); max-width: 720px; }
.placeholder h2 { color: var(--green-900); font-size: 25px; font-weight: 800; margin: 0 0 14px; }
.placeholder ol { padding-left: 20px; margin: 0; display: flex; flex-direction: column; gap: 7px; }
.intro { padding: 34px 38px; }

.spinner {
  width: 26px; height: 26px; border-radius: 50%;
  border: 3px solid var(--line); border-top-color: var(--green-700);
  animation: spin .9s linear infinite; margin-bottom: 14px;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 900px) {
  .app { grid-template-columns: 1fr; height: auto; }
  aside { border-right: none; border-bottom: 1px solid var(--line); }
  main { padding: 24px 18px 48px; }
}
</style>
