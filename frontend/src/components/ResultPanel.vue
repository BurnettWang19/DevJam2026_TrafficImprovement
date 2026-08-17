<script setup>
import { computed } from 'vue'

const props = defineProps({ result: { type: Object, required: true } })

const r = computed(() => props.result)
const sev = { high: '重大', medium: '中等', low: '輕微', uncertain: '待確認' }

const allIssues = computed(() => {
  const out = []
  for (const cat of Object.values(r.value.findings || {})) {
    for (const i of cat.issues || []) out.push({ ...i, category: cat.category })
  }
  const order = { high: 0, medium: 1, low: 2, uncertain: 3 }
  return out.sort((a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9))
})
</script>

<template>
  <div class="wrap">
    <div class="cachebar" v-if="r.cached">
      ⚡ 這是 <b>{{ r.cached_at }}</b> 預先跑好的快取結果，未重新呼叫模型。
      左側「↻ 重新分析（跳過快取）」可當場實際跑一次。
    </div>

    <!-- ── 非路口 ───────────────────────────────── -->
    <div v-if="r.verdict === 'not_intersection'" class="card verdict bad">
      <h2>非路口</h2>
      <p>{{ r.message }}</p>
      <p class="muted" v-if="r.intersection_type">
        判定信心 {{ r.intersection_type.confidence }} — 判斷迴圈已中斷，未進行後續分析。
      </p>
      <img v-if="r.current_image" :src="r.current_image" alt="現況向量圖" />
    </div>

    <!-- ── 無重大問題 ───────────────────────────── -->
    <div v-else-if="r.verdict === 'no_problem'" class="card verdict good">
      <h2>No Problem — 此路口設計無重大問題</h2>
      <div class="scorebar">
        <div class="num">{{ r.score?.score ?? '—' }}<small>/100</small></div>
        <p>{{ r.message }}</p>
      </div>
      <ul class="criteria">
        <li v-for="(c, i) in r.score?.criteria || []" :key="i">
          <span>{{ c.name }}</span>
          <b class="mono">{{ c.score }}/{{ c.max }}</b>
          <em class="muted">{{ c.comment }}</em>
        </li>
      </ul>
      <img v-if="r.current_image" :src="r.current_image" alt="現況向量圖" />
    </div>

    <!-- ── 有問題，已產生改善設計 ───────────────── -->
    <template v-else>
      <div class="card verdict warn">
        <div class="topline">
          <h2>{{ r.report?.headline || '此路口有設計問題' }}</h2>
          <span class="tag">{{ r.intersection_type?.type }}</span>
        </div>
        <div class="scorebar">
          <div class="num">{{ r.score?.score ?? '—' }}<small>/100</small></div>
          <p>{{ r.score?.summary }}</p>
        </div>
        <ul class="criteria">
          <li v-for="(c, i) in r.score?.criteria || []" :key="i">
            <span><b class="mono cid">{{ c.criterion }}</b> {{ c.name }}</span>
            <b class="mono">{{ c.score == null ? '—' : c.score }}</b>
            <em :class="['st', (c.status || '').toLowerCase()]">{{ c.status }}</em>
            <em class="muted">{{ (c.issues || []).map(x => x.issue).join('；') || c.comment }}</em>
          </li>
        </ul>
      </div>

      <!-- 前後對照 -->
      <div class="card">
        <h3>設計前後對照</h3>
        <div class="compare">
          <figure>
            <img :src="r.current_image" alt="現況" />
            <figcaption>現況（OSM + 視覺辨識向量）</figcaption>
          </figure>
          <figure>
            <img :src="r.design_image" alt="改善設計" />
            <figcaption>{{ r.design?.name || '改善設計' }}</figcaption>
          </figure>
        </div>
        <p class="attrib muted" v-if="r.imagery">
          底圖：{{ r.imagery.attribution }} · zoom {{ r.imagery.zoom }} ·
          {{ r.imagery.meters_per_pixel }} m/px
        </p>
        <figure v-if="r.design_image_ai" class="ai">
          <img :src="r.design_image_ai" alt="AI 擬真圖" />
          <figcaption>AI 生成的擬真示意圖</figcaption>
        </figure>
        <p class="muted">{{ r.design?.summary }}</p>
      </div>

      <!-- 原有問題（讀自記憶體） -->
      <div class="card">
        <h3>這個路口原本的問題</h3>
        <p class="narrative">{{ r.report?.problem_narrative }}</p>
        <ul class="issues">
          <li v-for="it in allIssues" :key="it.id">
            <div class="ih">
              <span class="pill" :class="it.severity">{{ sev[it.severity] || it.severity }}</span>
              <span class="cat">{{ it.category }}</span>
              <strong>{{ it.title }}</strong>
            </div>
            <div class="loc muted">位置：{{ it.location }}</div>
            <div class="ev">{{ it.evidence }}</div>
            <div class="sol"><b>解方</b>{{ it.solution }}</div>
          </li>
        </ul>
      </div>

      <!-- 經典案例 -->
      <div class="card" v-if="r.classic_case">
        <h3>經典案例對照</h3>
        <div class="case">
          <img v-if="r.classic_case.image_data_url" :src="r.classic_case.image_data_url"
               :alt="r.classic_case.name" />
          <div>
            <h4>{{ r.classic_case.name }}
              <small class="muted">{{ r.classic_case.country }}</small></h4>
            <p>{{ r.classic_case.summary }}</p>
            <ul>
              <li v-for="(w, i) in r.classic_case.why_it_works || []" :key="i">{{ w }}</li>
            </ul>
          </div>
        </div>
        <p class="narrative" v-if="r.report?.case_narrative">{{ r.report.case_narrative }}</p>
      </div>
      <div class="card muted" v-else>
        經典案例資料夾中沒有符合「{{ r.intersection_type?.type }}」的案例，
        可在 <code class="mono">經典案例/index.json</code> 補上。
      </div>

      <!-- 改善說明 -->
      <div class="card">
        <h3>新設計如何改善</h3>
        <p class="narrative">{{ r.report?.improvement_narrative }}</p>
        <ol class="improve">
          <li v-for="(im, i) in r.report?.improvements || []" :key="i">
            <div class="row"><span class="k">問題</span>{{ im.problem }}</div>
            <div class="row"><span class="k on">改動</span>{{ im.change }}</div>
            <div class="row"><span class="k">效果</span>{{ im.effect }}</div>
          </li>
        </ol>
      </div>
    </template>
  </div>
