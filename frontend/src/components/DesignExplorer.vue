<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

/* 互動式設計圖：
   - 圖上放編號標記（來自重繪 Agent 的 annotations）
   - 點標記 → 平滑放大到該處，旁邊滑出說明卡：
       原本的問題（findings）→ 做了什麼改動（key_changes）→ 為什麼（rationale）
   - 再點一次、按 ✕、按 Esc 或點空白處 → 縮回全圖 */

const props = defineProps({
  image: { type: String, required: true },
  annotations: { type: Array, default: () => [] },
  keyChanges: { type: Array, default: () => [] },
  findings: { type: Object, default: () => ({}) },
})

const ZOOM = 2.2
const active = ref(null)

/* findings 是 {類別: {issues: [...]}}，攤平成 id → issue */
const issueById = computed(() => {
  const map = {}
  for (const cat of Object.values(props.findings || {})) {
    for (const iss of cat.issues || []) if (iss.id) map[iss.id] = iss
  }
  return map
})

/* 每個標記對應的完整說明 */
const details = computed(() => props.annotations.map((a, i) => {
  const ids = a.addresses || []
  const issues = ids.map((id) => issueById.value[id]).filter(Boolean)
  const changes = (props.keyChanges || []).filter(
    (kc) => (kc.addresses || []).some((x) => ids.includes(x)))
  const whys = changes.map((c) => c.rationale).filter(Boolean)
  if (!whys.length) whys.push(...issues.map((x) => x.solution).filter(Boolean))
  return { ...a, n: i + 1, issues, changes, whys }
}))

const current = computed(() =>
  active.value == null ? null : details.value[active.value])

/* 縮放：以標記點為 transform-origin 放大，再平移使該點靠近畫面中心。
   平移量夾住，讓圖的邊緣不會被拉進畫面裡。 */
const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi)

const canvasStyle = computed(() => {
  if (active.value == null) {
    return { transformOrigin: '50% 50%', transform: 'translate(0, 0) scale(1)' }
  }
  const [nx, ny] = details.value[active.value].point
  const tx = clamp(0.5 - nx, (ZOOM - 1) * (nx - 1), (ZOOM - 1) * nx) * 100
  const ty = clamp(0.5 - ny, (ZOOM - 1) * (ny - 1), (ZOOM - 1) * ny) * 100
  return {
    transformOrigin: `${nx * 100}% ${ny * 100}%`,
    transform: `translate(${tx}%, ${ty}%) scale(${ZOOM})`,
  }
})

/* 放大時標記反向縮小，維持固定視覺大小 */
function markerStyle(d) {
  const zoomed = active.value != null
  const isActive = active.value === d.n - 1
  const s = zoomed ? (isActive ? 1.2 : 1) / ZOOM : 1
  return {
    left: d.point[0] * 100 + '%',
    top: d.point[1] * 100 + '%',
    transform: `translate(-50%, -50%) scale(${s})`,
  }
}

function select(i) {
  active.value = active.value === i ? null : i
}
function reset() { active.value = null }

function onKey(e) { if (e.key === 'Escape') reset() }
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))

const SEV = {
  high: '高度', critical: '極高', medium: '中度', low: '低度', uncertain: '待確認',
}
const sevLabel = (s) => SEV[String(s || '').toLowerCase()] || ''
</script>

<template>
  <div class="explorer">
    <div class="viewport" @click="reset">
      <div class="canvas" :style="canvasStyle">
        <img :src="image" alt="改善後設計圖" draggable="false" />
        <button v-for="d in details" :key="d.n" class="marker"
                :class="{ active: active === d.n - 1,
                          dim: active !== null && active !== d.n - 1 }"
                :style="markerStyle(d)"
                :title="d.label"
                @click.stop="select(d.n - 1)">
          <span class="ripple"></span>
          <b>{{ d.n }}</b>
        </button>
      </div>

      <!-- 說明卡 -->
      <Transition name="pop">
        <aside v-if="current" class="detail" @click.stop>
          <button class="close" @click="reset" aria-label="關閉">✕</button>
          <h4><span class="num">{{ current.n }}</span>{{ current.label }}</h4>

          <div class="block" v-if="current.issues.length">
            <span class="k prob">原本的問題</span>
            <p v-for="iss in current.issues" :key="iss.id">
              <b>{{ iss.title }}</b>
              <i v-if="sevLabel(iss.severity)" class="sev">{{ sevLabel(iss.severity) }}</i>
              <em v-if="iss.evidence">{{ iss.evidence }}</em>
            </p>
          </div>

          <div class="block" v-if="current.changes.length">
            <span class="k chg">做了什麼改動</span>
            <p v-for="(c, i) in current.changes" :key="i"><b>{{ c.change }}</b></p>
          </div>

          <div class="block" v-if="current.whys.length">
            <span class="k why">為什麼這樣改</span>
            <p v-for="(w, i) in current.whys" :key="i">{{ w }}</p>
          </div>

          <p v-if="!current.issues.length && !current.changes.length && !current.whys.length"
             class="empty">此標記沒有對應到詳細的問題資料。</p>
        </aside>
      </Transition>

      <button v-if="active !== null" class="resetview" @click.stop="reset">↺ 看全圖</button>
    </div>

    <p class="hint">點擊圖上的編號標記，放大檢視該處的改動與原因；點空白處或按 Esc 縮回全圖</p>
  </div>
