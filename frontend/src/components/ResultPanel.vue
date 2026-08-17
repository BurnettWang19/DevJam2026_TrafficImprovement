<script setup>
import { computed, defineAsyncComponent, ref } from 'vue'
import TraceTimeline from './TraceTimeline.vue'
import DesignExplorer from './DesignExplorer.vue'
// CesiumJS 很大，切成獨立 chunk，點「3D 檢視」才載入
const Design3D = defineAsyncComponent(() => import('./Design3D.vue'))
import CountUp from './CountUp.vue'

const props = defineProps({ result: { type: Object, required: true } })
const emit = defineEmits(['back'])

const r = computed(() => props.result)

/* 嚴重程度：後端給 high/medium/low/uncertain，介面顯示中文 */
const SEV = {
  high: { label: '高度', cls: 'high' },
  critical: { label: '極高', cls: 'crit' },
  medium: { label: '中度', cls: 'mid' },
  low: { label: '低度', cls: 'low' },
  uncertain: { label: '待確認', cls: 'mid' },
}
const sev = (s) => SEV[String(s || '').toLowerCase()] || SEV.uncertain

/* 分數不再直接呈現數字，改成四個等級 */
const BANDS = [
  { min: 75, key: 'good', label: '完善' },
  { min: 50, key: 'ok', label: '尚可' },
  { min: 25, key: 'weak', label: '待加強' },
  { min: 0, key: 'bad', label: '嚴重' },
]
const band = computed(() => {
  const s = r.value.score?.score
  if (typeof s !== 'number') return { key: 'unknown', label: '資料不足' }
  return BANDS.find((b) => s >= b.min) || BANDS[BANDS.length - 1]
})

/* 依 斑馬線 → 人行道 → 車道標線 排序，同類再依嚴重度 */
const CAT_ORDER = ['斑馬線', '人行道', '車道標線']
const SEV_ORDER = { critical: 0, high: 1, medium: 2, low: 3, uncertain: 4 }

const allIssues = computed(() => {
  const out = []
  for (const cat of Object.values(r.value.findings || {})) {
    for (const i of cat.issues || []) out.push({ ...i, category: cat.category })
  }
  return out.sort((a, b) => {
    const c = CAT_ORDER.indexOf(a.category) - CAT_ORDER.indexOf(b.category)
    if (c !== 0) return c
    return (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9)
  })
})

const cases = computed(() => r.value.classic_cases
  || (r.value.classic_case ? [r.value.classic_case] : []))

const annotations = computed(() => r.value.design?.annotations || [])
const view = ref('2d')        // 改善後設計：2D 互動 / 3D 檢視
const can3d = computed(() =>
  !!(r.value.design?.geojson?.features?.length && r.value.bbox))

/* 報告改成條列。舊格式（長段落）仍相容，切成句子當作條列。 */
const toPoints = (list, fallback) => {
  if (Array.isArray(list) && list.length) return list.filter(Boolean)
  if (typeof fallback === 'string' && fallback.trim()) {
    return fallback.split(/[。；\n]/).map((s) => s.trim()).filter(Boolean).slice(0, 3)
  }
  return []
}
const problemPoints = computed(() =>
  toPoints(r.value.report?.problem_points, r.value.report?.problem_narrative))
const improvePoints = computed(() =>
  toPoints(r.value.report?.improvement_points, r.value.report?.improvement_narrative))

const cost = computed(() => r.value.cost)
const currencyPrefix = computed(() => cost.value?.currency === 'TWD' ? 'NT$ ' : '$')
const averageCost = computed(() => {
  const supplied = Number(cost.value?.total?.average)
  if (Number.isFinite(supplied) && supplied >= 0) return supplied
  const low = Number(cost.value?.total?.low)
  const high = Number(cost.value?.total?.high)
  if (!Number.isFinite(low) || !Number.isFinite(high)) return 0
  return Math.ceil(((low + high) / 2) / 100) * 100
})
const money = (n) => currencyPrefix.value + Number(n || 0).toLocaleString('en-US')

