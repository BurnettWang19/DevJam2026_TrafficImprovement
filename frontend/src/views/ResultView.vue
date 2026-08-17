<template>
  <main class="result-page">
    <header class="result-header">
      <RouterLink class="back-link" to="/">← 重新選擇路口</RouterLink>
      <div>
        <div class="result-title-meta">
          <p class="result-eyebrow">ROAD DESIGN REVIEW</p>
          <span v-if="isDemo" class="demo-badge">示範資料</span>
        </div>
        <h1>路口改善建議</h1>
        <p v-if="result">{{ statusMessage }}</p>
      </div>
      <div v-if="result?.overallScore != null" class="score-orb">
        <strong>{{ result.overallScore }}</strong>
        <span>設計評分</span>
      </div>
    </header>

    <section v-if="!result" class="empty-result">
      <h2>還沒有分析結果</h2>
      <p>請先回到地圖選擇路口並開始分析。</p>
      <RouterLink to="/">回到地圖</RouterLink>
    </section>

    <template v-else>
      <section class="analysis-facts" aria-label="分析摘要">
        <div>
          <span>分析位置</span>
          <strong>{{ result.location.latitude.toFixed(4) }}, {{ result.location.longitude.toFixed(4) }}</strong>
        </div>
        <div>
          <span>路口型態</span>
          <strong>{{ intersectionTypeLabel(result.intersectionType) }}</strong>
        </div>
        <div>
          <span>證據涵蓋</span>
          <strong>{{ evidenceCoverage }}</strong>
        </div>
        <div>
          <span>資料來源</span>
          <strong>{{ dataSources }}</strong>
        </div>
      </section>

      <section v-if="result.status === 'NOT_INTERSECTION'" class="result-state-card">
        <span>非路口範圍</span>
        <h2>這個範圍看起來不是道路交會處</h2>
        <p>{{ result.problemSummary }}</p>
      </section>

      <section v-else-if="result.status === 'NO_PROBLEM'" class="result-state-card is-good">
        <span>沒有重大問題</span>
        <h2>這個路口目前的規劃大致完善</h2>
        <p>{{ result.problemSummary }}</p>
      </section>

      <template v-else>
        <section class="comparison-stage">
          <article>
            <div class="image-heading"><span>改善前</span><small>衛星影像與現況向量</small></div>
            <img v-if="result.sourceImage" :src="result.sourceImage.dataUrl" alt="改善前路口衛星影像" />
            <div v-else class="image-placeholder">目前沒有可顯示的現況影像</div>
          </article>
          <article class="recommended-image">
            <div class="image-heading"><span>建議方案</span><small>AI 概念示意圖</small></div>
            <img v-if="result.renderedImage" :src="result.renderedImage.dataUrl" alt="改善後道路設計概念圖" />
            <div v-else class="image-placeholder">本次分析未產生改善示意圖</div>
          </article>
        </section>

        <section class="result-summary">
          <div>
            <p class="result-eyebrow">WHY IT MATTERS</p>
            <h2>我們發現的問題</h2>
            <p>{{ result.problemSummary }}</p>
          </div>
          <div class="improvement-copy">
            <p class="result-eyebrow">PROPOSED DESIGN</p>
            <h2>新版設計如何改善</h2>
            <p>{{ result.improvementSummary }}</p>
          </div>
        </section>

        <section class="findings-grid">
          <article v-for="finding in result.findings" :key="`${finding.category}-${finding.title}`">
            <div class="finding-meta">
              <span>{{ categoryLabel(finding.category) }}</span>
              <small :data-severity="finding.severity">{{ severityLabel(finding.severity) }}</small>
            </div>
            <h3>{{ finding.title }}</h3>
            <p>{{ finding.description }}</p>
            <strong>{{ finding.recommendation }}</strong>
          </article>
        </section>

        <section v-if="result.matchedCases.length" class="case-section">
          <div class="case-heading">
            <div>
              <p class="result-eyebrow">REFERENCE CASES</p>
              <h2>相似的經典案例</h2>
            </div>
            <p>依路口型態與問題標籤匹配，提供設計脈絡而非直接套用。</p>
          </div>
          <div class="case-grid">
            <a
              v-for="caseItem in result.matchedCases"
              :key="caseItem.id"
              :href="caseItem.sourceUrl"
              target="_blank"
              rel="noreferrer"
            >
              <span>{{ caseItem.location }}</span>
              <h3>{{ caseItem.title }}</h3>
              <p>{{ caseItem.summary }}</p>
              <small>{{ caseItem.matchReason }}</small>
            </a>
          </div>
        </section>

        <p class="concept-note">此結果為 AI 輔助的概念設計，實際工程仍需交通工程師現勘、模擬與法規審查。</p>
      </template>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { useIntersectionStore } from '../stores/intersection'

const store = useIntersectionStore()
const result = computed(() => store.analysisResult)
const isDemo = computed(() => result.value?.metadata.demo === true)
const evidenceCoverage = computed(() => String(result.value?.metadata.evidenceCoverage ?? '依現有資料'))
const dataSources = computed(() => {
  const sources = result.value?.metadata.dataSources
  return Array.isArray(sources) ? sources.join('・') : 'OSM・影像辨識'
})

const statusMessage = computed(() => {
  if (result.value?.status === 'NO_PROBLEM') return '分析完成，未發現需要立即改善的重大問題。'
  if (result.value?.status === 'NOT_INTERSECTION') return '分析已停止，請重新選擇實際的道路交會點。'
  return '分析完成，以下是依現況問題提出的概念改善方向。'
})

function categoryLabel(category: string) {
  return { crosswalk: '斑馬線', sidewalk: '人行道', lane_marking: '車道標線', overall: '整體' }[category] ?? category
}

function severityLabel(severity: string) {
  return { LOW: '低度', MEDIUM: '中度', HIGH: '高度', CRITICAL: '嚴重' }[severity] ?? severity
}

function intersectionTypeLabel(type?: string | null) {
  return {
    ORTHOGONAL: '正交路口',
    T_JUNCTION: 'T 字路口',
    SKEWED: '偏斜路口',
    ROUNDABOUT: '圓環',
    MULTI_LEG: '多岔路口',
    OTHER_INTERSECTION: '其他路口'
  }[type ?? ''] ?? '未分類'
}
</script>