</template>

<style scoped>
.wrap { display: flex; flex-direction: column; gap: 14px; }
.cachebar {
  background: #1e3a4d; border: 1px solid #2b5570; color: #bae6fd;
  border-radius: 10px; padding: 9px 14px; font-size: 12.5px;
}
h2 { margin: 0 0 8px; font-size: 18px; }
h3 { margin: 0 0 12px; font-size: 15px; }
h4 { margin: 0 0 6px; font-size: 14px; }
img { width: 100%; border-radius: 8px; display: block; border: 1px solid var(--line); }

.verdict { border-left: 3px solid var(--line); }
.verdict.good { border-left-color: var(--accent); }
.verdict.warn { border-left-color: var(--warn); }
.verdict.bad { border-left-color: var(--bad); }

.topline { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.tag {
  flex: none; font-size: 12px; padding: 2px 10px; border-radius: 999px;
  background: #1e3a4d; color: var(--accent-2); border: 1px solid #2b5570;
}

.scorebar { display: flex; gap: 16px; align-items: center; margin: 10px 0; }
.num { font-size: 34px; font-weight: 700; line-height: 1; }
.num small { font-size: 14px; color: var(--muted); font-weight: 400; }
.scorebar p { margin: 0; }

.criteria { list-style: none; padding: 0; margin: 12px 0 0; }
.criteria li {
  display: grid; grid-template-columns: 220px 44px 120px 1fr; gap: 10px;
  padding: 6px 0; border-top: 1px solid var(--line); font-size: 13px;
  align-items: baseline;
}
.criteria em { font-style: normal; }
.cid { color: var(--accent-2); margin-right: 6px; }
.st { font-size: 11px; letter-spacing: .3px; color: var(--muted); }
.st.good { color: var(--accent); }
.st.acceptable { color: #7dd3fc; }
.st.problematic, .st.high_risk { color: var(--warn); }
.st.critical { color: var(--bad); }
.st.insufficient_data { color: #6b7280; }

.compare { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.compare figure, .ai { margin: 0; }
.ai { margin-top: 12px; }
figcaption { font-size: 12px; color: var(--muted); padding-top: 6px; text-align: center; }

.narrative { background: var(--panel-2); border-radius: 8px; padding: 12px; margin: 0 0 12px; }
.attrib { font-size: 11.5px; margin: 10px 0 0; text-align: right; }

.issues { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }
.issues li { border: 1px solid var(--line); border-radius: 10px; padding: 12px; }
.ih { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }
.pill { font-size: 11px; padding: 1px 8px; border-radius: 999px; background: #2a3342; }
.pill.high { background: #4a1f22; color: var(--bad); }
.pill.medium { background: #4a3c14; color: var(--warn); }
.pill.low { background: #1d4633; color: var(--accent); }
.cat { font-size: 12px; color: var(--accent-2); }
.loc, .ev { font-size: 13px; }
.sol { margin-top: 6px; font-size: 13px; }
.sol b { color: var(--accent); margin-right: 6px; }

.case { display: grid; grid-template-columns: 220px 1fr; gap: 14px; align-items: start; }
.case ul { margin: 6px 0 0; padding-left: 18px; font-size: 13px; }
.case p { margin: 0; }

.improve { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 12px; }
.improve .row { font-size: 13px; }
.improve .k {
  display: inline-block; width: 38px; font-size: 11px; color: var(--muted);
  margin-right: 8px;
}
.improve .k.on { color: var(--accent); }

@media (max-width: 900px) {
  .compare, .case { grid-template-columns: 1fr; }
  .criteria li { grid-template-columns: 1fr; gap: 2px; }
  .criteria li b.mono { display: inline; }
}
</style>