const coords = computed(() => {
  const i = r.value.input || {}
  return `${Number(i.lat).toFixed(4)}, ${Number(i.lng).toFixed(4)}`
})
</script>

<template>
  <div class="review">
    <!-- ── 頁首 ──────────────────────────────────────────── -->
    <header class="head" v-reveal>
      <div class="headspacer" aria-hidden="true"></div>

      <div class="title">
        <p class="eyebrow">Road Design Review</p>
        <h1>
          {{ r.verdict === 'not_intersection' ? '此範圍並非路口'
            : r.verdict === 'no_problem' ? '路口設計檢核' : '路口改善建議' }}
        </h1>
        <p class="sub">
          {{ r.verdict === 'not_intersection'
            ? '判斷迴圈已中斷，未進行後續的問題診斷與重繪。'
            : r.verdict === 'no_problem'
              ? '分析完成，此路口未發現重大設計問題。'
              : '分析完成，以下是依現況問題提出的概念改善方向。' }}
        </p>
      </div>

      <div class="badge" :class="band.key" v-if="r.verdict !== 'not_intersection'">
        <b>{{ band.label }}</b>
        <small>設計評估</small>
      </div>
    </header>

    <div class="cachebar" v-if="r.cached">
      這是 <b>{{ r.cached_at }}</b> 預先跑好的結果，未重新呼叫模型。
    </div>

    <!-- ── 基本資訊列 ────────────────────────────────────── -->
    <div class="metabar" v-reveal="{ delay: 80 }">
      <div><span>分析位置</span><b class="mono">{{ coords }}</b></div>
      <div><span>路口型態</span><b>{{ r.intersection_type?.type || '—' }}</b></div>
      <div>
        <span>證據涵蓋</span>
        <b>{{ r.score?.data_sufficient === false ? '證據不足' : '依現有資料' }}</b>
      </div>
      <div><span>資料來源</span><b>OSM・影像辨識</b></div>
    </div>

    <!-- ── 非路口 ────────────────────────────────────────── -->
    <template v-if="r.verdict === 'not_intersection'">
      <div class="notice" v-reveal>{{ r.message }}</div>
      <figure class="single" v-reveal="{ delay: 100 }">
        <img :src="r.current_image" alt="現況向量圖" />
        <figcaption>現況：衛星影像與 OSM／影像辨識向量</figcaption>
      </figure>
    </template>

    <template v-else>
      <!-- ── 前後對照 ──────────────────────────────────── -->
      <div class="compare" :class="{ single: !r.design_image }">
        <figure v-reveal>
          <img :src="r.current_image" alt="改善前" />
          <figcaption class="tag light">改善前<span>衛星影像與現況向量</span></figcaption>
        </figure>
        <figure v-if="r.design_image_ai || r.design_image" v-reveal="{ delay: 140 }">
          <img :src="r.design_image_ai || r.design_image" alt="建議方案" />
          <figcaption class="tag dark">
            建議方案<span>{{ r.design_image_ai ? 'AI 概念示意圖' : '設計向量圖' }}</span>
          </figcaption>
        </figure>
      </div>

      <div class="attrib" v-if="r.imagery">
        底圖 {{ r.imagery.attribution }}・zoom {{ r.imagery.zoom }}・{{ r.imagery.meters_per_pixel }} m/px
      </div>

      <!-- ── 互動式設計圖：點標記放大看改動 ──────────── -->
      <section class="marked" v-if="r.design_image" v-reveal>
        <div class="markedhead">
          <div>
            <p class="eyebrow">Proposed Design</p>
            <h2>改善後的設計</h2>
          </div>
          <div class="toggle" v-if="can3d">
            <button :class="{ on: view === '2d' }" @click="view = '2d'">2D 互動</button>
            <button :class="{ on: view === '3d' }" @click="view = '3d'">3D 檢視</button>
          </div>
        </div>
        <Design3D v-if="view === '3d' && can3d"
                  :geojson="r.design.geojson"
                  :bbox="r.bbox" />
        <DesignExplorer v-else-if="annotations.length"
                        :image="r.design_image"
                        :annotations="annotations"
                        :key-changes="r.design?.key_changes || []"
                        :findings="r.findings || {}" />
        <img v-else class="markedimg" :src="r.design_image" alt="設計向量圖" />
      </section>

      <!-- ── 問題 / 改善（條列） ──────────────────────── -->
      <section class="twocol" v-if="problemPoints.length || improvePoints.length" v-reveal>
        <div v-if="problemPoints.length">
          <p class="eyebrow">Why It Matters</p>
          <h2>我們發現的問題</h2>
          <ul class="points bad"><li v-for="(p, i) in problemPoints" :key="i">{{ p }}</li></ul>
        </div>
        <div v-if="improvePoints.length">
          <p class="eyebrow">Proposed Design</p>
          <h2>新版設計如何改善</h2>
          <ul class="points good"><li v-for="(p, i) in improvePoints" :key="i">{{ p }}</li></ul>
        </div>
      </section>

      <section class="twocol" v-else-if="r.verdict === 'no_problem'" v-reveal>
        <div>
          <p class="eyebrow">Assessment</p>
          <h2>檢核結果</h2>
          <p>{{ r.message || r.score?.summary }}</p>
        </div>
      </section>

      <!-- ── 問題卡片 ──────────────────────────────────── -->
      <section class="issues" v-if="allIssues.length">
        <div class="card issue" v-for="(it, i) in allIssues" :key="it.id || i"
             v-reveal="{ delay: (i % 3) * 90 }">
          <div class="top">
            <span class="cat">{{ it.category }}</span>
            <span class="pill" :class="sev(it.severity).cls">{{ sev(it.severity).label }}</span>
          </div>
          <h3>{{ it.title }}</h3>
          <p class="desc">{{ it.evidence || it.standard_violated }}</p>
          <p class="fix" v-if="it.solution">{{ it.solution }}</p>
        </div>
      </section>

      <!-- ── 工程費用估算 ──────────────────────────────── -->
      <section class="cost" v-if="cost && cost.items?.length" v-reveal>
        <div class="costhead">
          <div class="costtitle">
            <p class="eyebrow">Cost Estimate</p>
            <h2>工程費用估算</h2>
          </div>
          <div class="costsummary">
            <div class="averageprice">
              <span>平均工程費</span>
              <b><CountUp :value="averageCost" :prefix="currencyPrefix" /></b>
              <small>依估算上下限取平均，進位至百元</small>
            </div>
            <div class="total">
              <span>合理估算區間</span>
              <b>{{ money(cost.total.low) }}–{{ money(cost.total.high) }}</b>
              <small>標線總面積 {{ cost.total_area_m2 }} ㎡</small>
            </div>
          </div>
        </div>

        <table class="costtable">
          <thead>
            <tr><th>項目</th><th>數量</th><th>單價</th><th class="r">金額</th></tr>
          </thead>
          <tbody>
            <tr v-for="it in cost.items" :key="it.key">
              <td>
                <b>{{ it.label }}</b>
                <em>{{ it.basis }}</em>
              </td>
              <td class="mono">{{ it.length_m }} m<br /><span>{{ it.area_m2 }} ㎡</span></td>
              <td class="mono rate">{{ it.rate }}</td>
              <td class="r mono">{{ money(it.low) }}</td>
            </tr>
            <tr v-for="(f, i) in cost.fixed" :key="'f' + i" class="fixedrow">
              <td><b>{{ f.label }}</b><em>{{ f.basis }}</em></td>
              <td class="mono">{{ f.quantity }}</td>
              <td class="mono rate">{{ f.rate }}</td>
              <td class="r mono">
                {{ f.low === f.high ? money(f.low) : `${money(f.low)}~${money(f.high)}` }}
              </td>
            </tr>
          </tbody>
        </table>

        <div class="uncovered" v-if="cost.uncovered?.length">
          <b>未計入總額</b>
          <span>
            下列屬土木構造物，單價與標線差一個量級，需另行估算：
            <template v-for="(u, i) in cost.uncovered" :key="u.label">
              {{ i ? '、' : '' }}{{ u.label }}<i class="mono"> {{ u.length_m }} m</i>
            </template>
          </span>
        </div>

        <details class="notes">
          <summary>計算依據與假設</summary>
          <ul><li v-for="(a, i) in cost.assumptions" :key="i">{{ a }}</li></ul>
        </details>
      </section>

      <!-- ── 經典案例 ──────────────────────────────────── -->
      <section class="cases" v-if="cases.length">
        <div class="caseshead" v-reveal>
          <div>
            <p class="eyebrow">Reference Cases</p>
            <h2>相似的經典案例</h2>
          </div>
          <p class="note">依路口型態與問題標籤匹配，提供設計脈絡而非直接套用。</p>
        </div>

        <div class="casegrid">
          <article class="card" v-for="(c, i) in cases" :key="c.id"
                   v-reveal="{ delay: (i % 3) * 90 }">
            <img v-if="c.image_data_url" :src="c.image_data_url" :alt="c.name" />
            <p class="where">{{ c.country }}</p>
            <h4>{{ c.name }}</h4>
            <p class="desc">{{ c.summary }}</p>
            <p class="fix">{{ c.match_reason }}</p>
          </article>
        </div>
      </section>

      <!-- ── 逐條改善對應 ──────────────────────────────── -->
      <section class="improve" v-if="r.report?.improvements?.length">
        <div v-reveal>
          <p class="eyebrow">Change Log</p>
          <h2>逐項對應</h2>
        </div>
        <div class="rows">
          <div class="row card" v-for="(im, i) in r.report.improvements" :key="i"
               v-reveal="{ delay: Math.min(i, 4) * 70 }">
            <div><span>問題</span><p>{{ im.problem }}</p></div>
            <div><span>改動</span><p class="hl">{{ im.change }}</p></div>
            <div><span>效果</span><p>{{ im.effect }}</p></div>
          </div>
        </div>
      </section>
    </template>

    <!-- ── 分析流程軌跡（原左側欄的時間軸） ──────────────── -->
    <details class="pipeline card" v-if="r.trace?.length">
      <summary>
        <span class="eyebrow" style="margin:0">Pipeline</span>
        分析流程軌跡 · {{ r.trace.length }} 步
      </summary>
      <TraceTimeline :trace="r.trace" />
    </details>

    <!-- ── 重選地點 ──────────────────────────────────────── -->
    <footer class="foot" v-reveal>
      <button class="backbtn" @click="emit('back')">← 重新選擇路口</button>
    </footer>
  </div>
