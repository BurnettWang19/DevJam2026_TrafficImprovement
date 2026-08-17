<script setup>
import { onMounted, reactive, ref } from 'vue'
import MapPicker from './components/MapPicker.vue'
import ResultPanel from './components/ResultPanel.vue'
import SplashScreen from './components/SplashScreen.vue'
import RunnerLoader from './components/RunnerLoader.vue'
import { apiGet, apiPost } from './api'

const booting = ref(true)
const panelOpen = ref(true)      // 右上角控制盒開合

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
  panelOpen.value = true
}
</script>

<template>
  <SplashScreen v-if="booting" @done="booting = false" />

  <template v-else>
    <!-- ── 結果報告：獨立頁面，不顯示任何選單 ─────────── -->
    <main v-if="result" class="page">
      <ResultPanel :result="result" @back="backToMap" />
    </main>

    <!-- ── 分析中：滿版小遊戲 ─────────────────────────── -->
    <main v-else-if="loading" class="stagefull">
      <RunnerLoader :forcing="forcing" :done="gameDone" @finished="onGameFinished" />
    </main>

    <!-- ── 預設：滿版地圖 + 右上角可收合控制盒 ────────── -->
    <main v-else class="stagefull">
      <div class="map-stage">
        <MapPicker ref="mapRef" :lat="form.lat" :lng="form.lng" :size-m="form.sizeM"
                   @pick="onPick" />
      </div>
      <div class="map-hint">點地圖任一處設定中心點</div>

      <div v-if="error" class="errbar">分析失敗：{{ error }}</div>

      <div class="panel" :class="{ closed: !panelOpen }">
        <button class="panel-head" @click="panelOpen = !panelOpen"
                :aria-expanded="panelOpen">
          <span class="brand">
            <b>路口設計品質分析</b>
            <small>Road Design Review</small>
          </span>
          <span class="chev" :class="{ flip: !panelOpen }">▾</span>
        </button>

        <Transition name="fold">
          <div class="panel-body" v-show="panelOpen">
            <label>中心點座標</label>
            <div class="grid2">
              <input v-model="latText" placeholder="緯度" @change="applyText" />
              <input v-model="lngText" placeholder="經度" @change="applyText" />
            </div>

            <label>範圍邊長 <b class="mono">{{ form.sizeM }} m</b></label>
            <input type="range" min="40" max="400" step="10"
                   v-model.number="form.sizeM" class="range" />

            <button class="primary full" :disabled="loading" @click="analyze(false)">
              開始分析
            </button>
            <button class="full rerun" :disabled="loading" @click="analyze(true)"
                    title="忽略快取，實際重新呼叫所有代理人（約 2 分鐘）">
              ↻ 重新分析（跳過快取）
            </button>

            <div class="presets">
              <button v-for="p in PRESETS" :key="p.name" @click="usePreset(p)">
                {{ p.name }}
              </button>
            </div>

            <ul class="status" v-if="health">
              <li :class="health.gemini_api_key ? 'ok' : 'no'">Gemini 金鑰</li>
              <li :class="health.imagery_ready ? 'ok' : 'no'">
                衛星影像 · {{ health.imagery_provider }}
              </li>
              <li :class="health.scorer_prompt_filled ? 'ok' : 'no'">評分標準</li>
              <li :class="health.classic_cases ? 'ok' : 'no'">
                經典案例 {{ health.classic_cases }} 筆
              </li>
              <li :class="health.cache_entries ? 'ok' : 'no'">
                預熱快取 {{ health.cache_entries }} 筆
              </li>
            </ul>
          </div>
        </Transition>
      </div>
    </main>
  </template>
</template>

<style scoped>
/* ── 三種全螢幕狀態 ───────────────────────────── */
.stagefull { position: fixed; inset: 0; overflow: hidden; }
.page { position: fixed; inset: 0; overflow-y: auto; padding: 32px 36px 64px; }

.map-stage { position: absolute; inset: 0; }
.map-stage > :deep(.map) {
  height: 100%; min-height: 0;
  border: none; border-radius: 0;
}
.map-hint {
  position: absolute; left: 50%; bottom: 22px;
  transform: translateX(-50%);
  z-index: 1000;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 8px 18px;
  font-size: 13px; color: var(--text-2);
  box-shadow: 0 4px 18px rgba(30, 58, 43, .12);
  white-space: nowrap;
  pointer-events: none;
}

.errbar {
  position: absolute; left: 50%; top: 18px;
  transform: translateX(-50%);
  z-index: 1300;
  max-width: min(560px, calc(100vw - 32px));
  background: var(--surface);
  border: 1px solid var(--line-soft);
  border-left: 3px solid #a8412c;
  border-radius: 12px;
  padding: 12px 18px;
  color: #8c3826; font-size: 13.5px;
  box-shadow: 0 8px 26px rgba(30, 58, 43, .16);
}

/* ── 右上角控制盒 ─────────────────────────────── */
.panel {
  position: absolute; top: 16px; right: 16px;
  z-index: 1200;
  width: min(320px, calc(100vw - 32px));
  background: var(--surface);
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  box-shadow: 0 10px 34px rgba(30, 58, 43, .16);
  overflow: hidden;
  transition: width .25s ease;
}
.panel.closed { width: 232px; }

.panel-head {
  width: 100%;
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px;
  padding: 13px 16px;
  border: none; border-radius: 0;
  background: none;
  text-align: left;
}
.panel-head:hover { background: #fbfaf7; }
.brand b {
  display: block; font-size: 15px; font-weight: 800;
  color: var(--green-900); line-height: 1.25;
}
.brand small {
  font-size: 10.5px; letter-spacing: .14em; text-transform: uppercase;
  color: var(--muted); font-weight: 600;
}
.chev {
  flex: none; color: var(--text-2); font-size: 13px;
  transition: transform .3s ease;
}
.chev.flip { transform: rotate(-180deg); }

.panel-body {
  padding: 4px 16px 16px;
  border-top: 1px solid var(--line-soft);
  max-height: calc(100vh - 120px);
  overflow-y: auto;
}

/* 收合動畫 */
.fold-enter-active, .fold-leave-active {
  transition: opacity .22s ease, transform .28s cubic-bezier(.22, .9, .3, 1);
  transform-origin: top;
}
.fold-enter-from, .fold-leave-to { opacity: 0; transform: translateY(-8px) scaleY(.96); }

label { display: block; font-size: 12.5px; color: var(--text-2); margin: 13px 0 6px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.grid2 input { font-size: 13.5px; padding: 8px 10px; }
.range { padding: 0; accent-color: var(--green-700); }
.full { width: 100%; margin-top: 14px; }
.rerun { margin-top: 8px; font-size: 12.5px; }

.presets { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 13px; }
.presets button { font-size: 12px; padding: 5px 11px; border-radius: 999px; }

.status {
  list-style: none; padding: 12px 0 0; margin: 14px 0 0;
  border-top: 1px solid var(--line-soft);
  font-size: 12.5px;
}
.status li { color: var(--text-2); }
.status li::before {
  content: '✕'; display: inline-block; width: 18px; color: #a8412c; font-weight: 700;
}
.status li.ok::before { content: '✓'; color: var(--green-600); }

@media (max-width: 900px) {
  .page { padding: 24px 18px 48px; }
  .panel { top: 12px; right: 12px; }
}
</style>
