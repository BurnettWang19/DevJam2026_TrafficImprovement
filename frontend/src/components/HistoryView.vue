<script setup>
import { computed, onMounted, ref } from 'vue'

const emit = defineEmits(['open-result'])
const entries = ref([])
const selected = ref(null)
const query = ref('')
const priority = ref('all')
const loading = ref(true)
const error = ref('')

const severityTotal = (item) => Object.values(item.severity || {}).reduce((a, b) => a + b, 0)
const priorityOf = (item) => {
  if ((item.severity?.critical || 0) > 0) return 'critical'
  if ((item.severity?.high || 0) > 0 || (item.score ?? 100) < 50) return 'high'
  if ((item.severity?.medium || 0) > 0 || (item.score ?? 100) < 75) return 'medium'
  return 'low'
}
const priorityLabel = { critical: '極高', high: '高', medium: '中', low: '低' }

const filtered = computed(() => entries.value.filter((item) => {
  const text = `${item.location} ${item.lat} ${item.lng}`.toLowerCase()
  return text.includes(query.value.trim().toLowerCase())
    && (priority.value === 'all' || priorityOf(item) === priority.value)
}))

const stats = computed(() => ({
  total: entries.value.length,
  critical: entries.value.filter((item) => ['critical', 'high'].includes(priorityOf(item))).length,
  incomplete: entries.value.filter((item) => item.score == null || !item.osm_available).length,
}))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/api/history')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    entries.value = (await res.json()).entries || []
    if (entries.value.length) await select(entries.value[0])
  } catch (e) {
    error.value = `無法載入分析歷史：${e.message}`
  } finally {
    loading.value = false
  }
}

async function select(item) {
  const res = await fetch(`/api/history/${encodeURIComponent(item.id)}`)
  if (!res.ok) return
  selected.value = { summary: item, result: await res.json() }
}

async function removeSelected() {
  if (!selected.value || !window.confirm('確定刪除這筆分析紀錄？此動作無法復原。')) return
  const id = selected.value.summary.id
  const res = await fetch(`/api/history/${encodeURIComponent(id)}`, { method: 'DELETE' })
  if (!res.ok) return
  entries.value = entries.value.filter((item) => item.id !== id)
  selected.value = null
  if (entries.value.length) await select(entries.value[0])
}

const dateParts = (value) => {
  if (!value) return ['—', '—']
  const [date, time] = value.split(' ')
  return [date?.replaceAll('-', '/'), time?.slice(0, 5)]
}

onMounted(load)
</script>