</template>

<style scoped>
.review { display: flex; flex-direction: column; gap: 28px; max-width: 1180px; margin: 0 auto; }

/* ── 頁首 ─────────────────────────────────────────────── */
.head {
  display: grid;
  grid-template-columns: 180px 1fr 120px;
  align-items: start;
  gap: 20px;
  padding-top: 8px;
}
.pipeline { padding: 16px 22px; }
.pipeline summary {
  cursor: pointer; font-size: 14px; font-weight: 600; color: var(--text-2);
  display: flex; align-items: center; gap: 12px;
}
.pipeline summary:hover { color: var(--green-800); }
.pipeline[open] summary { margin-bottom: 14px; }

.foot { display: flex; justify-content: center; padding: 10px 0 20px; }
.backbtn {
  padding: 13px 40px; border-radius: 999px;
  font-size: 15px; font-weight: 600; color: var(--green-800);
}
.backbtn:hover { border-color: var(--green-600); color: var(--green-700); }
.title { text-align: center; }
.title h1 {
  margin: 0 0 10px;
  font-size: 42px; line-height: 1.2; font-weight: 800;
  color: var(--green-900); letter-spacing: -.01em;
}
.title .sub { margin: 0; color: var(--text-2); }

.badge {
  justify-self: end;
  width: 112px; height: 112px; border-radius: 50%;
  display: grid; place-content: center; text-align: center;
  background: var(--green-900); color: #eef3ec;
}
.badge b { display: block; font-size: 26px; font-weight: 800; line-height: 1.15; }
.badge small { font-size: 11px; opacity: .72; letter-spacing: .06em; }
.badge.weak { background: #b8721c; }
.badge.bad { background: #a8412c; }
.badge.unknown { background: #7b837c; }

.cachebar {
  background: var(--sage); border: 1px solid #d5e0d2; color: var(--green-800);
  border-radius: 12px; padding: 10px 16px; font-size: 13px;
}

/* ── 基本資訊列 ───────────────────────────────────────── */
.metabar {
  display: grid; grid-template-columns: repeat(4, 1fr);
  background: var(--surface); border: 1px solid var(--line-soft);
  border-radius: 14px; overflow: hidden;
}
.metabar > div { padding: 14px 20px; border-left: 1px solid var(--line-soft); }
.metabar > div:first-child { border-left: none; }
.metabar span { display: block; font-size: 12px; color: var(--muted); }
.metabar b { font-weight: 600; color: var(--text); }

/* ── 圖片 ─────────────────────────────────────────────── */
.compare { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.compare.single { grid-template-columns: 1fr; }
.compare figure, .single figure { margin: 0; position: relative; }
.compare img, .single img {
  width: 100%; display: block; border-radius: 16px; border: 1px solid var(--line-soft);
}
.tag {
  position: absolute; top: 16px; left: 16px;
  display: flex; align-items: baseline; gap: 8px;
  padding: 7px 15px; border-radius: 999px;
  font-weight: 700; font-size: 14px;
}
.tag span { font-weight: 400; font-size: 12.5px; opacity: .75; }
.tag.light { background: rgba(255, 255, 255, .93); color: var(--green-900); }
.tag.dark { background: var(--green-900); color: #eef3ec; }

.single { margin: 0; }
.single figcaption { font-size: 12.5px; color: var(--muted); padding-top: 8px; }
.attrib { font-size: 11.5px; color: var(--muted); text-align: right; margin-top: -18px; }

/* ── 改動標示 ─────────────────────────────────────────── */
.marked {
  background: var(--surface); border: 1px solid var(--line-soft);
  border-radius: 18px; padding: 30px 34px 34px;
}
.markedhead {
  display: flex; justify-content: space-between; align-items: flex-end;
  gap: 20px; margin-bottom: 20px;
}
.markedhead h2 { margin: 0; font-size: 25px; font-weight: 800; color: var(--green-900); }
.toggle {
  display: flex; gap: 4px; padding: 4px;
  background: var(--bg-sunken); border-radius: 999px; flex: none;
}
.toggle button {
  border: none; background: none; border-radius: 999px;
  padding: 6px 16px; font-size: 13px; color: var(--text-2);
}
.toggle button:hover { background: rgba(255, 255, 255, .6); }
.toggle button.on {
  background: var(--green-900); color: var(--bg); font-weight: 600;
}
.toggle button.on:hover { background: var(--green-800); }
.markedimg {
  width: 100%; display: block;
  border-radius: 14px; border: 1px solid var(--line-soft);
}

/* ── 條列 ─────────────────────────────────────────────── */
.points { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.points li {
  position: relative; padding-left: 24px; color: var(--text-2); font-size: 15px;
}
.points li::before {
  content: ''; position: absolute; left: 2px; top: .62em;
  width: 8px; height: 8px; border-radius: 50%;
}
.points.bad li::before { background: var(--sev-high-fg); }
.points.good li::before { background: var(--green-600); }

.notice {
  background: var(--surface); border: 1px solid var(--line-soft);
  border-left: 3px solid #a8412c; border-radius: 14px; padding: 18px 22px;
}

/* ── 兩欄敘述 ─────────────────────────────────────────── */
.twocol {
  display: grid; grid-template-columns: 1fr 1fr; gap: 48px;
  background: var(--surface); border: 1px solid var(--line-soft);
  border-radius: 18px; padding: 34px 38px;
}
.twocol > div + div { border-left: 1px solid var(--line-soft); padding-left: 48px; margin-left: -48px; }
.twocol h2 { margin: 0 0 14px; font-size: 25px; font-weight: 800; color: var(--green-900); }
.twocol p { margin: 0; color: var(--text-2); }

/* ── 問題卡片 ─────────────────────────────────────────── */
.issues { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.issue { padding: 24px 26px 28px; display: flex; flex-direction: column; }
.top { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.cat { font-size: 13px; color: var(--muted); }
.pill {
  font-size: 12.5px; font-weight: 600; padding: 3px 13px; border-radius: 999px;
  background: var(--sev-mid-bg); color: var(--sev-mid-fg);
}
.pill.high { background: var(--sev-high-bg); color: var(--sev-high-fg); }
.pill.crit { background: var(--sev-crit-bg); color: var(--sev-crit-fg); }
.pill.low { background: var(--sev-low-bg); color: var(--sev-low-fg); }

.issue h3 {
  margin: 14px 0 12px; font-size: 22px; line-height: 1.4;
  font-weight: 800; color: var(--green-900); letter-spacing: -.01em;
}
.desc { margin: 0; color: var(--text-2); font-size: 14.5px; }
.fix {
  margin: 18px 0 0; font-weight: 700; color: var(--green-700); font-size: 14.5px;
}

/* ── 工程費用估算 ─────────────────────────────────────── */
.cost {
  background: var(--surface); border: 1px solid var(--line-soft);
  border-radius: 18px; padding: 30px 34px 26px;
}
.costhead {
  display: grid; grid-template-columns: minmax(170px, .6fr) minmax(440px, 1.4fr);
  align-items: end;
  gap: 24px; margin-bottom: 22px;
}
.costhead h2 { margin: 0; font-size: 25px; font-weight: 800; color: var(--green-900); }
.costsummary {
  display: grid; grid-template-columns: minmax(250px, 1fr) auto;
  align-items: end; gap: 28px; padding-left: 24px;
  border-left: 3px solid var(--green-600);
}
.averageprice span, .total span {
  display: block; font-size: 11.5px; font-weight: 700;
  letter-spacing: .08em; color: var(--muted);
}
.averageprice b {
  display: block; margin: 4px 0 3px;
  color: var(--green-900); font-size: clamp(40px, 5vw, 58px);
  font-weight: 900; line-height: .98; letter-spacing: -.055em;
  font-variant-numeric: tabular-nums;
}
.averageprice small, .total small { font-size: 12px; color: var(--text-2); }
.total { text-align: right; padding-bottom: 3px; }
.total span { display: block; font-size: 12px; color: var(--muted); }
.total b {
  display: block; margin: 4px 0 5px; font-size: 17px; font-weight: 700;
  color: var(--text); letter-spacing: -.015em; line-height: 1.3;
  font-variant-numeric: tabular-nums;
}

.costtable { width: 100%; border-collapse: collapse; font-size: 14px; }
.costtable th {
  text-align: left; font-size: 11.5px; letter-spacing: .1em;
  text-transform: uppercase; color: var(--muted); font-weight: 600;
  padding: 0 12px 8px 0; border-bottom: 1px solid var(--line);
}
.costtable td { padding: 13px 12px 13px 0; border-bottom: 1px solid var(--line-soft); vertical-align: top; }
.costtable td b { display: block; color: var(--green-900); font-size: 15px; }
.costtable td em {
  display: block; font-style: normal; font-size: 12px;
  color: var(--muted); margin-top: 3px; line-height: 1.5;
}
.costtable td span { color: var(--muted); font-size: 12.5px; }
.costtable .rate { color: var(--text-2); font-size: 12.5px; white-space: nowrap; }
.costtable .r { text-align: right; white-space: nowrap; }
.costtable tbody tr:last-child td { border-bottom: none; }
.fixedrow td { background: #fbfaf7; }
.fixedrow td:first-child { border-radius: 8px 0 0 8px; }
.fixedrow td:last-child { border-radius: 0 8px 8px 0; }

.uncovered {
  margin-top: 18px; padding: 14px 16px; border-radius: 10px;
  background: var(--bg-sunken); font-size: 13px; color: var(--text-2);
}
.uncovered b { color: var(--green-900); margin-right: 8px; }
.uncovered i { font-style: normal; color: var(--muted); }

.notes { margin-top: 14px; }
.notes summary { cursor: pointer; font-size: 12.5px; color: var(--text-2); }
.notes ul { margin: 10px 0 0; padding-left: 20px; font-size: 12.5px; color: var(--muted); }
.notes li { margin-bottom: 5px; }

/* ── 經典案例 ─────────────────────────────────────────── */
.cases { background: var(--sage); border-radius: 22px; padding: 36px 38px 40px; }
.caseshead {
  display: flex; justify-content: space-between; align-items: flex-end;
  gap: 24px; margin-bottom: 26px;
}
.caseshead h2 { margin: 0; font-size: 30px; font-weight: 800; color: var(--green-900); }
.caseshead .note { margin: 0; font-size: 13px; color: var(--text-2); text-align: right; }
.casegrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.casegrid .card { padding: 22px 24px 26px; border-color: transparent; }
.casegrid img {
  width: 100%; border-radius: 10px; margin-bottom: 14px; display: block;
  aspect-ratio: 16 / 10; object-fit: cover;
}
.where { margin: 0 0 4px; font-size: 12.5px; color: var(--muted); }
.casegrid h4 { margin: 0 0 10px; font-size: 19px; font-weight: 800; color: var(--green-900); }

/* ── 逐項對應 ─────────────────────────────────────────── */
.improve h2 { margin: 0 0 18px; font-size: 25px; font-weight: 800; color: var(--green-900); }
.rows { display: flex; flex-direction: column; gap: 12px; }
.row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 28px; padding: 20px 24px; }
.row span { display: block; font-size: 11.5px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
.row p { margin: 4px 0 0; font-size: 14.5px; color: var(--text-2); }
.row p.hl { color: var(--green-700); font-weight: 600; }

/* ── 窄螢幕 ───────────────────────────────────────────── */
@media (max-width: 1100px) {
  .issues, .casegrid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 780px) {
  .head { grid-template-columns: 1fr; }
  .headspacer { display: none; }
  .title { text-align: left; }
  .title h1 { font-size: 32px; }
  .badge { justify-self: start; }
  .metabar { grid-template-columns: 1fr 1fr; }
  .metabar > div:nth-child(odd) { border-left: none; }
  .compare, .issues, .casegrid, .row { grid-template-columns: 1fr; }
  .costhead { grid-template-columns: 1fr; align-items: start; }
  .costsummary { grid-template-columns: 1fr; padding-left: 18px; gap: 16px; }
  .total { text-align: left; }
  .costtable { font-size: 13px; }
  .costtable .rate { display: none; }
  .costtable th:nth-child(3) { display: none; }
  .twocol { grid-template-columns: 1fr; gap: 28px; padding: 26px; }
  .twocol > div + div { border-left: none; padding-left: 0; margin-left: 0; padding-top: 24px; border-top: 1px solid var(--line-soft); }
}
</style>
