<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

const emit = defineEmits(['done'])

/* 模擬載入：非線性推進，約 2.2 秒跑滿，淡出後總長 < 3 秒 */
const progress = ref(0)
const label = ref('初始化介面…')
const leaving = ref(false)

const STEPS = [
  { at: 0, text: '初始化介面…' },
  { at: 30, text: '載入地圖資源…' },
  { at: 62, text: '連線分析服務…' },
  { at: 88, text: '準備完成' },
]

let raf = 0
let timer = 0

onMounted(() => {
  const DURATION = 2200
  const start = performance.now()
  const tick = (now) => {
    const t = Math.min((now - start) / DURATION, 1)
    // easeOutCubic：前快後慢，比較像真的在載入
    const eased = 1 - Math.pow(1 - t, 3)
    progress.value = Math.round(eased * 100)
    for (const s of STEPS) if (progress.value >= s.at) label.value = s.text
    if (t < 1) {
      raf = requestAnimationFrame(tick)
    } else {
      leaving.value = true
      timer = setTimeout(() => emit('done'), 450) // 等淡出動畫跑完
    }
  }
  raf = requestAnimationFrame(tick)
})

onUnmounted(() => {
  cancelAnimationFrame(raf)
  clearTimeout(timer)
})
</script>

<template>
  <div class="splash" :class="{ leaving }">
    <div class="inner">
      <!-- Logo：路口＋斑馬線意象 -->
      <svg class="logo" viewBox="0 0 120 120" aria-label="Road Design Review logo">
        <rect x="4" y="4" width="112" height="112" rx="28" fill="#1e3a2b" />
        <!-- 十字路口 -->
        <rect x="44" y="4" width="32" height="112" fill="#f4f3ee" opacity=".14" />
        <rect x="4" y="44" width="112" height="32" fill="#f4f3ee" opacity=".14" />
        <!-- 車道中線 -->
        <line x1="60" y1="10" x2="60" y2="38" stroke="#f4f3ee" stroke-width="3" stroke-dasharray="7 6" opacity=".8" />
        <line x1="60" y1="82" x2="60" y2="110" stroke="#f4f3ee" stroke-width="3" stroke-dasharray="7 6" opacity=".8" />
        <line x1="10" y1="60" x2="38" y2="60" stroke="#f4f3ee" stroke-width="3" stroke-dasharray="7 6" opacity=".8" />
        <line x1="82" y1="60" x2="110" y2="60" stroke="#f4f3ee" stroke-width="3" stroke-dasharray="7 6" opacity=".8" />
        <!-- 斑馬線（上、下） -->
        <g fill="#f4f3ee">
          <rect x="46" y="30" width="4.6" height="10" rx="1.4" />
          <rect x="53.5" y="30" width="4.6" height="10" rx="1.4" />
          <rect x="61" y="30" width="4.6" height="10" rx="1.4" />
          <rect x="68.5" y="30" width="4.6" height="10" rx="1.4" />
          <rect x="46" y="80" width="4.6" height="10" rx="1.4" />
          <rect x="53.5" y="80" width="4.6" height="10" rx="1.4" />
          <rect x="61" y="80" width="4.6" height="10" rx="1.4" />
          <rect x="68.5" y="80" width="4.6" height="10" rx="1.4" />
        </g>
        <!-- 斑馬線（左、右） -->
        <g fill="#f4f3ee">
          <rect x="30" y="46" width="10" height="4.6" rx="1.4" />
          <rect x="30" y="53.5" width="10" height="4.6" rx="1.4" />
          <rect x="30" y="61" width="10" height="4.6" rx="1.4" />
          <rect x="30" y="68.5" width="10" height="4.6" rx="1.4" />
          <rect x="80" y="46" width="10" height="4.6" rx="1.4" />
          <rect x="80" y="53.5" width="10" height="4.6" rx="1.4" />
          <rect x="80" y="61" width="10" height="4.6" rx="1.4" />
          <rect x="80" y="68.5" width="10" height="4.6" rx="1.4" />
        </g>
        <!-- 中心定位點 -->
        <circle cx="60" cy="60" r="7.5" fill="#7fae8f" />
        <circle cx="60" cy="60" r="3" fill="#1e3a2b" />
      </svg>

      <p class="eyebrow">Road Design Review</p>
      <h1>路口設計品質分析</h1>

      <div class="bar" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100">
        <div class="fill" :style="{ width: progress + '%' }"></div>
      </div>
      <p class="state">
        <span>{{ label }}</span>
        <b class="mono">{{ progress }}%</b>
      </p>
    </div>
  </div>
</template>

<style scoped>
.splash {
  position: fixed; inset: 0; z-index: 999;
  display: grid; place-items: center;
  background: var(--bg);
  transition: opacity .45s ease;
}
.splash.leaving { opacity: 0; pointer-events: none; }

.inner {
  display: flex; flex-direction: column; align-items: center;
  text-align: center; padding: 0 24px;
  animation: pop .7s cubic-bezier(.16, 1, .3, 1) both;
}
@keyframes pop {
  from { opacity: 0; transform: translateY(18px) scale(.96); }
  to { opacity: 1; transform: none; }
}

.logo {
  width: 128px; height: 128px; margin-bottom: 22px;
  filter: drop-shadow(0 10px 24px rgba(30, 58, 43, .22));
}

.inner .eyebrow { margin-bottom: 6px; }
h1 {
  margin: 0 0 30px; font-size: 27px; font-weight: 800;
  color: var(--green-900); letter-spacing: -.01em;
}

.bar {
  width: min(320px, 70vw); height: 6px; border-radius: 999px;
  background: var(--line); overflow: hidden;
}
.fill {
  height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, var(--green-700), var(--green-600));
  transition: width .12s linear;
}
.state {
  display: flex; justify-content: space-between; align-items: baseline;
  width: min(320px, 70vw);
  margin: 10px 0 0; font-size: 13px; color: var(--text-2);
}
.state b { color: var(--green-700); font-weight: 600; }

@media (prefers-reduced-motion: reduce) {
  .inner { animation: none; }
  .splash { transition: none; }
}
</style>