<template>
  <section class="history-page">
    <div class="history-main">
      <header class="page-head">
        <div>
          <p class="eyebrow">Analysis archive</p>
          <h1>分析歷史</h1>
          <p>瀏覽曾經完成的路口分析結果，快速找回設計判讀與改善建議。</p>
        </div>
        <button class="refresh" @click="load">↻ 更新資料</button>
      </header>

      <div class="stats-row">
        <article><span class="stat-icon green">▥</span><div><small>已分析路口</small><b>{{ stats.total }}</b><em>累積完成分析</em></div></article>
        <article><span class="stat-icon red">⚑</span><div><small>需要優先處理</small><b>{{ stats.critical }}</b><em>含極高與高風險</em></div></article>
        <article><span class="stat-icon amber">▤</span><div><small>待補充資料</small><b>{{ stats.incomplete }}</b><em>資料不足或降級分析</em></div></article>
      </div>

      <div class="history-card">
        <div class="toolbar">
          <label class="search"><span>⌕</span><input v-model="query" placeholder="搜尋路口或座標" /></label>
          <label class="filter">改善優先度
            <select v-model="priority">
              <option value="all">全部</option>
              <option value="critical">極高</option>
              <option value="high">高</option>
              <option value="medium">中</option>
              <option value="low">低</option>
            </select>
          </label>
        </div>

        <div v-if="loading" class="empty">正在載入分析歷史…</div>
        <div v-else-if="error" class="empty error">{{ error }}</div>
        <div v-else-if="!filtered.length" class="empty">
          <b>尚無符合條件的分析紀錄</b>
          <span>完成一次路口分析後，結果會自動出現在這裡。</span>
        </div>
        <div v-else class="table-wrap">
          <table>
            <thead><tr><th>路口</th><th>分析日期</th><th>改善優先度</th><th>風險問題</th><th>完整度</th><th>狀態</th><th></th></tr></thead>
            <tbody>
              <tr v-for="item in filtered" :key="item.id"
                  :class="{ active: selected?.summary.id === item.id }" @click="select(item)">
                <td><strong>{{ item.location }}</strong><small>{{ Number(item.lat).toFixed(5) }}, {{ Number(item.lng).toFixed(5) }}</small></td>
                <td><span>{{ dateParts(item.analyzed_at)[0] }}</span><small>{{ dateParts(item.analyzed_at)[1] }}</small></td>
                <td><span class="priority" :class="priorityOf(item)">{{ priorityLabel[priorityOf(item)] }}</span></td>
                <td><b>{{ severityTotal(item) }}</b><small>項問題</small></td>
                <td><div class="meter"><i :style="{ width: `${item.score ?? 0}%` }"></i></div><small>{{ item.score ?? '—' }}%</small></td>
                <td><span class="state">● 已完成</span></td>
                <td><button class="peek" aria-label="查看詳情">›</button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <footer class="table-foot">顯示 {{ filtered.length }} 筆，共 {{ entries.length }} 筆分析紀錄</footer>
      </div>
    </div>

    <aside class="detail-panel" v-if="selected">
      <button class="close" @click="selected = null" aria-label="關閉">×</button>
      <p class="eyebrow">Selected intersection</p>
      <h2>{{ selected.summary.location }}</h2>
      <p class="coords">{{ selected.summary.lat }}, {{ selected.summary.lng }}</p>

      <img v-if="selected.result.current_image" :src="selected.result.current_image" alt="路口分析圖" class="preview" />

      <div class="severity-grid">
        <div class="crit"><small>CRITICAL</small><b>{{ selected.summary.severity.critical }}</b></div>
        <div class="high"><small>HIGH</small><b>{{ selected.summary.severity.high }}</b></div>
        <div class="mid"><small>MEDIUM</small><b>{{ selected.summary.severity.medium }}</b></div>
      </div>

      <div class="score-block">
        <div><span>證據完整度</span><small>{{ selected.summary.osm_available ? '資料齊全' : 'OSM 降級' }}</small></div>
        <b>{{ selected.summary.score ?? '—' }}%</b>
        <div class="score-line"><i :style="{ width: `${selected.summary.score ?? 0}%` }"></i></div>
      </div>

      <div class="summary-block">
        <h3>分析摘要</h3>
        <p>{{ selected.result.score?.summary || selected.result.message || '此紀錄沒有摘要文字。' }}</p>
      </div>

      <dl>
        <div><dt>分析時間</dt><dd>{{ selected.summary.analyzed_at || '—' }}</dd></div>
        <div><dt>分析範圍</dt><dd>{{ selected.summary.size_m }} 公尺</dd></div>
        <div><dt>資料來源</dt><dd>{{ selected.summary.osm_available ? 'OSM＋衛星影像' : '衛星影像' }}</dd></div>
      </dl>

      <div class="detail-actions">
        <button class="primary" @click="emit('open-result', selected.result)">開啟完整結果</button>
        <button class="danger" @click="removeSelected">刪除紀錄</button>
      </div>
    </aside>
  </section>
</template>

