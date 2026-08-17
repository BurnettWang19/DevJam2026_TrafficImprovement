<script setup>
import { computed, ref } from 'vue'

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
// 預設看乾淨的設計圖；要看說明的人自己切過去
const showMarks = ref(false)

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

const coords = computed(() => {
  const i = r.value.input || {}
  return `${Number(i.lat).toFixed(4)}, ${Number(i.lng).toFixed(4)}`
})
</script>

<template>
  <div class="review">
    <!-- ── 頁首 ──────────────────────────────────────────── -->
    <header class="head" v-reveal>
      <button class="back" @click="emit('back')">← 重新選擇路口</button>

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

      <!-- ── 設計圖，需要說明的人再切到標示版 ────────── -->
      <section class="marked" v-if="r.design_image" v-reveal>
        <div class="markedhead">
          <div>
            <p class="eyebrow">Proposed Design</p>
            <h2>改善後的設計</h2>
          </div>
          <div class="toggle" v-if="r.annotated_image && annotations.length">
            <button :class="{ on: !showMarks }" @click="showMarks = false">設計圖</button>
            <button :class="{ on: showMarks }" @click="showMarks = true">標示改動位置</button>
          </div>
        </div>
        <img class="markedimg"
             :src="showMarks ? r.annotated_image : r.design_image"
             :alt="showMarks ? '改動標示圖' : '設計向量圖'" />
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
.back {
  background: none; border: none; padding: 6px 0;
  color: var(--text-2); font-size: 14px;
}
.back:hover { background: none; color: var(--green-700); }
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
  .title { text-align: left; }
  .title h1 { font-size: 32px; }
  .badge { justify-self: start; }
  .metabar { grid-template-columns: 1fr 1fr; }
  .metabar > div:nth-child(odd) { border-left: none; }
  .compare, .issues, .casegrid, .row { grid-template-columns: 1fr; }
  .twocol { grid-template-columns: 1fr; gap: 28px; padding: 26px; }
  .twocol > div + div { border-left: none; padding-left: 0; margin-left: 0; padding-top: 24px; border-top: 1px solid var(--line-soft); }
}
</style>
