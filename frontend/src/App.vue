<script setup>
import { onMounted, reactive, ref } from 'vue'
import MapPicker from './components/MapPicker.vue'
import TraceTimeline from './components/TraceTimeline.vue'
import ResultPanel from './components/ResultPanel.vue'
import SplashScreen from './components/SplashScreen.vue'
import RunnerLoader from './components/RunnerLoader.vue'
import { apiGet, apiPost } from './api'

const booting = ref(true)
const sidebarOpen = ref(true)

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
  try { health.value = await apiGet('/api/health') } catch { health.value = { ok: false } }
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

/* 分析完成後不直接切畫面：先讓小遊戲角色衝過終點線（gameDone → @finished）*/
const gameDone = ref(false)
let pendingResult = null

async function analyze(force = false) {
  loading.value = true
  forcing.value = force
  error.value = ''
  result.value = null
  gameDone.value = false
  pendingResult = null
  sidebarOpen.value = false        // 分析開始 → 收起左側欄，讓 loading 滿版
  try {
    pendingResult = await apiPost('/api/analyze', {
      lat: form.lat, lng: form.lng, size_m: form.sizeM, force,
    })
    gameDone.value = true          // 通知遊戲：放終點線
  } catch (e) {
    error.value = e.message
    loading.value = false
    forcing.value = false
    refreshHealth()
  }
}

function onGameFinished() {
  result.value = pendingResult
  pendingResult = null
  loading.value = false
  forcing.value = false
  refreshHealth()
}

function backToMap() {
  result.value = null
  error.value = ''
  sidebarOpen.value = true         // 回到選點畫面時把側欄拉回來
}
</script>

<template>
  <SplashScreen v-if="booting" @done="booting = false" />

  <div class="app" :class="{ collapsed: !sidebarOpen }" v-if="!booting">
    <aside>
      <header v-reveal>
        <p class="eyebrow">Road Design Review</p>
        <h1>路口設計品質分析</h1>
        <p class="lede">OSM 向量與影像辨識彙整，經多重代理人評估後重繪改善設計。</p>
      </header>

      <div class="card" v-reveal="{ delay: 80 }">
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

      <div class="card" v-if="result?.trace?.length">
        <p class="eyebrow">Pipeline</p>
        <TraceTimeline :trace="result.trace" />
      </div>

      <div class="card status" v-if="health" v-reveal="{ delay: 240 }">
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
      <!-- 側欄開合箭頭 -->
      <button class="edge-toggle" @click="sidebarOpen = !sidebarOpen"
              :title="sidebarOpen ? '收起側欄' : '展開側欄'"
              :aria-label="sidebarOpen ? '收起側欄' : '展開側欄'">
        <span :class="{ flip: !sidebarOpen }">◀</span>
      </button>

      <div v-if="error" class="content">
        <div class="card err">分析失敗：{{ error }}</div>
      </div>

      <div v-else-if="loading" class="game-stage">
        <RunnerLoader :forcing="forcing" :done="gameDone" @finished="onGameFinished" />
      </div>

      <div v-else-if="result" class="content">
        <ResultPanel :result="result" @back="backToMap" />
      </div>

      <!-- 預設畫面：滿版 OSM 選點地圖 -->
      <div v-else class="map-stage">
        <MapPicker ref="mapRef" :lat="form.lat" :lng="form.lng" :size-m="form.sizeM"
                   @pick="onPick" />
        <div class="map-hint">點地圖任一處設定中心點，再從左側「開始分析」</div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.app {
  display: grid;
  grid-template-columns: 340px 1fr;
  height: 100%;
  transition: grid-template-columns .32s cubic-bezier(.4, 0, .2, 1);
}
.app.collapsed { grid-template-columns: 0px 1fr; }

aside {
  border-right: 1px solid var(--line);
  background: var(--bg-sunken);
  padding: 24px 20px;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex; flex-direction: column; gap: 16px;
  min-width: 0;
  transition: padding .32s cubic-bezier(.4, 0, .2, 1), opacity .2s ease;
}
.collapsed aside {
  padding-left: 0; padding-right: 0;
  border-right: none;
  opacity: 0;
}
aside > * { min-width: 280px; }   /* 收合時內容不跟著壓扁，直接被裁掉 */

aside header h1 {
  margin: 0 0 8px; font-size: 22px; font-weight: 800;
  color: var(--green-900); letter-spacing: -.01em;
}
.lede { margin: 0; font-size: 13px; color: var(--text-2); }

main { position: relative; overflow: hidden; min-width: 0; }

/* 一般內容（結果／錯誤）自己捲動 */
.content { height: 100%; overflow-y: auto; padding: 32px 36px 64px; }

/* ── 側欄開合箭頭 ─────────────────────────────── */
.edge-toggle {
  position: absolute;
  left: 0; top: 50%;
  transform: translateY(-50%);
  z-index: 1100;                    /* 蓋過 Leaflet 圖層 */
  width: 24px; height: 64px;
  padding: 0;
  border-radius: 0 12px 12px 0;
  border: 1px solid var(--line);
  border-left: none;
  background: var(--surface);
  color: var(--text-2);
  font-size: 11px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 2px 0 10px rgba(30, 58, 43, .08);
}
.edge-toggle:hover { color: var(--green-700); }
.edge-toggle span { transition: transform .3s ease; display: inline-block; }
.edge-toggle span.flip { transform: rotate(180deg); }

/* ── 滿版地圖 ────────────────────────────────── */
.map-stage { position: absolute; inset: 0; }
.map-stage > :deep(.map) {
  height: 100%; min-height: 0;
  border: none; border-radius: 0;
}
.map-hint {
  position: absolute;
  left: 50%; bottom: 22px;
  transform: translateX(-50%);
  z-index: 1000;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 8px 18px;
  font-size: 13px;
  color: var(--text-2);
  box-shadow: 0 4px 18px rgba(30, 58, 43, .12);
  white-space: nowrap;
  pointer-events: none;
}

/* ── Loading：滿版小遊戲 ──────────────────────── */
.game-stage { position: absolute; inset: 0; }

label { display: block; font-size: 12.5px; color: var(--text-2); margin: 14px 0 7px; }
label:first-child { margin-top: 0; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.range { padding: 0; accent-color: var(--green-700); }
.full { width: 100%; margin-top: 16px; }
.rerun { margin-top: 8px; font-size: 12.5px; }

.presets { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 14px; }
.presets button { font-size: 12px; padding: 5px 11px; border-radius: 999px; }

.status ul { list-style: none; padding: 0; margin: 0; font-size: 13px; }
.status li { color: var(--text-2); }
.status li::before {
  content: '✕'; display: inline-block; width: 18px; color: #a8412c; font-weight: 700;
}
.status li.ok::before { content: '✓'; color: var(--green-600); }

.err { border-left: 3px solid #a8412c; color: #8c3826; }

.placeholder { color: var(--text-2); }

@media (max-width: 900px) {
  .app { grid-template-columns: 1fr; height: auto; display: block; }
  aside { border-right: none; border-bottom: 1px solid var(--line); }
  .collapsed aside { display: none; }
  main { height: 70vh; }
  .content { padding: 24px 18px 48px; }
  .edge-toggle { top: 16px; transform: none; }
}
</style>