</template>

<style scoped>
.explorer { width: 100%; max-width: 620px; margin: 0 auto; }

.viewport {
  position: relative;
  overflow: hidden;
  border-radius: 14px;
  border: 1px solid var(--line-soft);
  cursor: zoom-out;
  background: var(--bg-sunken);
}

.canvas {
  position: relative;
  transition: transform .6s cubic-bezier(.22, .9, .3, 1);
  will-change: transform;
}
.canvas img { width: 100%; display: block; user-select: none; }

/* ── 編號標記 ─────────────────────────────────── */
.marker {
  position: absolute;
  width: 34px; height: 34px;
  padding: 0; border: none; border-radius: 50%;
  background: var(--green-900); color: #f3f6f2;
  font-weight: 800; font-size: 15px;
  display: grid; place-content: center;
  cursor: zoom-in;
  box-shadow: 0 3px 12px rgba(30, 58, 43, .35), 0 0 0 3px rgba(255, 255, 255, .85);
  transition: transform .6s cubic-bezier(.22, .9, .3, 1),
              opacity .3s ease, background .2s ease;
  z-index: 5;
}
.marker:hover { background: var(--green-700); }
.marker.active { background: #d97b29; cursor: zoom-out; z-index: 6; }
.marker.dim { opacity: .35; }
.marker b { position: relative; z-index: 2; font-weight: 800; }

/* 呼吸光圈：提示可以點 */
.ripple {
  position: absolute; inset: 0; border-radius: 50%;
  border: 2px solid var(--green-700);
  animation: ripple 2s ease-out infinite;
  pointer-events: none;
}
.marker.active .ripple { border-color: #d97b29; }
.marker.dim .ripple { animation: none; opacity: 0; }
@keyframes ripple {
  0%   { transform: scale(1); opacity: .8; }
  70%  { transform: scale(1.9); opacity: 0; }
  100% { transform: scale(1.9); opacity: 0; }
}

/* ── 說明卡 ───────────────────────────────────── */
.detail {
  position: absolute; right: 14px; bottom: 14px;
  width: min(320px, calc(100% - 28px));
  max-height: calc(100% - 32px);
  overflow-y: auto;
  background: var(--surface);
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  padding: 20px 22px 18px;
  box-shadow: 0 14px 40px rgba(30, 58, 43, .22);
  cursor: auto;
  z-index: 10;
}
.detail h4 {
  margin: 0 0 14px; padding-right: 28px;
  font-size: 18px; font-weight: 800; color: var(--green-900);
  display: flex; align-items: center; gap: 10px;
}
.num {
  flex: none;
  width: 26px; height: 26px; border-radius: 50%;
  background: #d97b29; color: #fff;
  font-size: 14px; font-weight: 800;
  display: grid; place-content: center;
}
.close {
  position: absolute; top: 12px; right: 12px;
  width: 28px; height: 28px; padding: 0;
  border: none; border-radius: 8px;
  background: none; color: var(--muted); font-size: 14px;
}
.close:hover { background: var(--bg-sunken); color: var(--text); }

.block { margin-bottom: 14px; }
.block:last-child { margin-bottom: 0; }
.k {
  display: block;
  font-size: 11px; letter-spacing: .12em; text-transform: uppercase;
  font-weight: 700; margin-bottom: 6px;
}
.k.prob { color: var(--sev-high-fg); }
.k.chg { color: var(--green-700); }
.k.why { color: var(--muted); }

.block p { margin: 0 0 8px; font-size: 13.5px; line-height: 1.6; color: var(--text-2); }
.block p:last-child { margin-bottom: 0; }
.block p b { color: var(--text); font-weight: 700; }
.block p em { display: block; font-style: normal; font-size: 12.5px; color: var(--muted); }
.sev {
  font-style: normal; font-size: 11.5px; font-weight: 600;
  background: var(--sev-high-bg); color: var(--sev-high-fg);
  border-radius: 999px; padding: 1px 9px; margin-left: 7px;
  vertical-align: 1px;
}
.empty { margin: 0; font-size: 13px; color: var(--muted); }

/* 卡片進出場動畫 */
.pop-enter-active { transition: opacity .35s ease, transform .45s cubic-bezier(.22, .9, .3, 1); }
.pop-leave-active { transition: opacity .2s ease, transform .25s ease; }
.pop-enter-from, .pop-leave-to { opacity: 0; transform: translateY(16px) scale(.96); }

/* ── 重設按鈕與提示 ───────────────────────────── */
.resetview {
  position: absolute; left: 16px; bottom: 16px; z-index: 10;
  font-size: 13px; padding: 7px 16px; border-radius: 999px;
  box-shadow: 0 4px 14px rgba(30, 58, 43, .18);
}
.hint { margin: 10px 0 0; font-size: 12.5px; color: var(--muted); text-align: center; }

@media (prefers-reduced-motion: reduce) {
  .canvas, .marker { transition: none; }
  .ripple { animation: none; }
}
</style>
