<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

/* 分析中的模擬進度條：後端不回報進度，用漸近曲線模擬——
   前段快速推進、越接近尾聲越慢，最多停在 97% 等實際結果回來。 */
const props = defineProps({
  forcing: { type: Boolean, default: false },
})

const progress = ref(0)
const label = ref('準備分析…')

/* 對應後端 pipeline 的階段 */
const STAGES = [
  { at: 0, text: '擷取 OSM 向量與衛星影像…' },
  { at: 16, text: '影像辨識補上車道標線…' },
  { at: 32, text: '依評分標準檢核設計…' },
  { at: 46, text: '判斷路口型態…' },
  { at: 58, text: '三個代理人平行診斷中…' },
  { at: 72, text: '重繪改善設計…' },
  { at: 84, text: '生成設計圖面…' },
  { at: 93, text: '彙整報告與經典案例…' },
]

let raf = 0

onMounted(() => {
  // 強制重跑約 2 分鐘、一般分析較快 → 用不同時間常數
  const TAU = props.forcing ? 42_000 : 16_000
  const start = performance.now()
  const tick = (now) => {
    const t = now - start
    progress.value = Math.min(Math.round(97 * (1 - Math.exp(-t / TAU))), 97)
    for (const s of STAGES) if (progress.value >= s.at) label.value = s.text
    raf = requestAnimationFrame(tick)
  }
  raf = requestAnimationFrame(tick)
})

onUnmounted(() => cancelAnimationFrame(raf))
</script>

<template>
  <div class="progress">
    <div class="bar" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100">
      <div class="fill" :style="{ width: progress + '%' }"></div>
    </div>
    <p class="state">
      <span>{{ label }}</span>
      <b class="mono">{{ progress }}%</b>
    </p>
  </div>
</template>

<style scoped>
/* 和開場 Splash 同一套視覺 */
.progress { width: min(400px, 100%); margin: 2px 0 16px; }

.bar {
  width: 100%; height: 6px; border-radius: 999px;
  background: var(--line); overflow: hidden;
}
.fill {
  height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, var(--green-700), var(--green-600));
  transition: width .2s linear;
}
.state {
  display: flex; justify-content: space-between; align-items: baseline;
  margin: 10px 0 0; font-size: 13px; color: var(--text-2);
}
.state b { color: var(--green-700); font-weight: 600; }
</style>
