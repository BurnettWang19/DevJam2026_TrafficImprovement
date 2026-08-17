<template>
  <main class="selection-page">
    <header class="brand-header">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">
          <span class="brand-road brand-road-a" />
          <span class="brand-road brand-road-b" />
          <span class="brand-center" />
        </div>
        <div>
          <h1>路口改善分析</h1>
          <p>從熟悉的路口開始，一起找出更安全的設計</p>
        </div>
      </div>
      <button class="demo-entry" type="button" :disabled="store.loading" @click="openDemo">
        <span>DEMO</span>
        查看完整範例結果 →
      </button>
    </header>

    <section class="selection-card">
      <div class="map-stage">
        <IntersectionMap />
        <div class="map-instruction" role="status">
          <span class="instruction-pin" aria-hidden="true">●</span>
          <div>
            <strong>{{ store.selectedLocation ? '已選擇路口中心點' : '在地圖上點一下想改善的路口' }}</strong>
            <span>{{ store.selectedLocation ? '可再次點擊地圖重新選擇' : '別擔心，之後還能重新選擇' }}</span>
          </div>
        </div>
      </div>

      <aside class="steps-panel" aria-label="使用步驟">
        <div class="steps-heading">
          <div>
            <p>HOW IT WORKS</p>
            <h2>使用步驟</h2>
          </div>
          <div class="steps-landscape" aria-hidden="true">
            <span /><span /><span />
          </div>
        </div>

        <ol class="step-list">
          <li
            v-for="(step, index) in steps"
            :key="step"
            class="step-item"
            :class="stepClass(index)"
          >
            <span class="step-number">
              <svg v-if="isCompleted(index)" viewBox="0 0 20 20" aria-hidden="true">
                <path d="m4.5 10.5 3.2 3.2 7.8-8" />
              </svg>
              <template v-else>{{ index + 1 }}</template>
            </span>
            <span class="step-copy">
              <small v-if="isActive(index)">目前步驟</small>
              <strong>{{ index + 1 }}. {{ step }}</strong>
            </span>
          </li>
        </ol>
      </aside>

      <footer class="selection-controls">
        <section class="location-summary">
          <span class="control-icon control-icon-location" aria-hidden="true">⌖</span>
          <div>
            <div class="control-label-row">
              <span class="control-label">你選擇的路口</span>
              <button
                v-if="store.selectedLocation"
                class="text-button"
                type="button"
                @click="clearSelection"
              >
                重新選擇
              </button>
            </div>
            <strong class="coordinates">{{ coordinates }}</strong>
            <span class="location-hint">{{ store.selectedLocation ? '目前選取位置' : '尚未選擇座標' }}</span>
          </div>
        </section>

        <section class="range-control">
          <div class="range-copy">
            <span class="control-label">分析範圍</span>
            <span>拖動圓點調整</span>
          </div>
          <input
            v-model.number="store.radiusMeters"
            aria-label="分析範圍"
            type="range"
            min="25"
            max="500"
            step="25"
            :style="rangeStyle"
            @input="markRadiusAdjusted"
          />
          <div class="range-ticks" aria-hidden="true">
            <span>25 公尺</span>
            <span>100 公尺</span>
            <span>250 公尺</span>
            <span>500 公尺</span>
          </div>
        </section>

        <section class="range-value">
          <strong>{{ store.radiusMeters }}</strong>
          <span>公尺</span>
          <small>約步行 {{ walkingTime }} 分鐘</small>
        </section>

        <button
          class="confirm-button"
          type="button"
          :disabled="!store.selectedLocation || store.loading"
          @click="confirmSelection"
        >
          <span class="button-pin" aria-hidden="true">●</span>
          <span>{{ store.loading ? '正在分析路口…' : '確認，開始分析' }}</span>
        </button>
      </footer>
    </section>

    <p v-if="store.error" class="analysis-message analysis-error" role="alert">
      分析失敗：{{ store.error }}
    </p>
    <p v-else-if="store.analysisStatus === 'loaded'" class="analysis-message analysis-success" role="status">
      路口資料已載入，接下來可以查看改善建議。
    </p>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import IntersectionMap from '../components/map/IntersectionMap.vue'
import { useIntersectionStore } from '../stores/intersection'

const store = useIntersectionStore()
const router = useRouter()
const radiusAdjusted = ref(false)

const steps = [
  '選一個想改善的路口',
  '調整要分析的範圍',
  '確認這次的選擇',
  '查看適合的改善建議'
]

const coordinates = computed(() => {
  if (!store.selectedLocation) {
    return '—, —'
  }

  return `${store.selectedLocation.latitude.toFixed(4)}, ${store.selectedLocation.longitude.toFixed(4)}`
})

const walkingTime = computed(() => Math.max(1, Math.ceil(store.radiusMeters / 75)))
const rangeStyle = computed(() => ({
  '--range-progress': `${((store.radiusMeters - 25) / 475) * 100}%`
}))

function markRadiusAdjusted() {
  radiusAdjusted.value = true
  if (store.selectedLocation && store.analysisStatus !== 'loading') {
    store.analysisStatus = 'selected'
  }
}

function isCompleted(index: number) {
  if (index === 0) return Boolean(store.selectedLocation)
  if (index === 1) return Boolean(store.selectedLocation && radiusAdjusted.value)
  if (index === 2) return store.analysisStatus === 'loaded'
  return false
}

function isActive(index: number) {
  if (!store.selectedLocation) return index === 0
  if (!radiusAdjusted.value) return index === 1
  if (store.analysisStatus === 'loaded') return index === 3
  return index === 2
}

function stepClass(index: number) {
  return {
    'is-completed': isCompleted(index),
    'is-active': isActive(index),
    'is-upcoming': !isCompleted(index) && !isActive(index)
  }
}

function clearSelection() {
  store.clearSelection()
  radiusAdjusted.value = false
}

async function confirmSelection() {
  radiusAdjusted.value = true
  await store.analyzeSelectedLocation()
  if (store.analysisStatus === 'loaded') {
    await router.push('/results')
  }
}

async function openDemo() {
  store.loadDemoAnalysis()
  await router.push('/results')
}
</script>