<style scoped>
.history-page { min-height: 100%; display: grid; grid-template-columns: minmax(0, 1fr) 360px; background: #f6f7f4; }
.history-main { padding: 42px 42px 56px; min-width: 0; }
.page-head { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 26px; }
.page-head h1 { margin: 0; color: #173f32; font-size: 34px; line-height: 1.2; letter-spacing: -.04em; }
.page-head p:last-child { margin: 7px 0 0; color: #77817b; font-size: 13px; }
.refresh { color: #315e4d; background: transparent; }
.stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 20px; }
.stats-row article { display: flex; align-items: center; gap: 15px; padding: 18px; background: white; border: 1px solid #e6e9e4; border-radius: 12px; box-shadow: 0 7px 22px rgba(27, 56, 43, .04); }
.stat-icon { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 50%; font-size: 18px; }
.stat-icon.green { color: #14764e; background: #e6f5ed; }.stat-icon.red { color: #d3524a; background: #fceceb; }.stat-icon.amber { color: #c98b14; background: #fff3d9; }
.stats-row small, .stats-row em { display: block; color: #758079; font-style: normal; font-size: 11px; line-height: 1.4; }.stats-row b { display: inline-block; margin-right: 7px; color: #183d31; font-size: 26px; line-height: 1.1; }
.history-card { overflow: hidden; background: white; border: 1px solid #e4e8e2; border-radius: 13px; box-shadow: 0 12px 36px rgba(31, 61, 48, .05); }
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 16px; border-bottom: 1px solid #edf0ec; }
.search { display: flex; align-items: center; width: 300px; height: 38px; padding: 0 12px; border: 1px solid #dfe4de; border-radius: 8px; color: #89928d; }
.search input { border: 0; padding: 0 8px; outline: 0; font-size: 13px; }.filter { display: flex; gap: 8px; align-items: center; margin: 0; font-size: 12px; }.filter select { border: 1px solid #dfe4de; border-radius: 8px; padding: 8px 28px 8px 10px; background: white; }
.table-wrap { overflow-x: auto; } table { width: 100%; border-collapse: collapse; font-size: 12px; } th { padding: 12px 14px; text-align: left; color: #78827c; background: #fafbf9; font-weight: 600; white-space: nowrap; } td { padding: 14px; border-top: 1px solid #edf0ec; color: #4f5b54; vertical-align: middle; } tbody tr { cursor: pointer; transition: background .15s; } tbody tr:hover, tbody tr.active { background: #f0f8f4; } tbody tr.active { box-shadow: inset 3px 0 #159263; }
td strong, td span, td small { display: block; white-space: nowrap; } td strong { color: #183d31; font-size: 12.5px; } td small { color: #929a95; font-size: 10px; }.priority { display: inline-block; width: fit-content; padding: 3px 10px; border-radius: 999px; }.priority.critical { color: #c8443c; background: #fde9e7; }.priority.high { color: #d76e2e; background: #fff0e6; }.priority.medium { color: #b77b0d; background: #fff5d9; }.priority.low { color: #25825b; background: #e8f5ed; }.meter { display: inline-block; width: 54px; height: 5px; margin-right: 7px; border-radius: 9px; background: #e8ece8; overflow: hidden; vertical-align: middle; }.meter i, .score-line i { display: block; height: 100%; background: #149261; border-radius: inherit; }.state { color: #31815f; }.peek { border: 0; background: transparent; color: #47705f; font-size: 22px; padding: 0; }.table-foot { padding: 12px 16px; color: #8b948f; border-top: 1px solid #edf0ec; font-size: 11px; }.empty { display: grid; place-items: center; min-height: 260px; color: #768079; }.empty span { font-size: 12px; }.empty.error { color: #b84f49; }
.detail-panel { position: relative; padding: 42px 26px 26px; background: white; border-left: 1px solid #e5e9e4; box-shadow: -12px 0 30px rgba(29, 58, 45, .04); overflow-y: auto; }.detail-panel .close { position: absolute; top: 18px; right: 20px; border: 0; padding: 0; background: none; color: #758079; font-size: 24px; }.detail-panel h2 { margin: 0; color: #173f32; font-size: 22px; }.coords { margin: 2px 0 14px; color: #88928c; font-size: 11px; }.preview { width: 100%; aspect-ratio: 16/10; object-fit: cover; border-radius: 10px; border: 1px solid #e2e7e2; }.severity-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 14px 0 20px; }.severity-grid div { padding: 10px; border: 1px solid #edf0ec; border-radius: 8px; text-align: center; }.severity-grid small { display: block; font-size: 9px; }.severity-grid b { font-size: 24px; }.severity-grid .crit { color: #c94d46; }.severity-grid .high { color: #d67632; }.severity-grid .mid { color: #c08a22; }.score-block { padding: 16px 0; border-top: 1px solid #edf0ec; border-bottom: 1px solid #edf0ec; }.score-block > div:first-child { display: flex; justify-content: space-between; }.score-block span { font-weight: 700; color: #294b3e; }.score-block small { color: #8b948e; }.score-block b { color: #16895c; font-size: 27px; }.score-line { height: 5px; background: #e6ebe7; border-radius: 5px; }.summary-block { padding: 18px 0; border-bottom: 1px solid #edf0ec; }.summary-block h3 { margin: 0 0 8px; color: #294b3e; font-size: 13px; }.summary-block p { margin: 0; color: #626e67; font-size: 12px; line-height: 1.7; } dl { margin: 18px 0; } dl div { display: flex; justify-content: space-between; padding: 5px 0; font-size: 11px; } dt { color: #89928d; } dd { margin: 0; color: #4c5952; }.detail-actions { display: grid; gap: 9px; }.detail-actions button { width: 100%; }.danger { color: #cb4e47; border-color: #edb9b5; background: white; }
@media (max-width: 1180px) { .history-page { grid-template-columns: 1fr; }.detail-panel { border-left: 0; border-top: 1px solid #e5e9e4; }.stats-row { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .history-main { padding: 26px 16px; }.page-head { align-items: flex-start; gap: 15px; }.toolbar { align-items: stretch; flex-direction: column; }.search { width: 100%; } }
</style>
