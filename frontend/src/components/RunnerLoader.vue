<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'

/* 分析等待中的滿版小遊戲：
   - 小人自動奔跑，Space/↑/點擊 跳過三角錐，↓/S 蹲下閃過飛鳥
   - 進度模擬顯示在右上角（後端不回報進度，用漸近曲線）
   - 每完成一個小階段，一個寫著「✓ 某某完成」的小方塊從右往左飛過
   - 分析結果回來（done=true）→ 補完剩餘階段 → 放終點線 → 角色衝線後才 emit('finished') */

const props = defineProps({
  forcing: { type: Boolean, default: false },
  done: { type: Boolean, default: false },
})
const emit = defineEmits(['finished'])

const sceneEl = ref(null)

/* ── 物理參數（滿版尺寸） ─────────────────────── */
const RUNNER_X_RATIO = 0.16
const RUNNER_W = 36
const GRAVITY = 2000
const JUMP_V = 580            // 一般跳最高約 84px，跳得過錐、跳不上平台
const CHARGE_BONUS = 240      // 蓄力滿的加成 → 最高約 168px，上得了平台
const CHARGE_TIME = 0.65      // 蓄滿所需秒數
const OB_SPEED = 260
const BIRD_SPEED = 315
const FINISH_SPEED = 300
const CONE_W = 32
const CONE_HIT_H = 30
const BIRD_BOT = 54           // 飛鳥帶：離地 54~92px
const BIRD_TOP = 92
const PLAT_TOP = 122          // 平台頂面高度 —— 比飛鳥再高一點

const y = ref(0)
const airborne = ref(false)
const ducking = ref(false)
const charge = ref(0)
const stumbling = ref(false)
const celebrating = ref(false)
const cleared = ref(0)
const obstacles = reactive([])
const platforms = reactive([])
const finish = reactive({ active: false, x: 0, crossed: false })

let vy = 0
let raf = 0
let last = 0
let spawnAt = 0
let platSpawnAt = 0
let obId = 0
let platId = 0
let spawned = 0
let stumbleTimer = 0
let finishTimer = 0
const pendingTimers = []

/* ── 進度模擬（原 AnalysisProgress 的曲線搬進來） ── */
const STAGES = [
  { at: 0,  run: '擷取 OSM 向量與衛星影像…', done: 'OSM 向量與衛星影像' },
  { at: 16, run: '影像辨識補上車道標線…',   done: '車道標線辨識' },
  { at: 32, run: '依評分標準檢核設計…',     done: '評分檢核' },
  { at: 46, run: '判斷路口型態…',           done: '路口型態判斷' },
  { at: 58, run: '三個代理人平行診斷中…',   done: '三路代理人診斷' },
  { at: 72, run: '重繪改善設計…',           done: '改善設計重繪' },
  { at: 84, run: '生成設計圖面…',           done: '設計圖面生成' },
  { at: 93, run: '彙整報告與經典案例…',     done: '報告彙整' },
]
const progress = ref(0)
let doneStages = 0
let startTime = 0

const stageLabel = computed(() => {
  if (props.done && progress.value >= 99.5) return '分析完成！'
  let label = STAGES[0].run
  for (const s of STAGES) if (progress.value >= s.at) label = s.run
  return label
})

/* ── 階段完成的飛行小方塊 ─────────────────────── */
const banners = reactive([])
let bannerId = 0

function spawnBanner(stageIdx) {
  const id = bannerId++
  banners.push({ id, text: STAGES[stageIdx].done, lane: id % 3 })
  const t = setTimeout(() => {
    const i = banners.findIndex((b) => b.id === id)
    if (i > -1) banners.splice(i, 1)
  }, 6200)
  pendingTimers.push(t)
}

/* done → 剩餘階段快速補完，接著放終點線 */
watch(() => props.done, (v) => {
  if (!v) return
  const remaining = []
  for (let i = doneStages; i < STAGES.length; i++) remaining.push(i)
  doneStages = STAGES.length
  remaining.forEach((idx, k) => {
    pendingTimers.push(setTimeout(() => spawnBanner(idx), k * 240))
  })
  finishTimer = setTimeout(() => {
    finish.active = true
    finish.x = (sceneEl.value?.offsetWidth || 900) + 80
  }, remaining.length * 240 + 350)
})

/* ── 操作 ─────────────────────────────────────── */
function jump() {
  if (!airborne.value && !stumbling.value && !finish.crossed) {
    airborne.value = true
    vy = JUMP_V + CHARGE_BONUS * charge.value   // 蹲越久跳越高
    ducking.value = false
    charge.value = 0
  }
}

function onKeyDown(e) {
  if (e.code === 'Space' || e.code === 'ArrowUp' || e.code === 'KeyW') {
    e.preventDefault()
    jump()
  } else if (e.code === 'ArrowDown' || e.code === 'KeyS') {
    e.preventDefault()
    if (e.repeat) return                              // 長按鍵盤重複事件不要重觸發
    if (airborne.value && !ducking.value) vy -= 520   // 空中按蹲 → 快速落地
    ducking.value = true
  }
}
function onKeyUp(e) {
  if (e.code === 'ArrowDown' || e.code === 'KeyS') ducking.value = false
}
function onBlur() { ducking.value = false }

/* ── 主迴圈 ───────────────────────────────────── */
function step(now) {
  const dt = Math.min((now - last) / 1000, 0.05)
  last = now
  const w = sceneEl.value?.offsetWidth || 900
  const runnerX = w * RUNNER_X_RATIO

  /* 進度：一般走漸近曲線；done 後快速收斂到 100 */
  if (props.done) {
    progress.value = Math.min(100, progress.value + (100 - progress.value) * Math.min(dt * 4, 1) + dt * 6)
  } else {
    const TAU = props.forcing ? 42_000 : 16_000
    progress.value = Math.min(97 * (1 - Math.exp(-(now - startTime) / TAU)), 97)
    while (doneStages < STAGES.length - 1 && progress.value >= STAGES[doneStages + 1].at) {
      spawnBanner(doneStages)
      doneStages++
    }
  }

  /* 蓄力：在地面（或平台上）蹲著就累積，起跳或站起就歸零 */
  if (ducking.value && !airborne.value) {
    charge.value = Math.min(1, charge.value + dt / CHARGE_TIME)
  } else if (!ducking.value) {
    charge.value = 0
  }

  /* 站立面支撐檢查（平台是否還在腳下） */
  const supported = () => platforms.some(
    (p) => p.x < runnerX + RUNNER_W - 8 && p.x + p.w > runnerX + 8)

  /* 跳躍物理 */
  const prevY = y.value
  if (airborne.value) {
    vy -= GRAVITY * dt
    y.value += vy * dt
    // 下落中由上往下穿過平台頂面 → 站上平台
    if (vy <= 0 && prevY >= PLAT_TOP && y.value <= PLAT_TOP && supported()) {
      y.value = PLAT_TOP
      vy = 0
      airborne.value = false
    }
    if (y.value <= 0) {
      y.value = 0
      vy = 0
      airborne.value = false
    }
  } else if (y.value > 0 && !supported()) {
    airborne.value = true      // 平台到頭了，往下掉
    vy = 0
  }

  /* 生成障礙物：三角錐（跳）或飛鳥（蹲）。done 之後不再生成 */
  if (!props.done && now >= spawnAt) {
    const type = spawned > 1 && Math.random() < 0.38 ? 'bird' : 'cone'
    obstacles.push({ id: obId++, type, x: w + 40, hit: false, scored: false })
    spawned++
    spawnAt = now + 1150 + Math.random() * 1050
  }

  /* 生成平台：偶爾一座，蓄力跳上去可以躲開下面整段障礙 */
  if (!props.done && now >= platSpawnAt) {
    platforms.push({ id: platId++, x: w + 60, w: 210 + Math.random() * 130 })
    platSpawnAt = now + 6500 + Math.random() * 4500
  }
  for (let i = platforms.length - 1; i >= 0; i--) {
    platforms[i].x -= OB_SPEED * dt
    if (platforms[i].x + platforms[i].w < -60) platforms.splice(i, 1)
  }

  /* 移動與判定 */
  for (let i = obstacles.length - 1; i >= 0; i--) {
    const o = obstacles[i]
    o.x -= (o.type === 'bird' ? BIRD_SPEED : OB_SPEED) * dt

    const width = o.type === 'bird' ? 44 : CONE_W
    const overlap = o.x < runnerX + RUNNER_W && o.x + width > runnerX + 4
    if (overlap && !o.hit && !stumbling.value && !finish.crossed) {
      // 幾何判定：蹲下(身高 50)閃鳥、站在平台上(y=122)整個人在鳥帶之上
      const bodyH = ducking.value ? 50 : 90
      const collide = o.type === 'bird'
        ? y.value < BIRD_TOP && y.value + bodyH > BIRD_BOT
        : y.value < CONE_HIT_H                     // 三角錐：跳得夠高（或在平台上）就過
      if (collide) {
        o.hit = true
        stumbling.value = true
        clearTimeout(stumbleTimer)
        stumbleTimer = setTimeout(() => { stumbling.value = false }, 650)
      }
    }
    if (!o.scored && !o.hit && o.x + width < runnerX) {
      o.scored = true
      cleared.value++
    }
    if (o.x < -80) obstacles.splice(i, 1)
  }

  /* 終點線 */
  if (finish.active && !finish.crossed) {
    finish.x -= FINISH_SPEED * dt
    if (finish.x + 18 < runnerX) {
      finish.crossed = true
      celebrating.value = true
      ducking.value = false
      pendingTimers.push(setTimeout(() => emit('finished'), 950))
    }
  }

  raf = requestAnimationFrame(step)
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  window.addEventListener('blur', onBlur)
  last = performance.now()
  startTime = last
  spawnAt = last + 900
  raf = requestAnimationFrame(step)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('blur', onBlur)
  cancelAnimationFrame(raf)
  clearTimeout(stumbleTimer)
  clearTimeout(finishTimer)
  pendingTimers.forEach(clearTimeout)
})
</script>

<template>
  <div ref="sceneEl" class="stage" @pointerdown="jump">
    <!-- 天空與雲 -->
    <div class="cloud c1"></div>
    <div class="cloud c2"></div>
    <div class="cloud c3"></div>

    <!-- 森林（遠近兩層視差） -->
    <div class="forest far"></div>
    <div class="forest near"></div>

    <!-- 地面 -->
    <div class="ground"></div>
    <div class="road"></div>

    <!-- 右上角進度 -->
    <div class="hud card">
      <div class="hudtop">
        <span class="hudlabel">{{ stageLabel }}</span>
        <b class="mono">{{ Math.round(progress) }}%</b>
      </div>
      <div class="hudbar">
        <div class="hudfill" :style="{ width: progress + '%' }"></div>
      </div>
    </div>

    <!-- 左上角分數 -->
    <div class="score mono" v-if="cleared">越過 {{ cleared }}</div>

    <!-- 階段完成的小方塊 -->
    <div v-for="b in banners" :key="b.id" class="banner"
         :style="{ '--lane': b.lane }">
      <i>✓</i>{{ b.text }}<em>完成</em>
    </div>

    <!-- 平台（比飛鳥高一點，蓄力跳才上得去） -->
    <div v-for="p in platforms" :key="'p' + p.id" class="platform"
         :style="{ transform: `translateX(${p.x}px)`, width: p.w + 'px' }">
      <div class="deck"></div>
    </div>

    <!-- 小人 -->
    <div class="runner"
         :class="{ air: airborne, hit: stumbling, duck: ducking && !celebrating, win: celebrating }"
         :style="{ transform: `translateY(${-y}px)` }">
      <svg viewBox="0 0 60 80" class="figure">
        <g class="arm a2">
          <path d="M31 24 L24 32 L27 39" stroke="var(--green-700)" stroke-width="4.5"
                stroke-linecap="round" stroke-linejoin="round" fill="none" />
        </g>
        <g class="thigh t2">
          <line x1="27" y1="42" x2="24" y2="55" stroke="var(--green-700)" stroke-width="5" stroke-linecap="round" />
          <g class="shin s2">
            <line x1="24" y1="55" x2="22" y2="68" stroke="var(--green-700)" stroke-width="5" stroke-linecap="round" />
            <line x1="22" y1="68" x2="28" y2="70" stroke="var(--green-700)" stroke-width="4" stroke-linecap="round" />
          </g>
        </g>
        <g class="torso">
          <path d="M33 18 L27 42" stroke="var(--green-900)" stroke-width="5.5" stroke-linecap="round" fill="none" />
          <circle cx="35" cy="11" r="7" fill="var(--green-900)" />
        </g>
        <g class="thigh t1">
          <line x1="27" y1="42" x2="33" y2="55" stroke="var(--green-900)" stroke-width="5" stroke-linecap="round" />
          <g class="shin s1">
            <line x1="33" y1="55" x2="32" y2="69" stroke="var(--green-900)" stroke-width="5" stroke-linecap="round" />
            <line x1="32" y1="69" x2="38" y2="70.5" stroke="var(--green-900)" stroke-width="4" stroke-linecap="round" />
          </g>
        </g>
        <g class="arm a1">
          <path d="M31 24 L39 31 L36 38" stroke="var(--green-900)" stroke-width="4.5"
                stroke-linecap="round" stroke-linejoin="round" fill="none" />
        </g>
      </svg>
      <div class="shadow" :style="{ transform: `translateY(${y}px) scaleX(${1 - Math.min(y / 110, 0.5)})`,
                                    opacity: 1 - Math.min(y / 130, 0.6) }"></div>
      <!-- 蓄力條 -->
      <div class="chargebar" v-if="charge > 0.03">
        <div class="chargefill" :class="{ full: charge >= 1 }"
             :style="{ width: charge * 100 + '%' }"></div>
      </div>
    </div>

    <!-- 障礙物 -->
    <template v-for="o in obstacles" :key="o.id">
      <div v-if="o.type === 'cone'" class="cone" :class="{ tipped: o.hit }"
           :style="{ transform: `translateX(${o.x}px)` }">
        <svg viewBox="0 0 40 36">
          <path d="M20 3 L30 30 L10 30 Z" fill="#d97b29" />
          <path d="M16.4 13 L23.6 13 L25.6 19 L14.4 19 Z" fill="#fdf6ec" />
          <rect x="4" y="29" width="32" height="5" rx="2.5" fill="#b8621c" />
        </svg>
      </div>
      <div v-else class="bird" :class="{ down: o.hit }"
           :style="{ transform: `translateX(${o.x}px)` }">
        <svg viewBox="0 0 48 32">
          <g class="wing">
            <path d="M22 16 Q14 2 2 7 Q13 13 21 18 Z" fill="var(--green-800)" />
          </g>
          <ellipse cx="27" cy="17" rx="13" ry="6.5" fill="var(--green-900)" />
          <path d="M39 15 L46 17 L39 20 Z" fill="#d97b29" />
          <circle cx="34" cy="14.5" r="1.6" fill="#f4f3ee" />
        </svg>
      </div>
    </template>

    <!-- 終點線 -->
    <div v-if="finish.active" class="finishline"
         :style="{ transform: `translateX(${finish.x}px)` }">
      <span class="fintext">FINISH</span>
      <div class="flag"></div>
      <div class="pole"></div>
    </div>

    <!-- 操作提示（角落，小小的） -->
    <p class="tip">
      <kbd>Space</kbd>／<kbd>↑</kbd> 跳　<kbd>↓</kbd> 蹲・閃飛鳥　按住 <kbd>↓</kbd> 蓄力再 <kbd>↑</kbd> 大跳上平台
    </p>
  </div>
</template>

<style scoped>
.stage {
  --stride: .52s;
  --ground: 64px;
  position: absolute; inset: 0;
  overflow: hidden;
  cursor: pointer;
  touch-action: manipulation;
  user-select: none;
  background: linear-gradient(#f9f8f3 0%, #f2f1e8 55%, var(--bg) 100%);
}

/* ── 右上角進度 HUD ──────────────────────────── */
.hud {
  position: absolute; top: 18px; right: 20px; z-index: 30;
  width: min(340px, 46vw);
  padding: 13px 16px 14px;
  box-shadow: 0 6px 22px rgba(30, 58, 43, .1);
}
.hudtop {
  display: flex; justify-content: space-between; align-items: baseline;
  gap: 12px; margin-bottom: 8px;
}
.hudlabel { font-size: 13px; color: var(--text-2); }
.hudtop b { color: var(--green-700); font-weight: 600; font-size: 13px; flex: none; }
.hudbar {
  height: 6px; border-radius: 999px; background: var(--line); overflow: hidden;
}
.hudfill {
  height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, var(--green-700), var(--green-600));
  transition: width .2s linear;
}

.score {
  position: absolute; top: 22px; left: 22px; z-index: 30;
  font-size: 13px; color: var(--green-700); font-weight: 600;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: 999px; padding: 4px 14px;
}

/* ── 階段完成小方塊 ──────────────────────────── */
.banner {
  position: absolute; left: 100%;
  top: calc(88px + var(--lane) * 56px);
  z-index: 20;
  display: flex; align-items: center; gap: 7px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 7px 16px;
  font-size: 13px; font-weight: 600; color: var(--green-900);
  box-shadow: 0 4px 16px rgba(30, 58, 43, .12);
  white-space: nowrap;
  animation: fly-across 5.6s linear forwards;
  pointer-events: none;
}
.banner i {
  font-style: normal; font-weight: 800; color: var(--green-600);
}
.banner em { font-style: normal; color: var(--muted); font-weight: 400; }
@keyframes fly-across {
  to { transform: translateX(calc(-100vw - 380px)); }
}

/* ── 森林視差 ────────────────────────────────── */
.forest {
  position: absolute; left: 0; right: 0;
  bottom: var(--ground);
  background-repeat: repeat-x;
  background-position: bottom left;
  pointer-events: none;
}
.forest.far {
  height: 150px;
  opacity: .5;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='140'><g fill='%23c2cdb8'><path d='M30 58 L52 134 L8 134 Z'/><rect x='26' y='128' width='8' height='12'/><path d='M95 84 L111 134 L79 134 Z'/><rect x='92' y='128' width='6' height='12'/><path d='M170 46 L196 134 L144 134 Z'/><rect x='166' y='128' width='8' height='12'/><path d='M247 78 L266 134 L228 134 Z'/><rect x='244' y='128' width='6' height='12'/></g></svg>");
  background-size: 300px 140px;
  animation: forest-scroll-far 30s linear infinite;
}
.forest.near {
  height: 120px;
  opacity: .8;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='340' height='120'><g fill='%239cb294'><path d='M42 32 L68 114 L16 114 Z'/><rect x='38' y='108' width='9' height='12'/><path d='M150 60 L170 114 L130 114 Z'/><rect x='146' y='108' width='7' height='12'/><path d='M262 22 L292 114 L232 114 Z'/><rect x='258' y='108' width='9' height='12'/></g></svg>");
  background-size: 340px 120px;
  animation: forest-scroll-near 12s linear infinite;
}
/* 平移量必須是各自 tile 寬的整數倍，迴圈才無縫 */
@keyframes forest-scroll-far {
  from { background-position-x: 0; }
  to { background-position-x: -900px; }    /* 300px × 3 */
}
@keyframes forest-scroll-near {
  from { background-position-x: 0; }
  to { background-position-x: -1020px; }   /* 340px × 3 */
}

/* ── 地面與路面 ──────────────────────────────── */
.ground {
  position: absolute; left: 0; right: 0; bottom: 0;
  height: var(--ground);
  background: #e6e9db;
  border-top: 1px solid #d5dac6;
}
.road {
  position: absolute; left: 0; right: 0; bottom: calc(var(--ground) - 2px);
  height: 3px;
  background: repeating-linear-gradient(90deg,
    var(--green-700) 0 26px, transparent 26px 48px);
  border-radius: 2px;
  opacity: .5;
  animation: road-flow 1.1s linear infinite;
}
@keyframes road-flow {
  from { background-position-x: 0; }
  to { background-position-x: -288px; }
}

/* ── 雲 ──────────────────────────────────────── */
.cloud {
  position: absolute; height: 12px; border-radius: 999px;
  background: var(--line); opacity: .7;
}
.cloud::after {
  content: ''; position: absolute; top: -7px; left: 22px;
  width: 32px; height: 12px; border-radius: 999px; background: inherit;
}
.c1 { width: 64px; top: 12%; animation: drift 17s linear infinite; }
.c2 { width: 46px; top: 30%; animation: drift 23s linear infinite; animation-delay: -11s; }
.c3 { width: 54px; top: 48%; animation: drift 20s linear infinite; animation-delay: -6s; }
@keyframes drift {
  from { transform: translateX(105vw); }
  to { transform: translateX(-120px); }
}

/* ── 小人 ────────────────────────────────────── */
.runner {
  position: absolute; left: 16%; bottom: calc(var(--ground) - 4px);
  width: 66px; height: 90px;
  will-change: transform;
  z-index: 10;
}
.figure {
  width: 100%; height: 100%; display: block; overflow: visible;
  transform-origin: 50% 100%;
  transition: transform .12s ease;
}

.torso { animation: bob calc(var(--stride) / 2) ease-in-out infinite alternate; }
@keyframes bob { from { transform: translateY(0); } to { transform: translateY(-2.5px); } }

.arm, .thigh, .shin { transform-box: view-box; transition: transform .16s ease; }

.thigh { transform-origin: 27px 42px; }
.t1 { animation: thigh-cycle var(--stride) ease-in-out infinite; }
.t2 { animation: thigh-cycle var(--stride) ease-in-out infinite; animation-delay: calc(var(--stride) / -2); }
@keyframes thigh-cycle {
  0%   { transform: rotate(-34deg); }
  50%  { transform: rotate(36deg); }
  100% { transform: rotate(-34deg); }
}

.s1, .s2 { transform-origin: 33px 55px; }
.s2 { transform-origin: 24px 55px; }
.s1 { animation: shin-cycle var(--stride) ease-in-out infinite; }
.s2 { animation: shin-cycle var(--stride) ease-in-out infinite; animation-delay: calc(var(--stride) / -2); }
@keyframes shin-cycle {
  0%   { transform: rotate(58deg); }
  35%  { transform: rotate(38deg); }
  55%  { transform: rotate(-4deg); }
  75%  { transform: rotate(6deg); }
  100% { transform: rotate(58deg); }
}

.arm { transform-origin: 31px 24px; }
.a1 { animation: arm-cycle var(--stride) ease-in-out infinite; animation-delay: calc(var(--stride) / -2); }
.a2 { animation: arm-cycle var(--stride) ease-in-out infinite; }
@keyframes arm-cycle {
  0%   { transform: rotate(-30deg); }
  50%  { transform: rotate(26deg); }
  100% { transform: rotate(-30deg); }
}

/* 空中：收腿抱膝 */
.runner.air .t1 { animation: none; transform: rotate(48deg); }
.runner.air .s1 { animation: none; transform: rotate(66deg); }
.runner.air .t2 { animation: none; transform: rotate(-14deg); }
.runner.air .s2 { animation: none; transform: rotate(74deg); }
.runner.air .a1 { animation: none; transform: rotate(-46deg); }
.runner.air .a2 { animation: none; transform: rotate(30deg); }
.runner.air .torso { animation: none; }

/* 蹲下：整體壓扁 + 手臂後收 */
.runner.duck .figure { transform: scaleY(.55) scaleX(1.08); }
.runner.duck .a1 { animation: none; transform: rotate(-58deg); }
.runner.duck .a2 { animation: none; transform: rotate(44deg); }

/* 衝線慶祝：雙手高舉 + 小跳 */
.runner.win .t1 { animation: none; transform: rotate(6deg); }
.runner.win .s1 { animation: none; transform: rotate(4deg); }
.runner.win .t2 { animation: none; transform: rotate(-8deg); }
.runner.win .s2 { animation: none; transform: rotate(8deg); }
.runner.win .a1 { animation: none; transform: rotate(-150deg); }
.runner.win .a2 { animation: none; transform: rotate(150deg); }
.runner.win .torso { animation: none; }
.runner.win .figure { animation: win-hop .45s ease-in-out infinite alternate; }
@keyframes win-hop { from { transform: translateY(0); } to { transform: translateY(-10px); } }

.runner.hit { animation: shake .3s ease-in-out 2; }
.runner.hit .figure :is(path, line, circle) { stroke: #a8412c; transition: stroke .1s; }
.runner.hit .figure circle { fill: #a8412c; stroke: none; }
@keyframes shake {
  0%, 100% { margin-left: 0; }
  25% { margin-left: -3px; }
  75% { margin-left: 3px; }
}

.shadow {
  position: absolute; left: 12px; bottom: -7px;
  width: 42px; height: 7px; border-radius: 50%;
  background: rgba(38, 43, 39, .18);
}

/* ── 障礙物 ──────────────────────────────────── */
.cone {
  position: absolute; left: 0; bottom: calc(var(--ground) - 2px);
  width: 34px; will-change: transform; z-index: 8;
}
.cone svg { display: block; width: 100%; transition: rotate .25s ease; }
.cone.tipped svg { rotate: -62deg; translate: -3px 2px; opacity: .75; }

.bird {
  position: absolute; left: 0; bottom: calc(var(--ground) + 54px);
  width: 46px; will-change: transform; z-index: 8;
}
.bird svg { display: block; width: 100%; animation: bird-bob .9s ease-in-out infinite alternate; }
.bird .wing {
  transform-box: view-box; transform-origin: 22px 16px;
  animation: flap .28s ease-in-out infinite alternate;
}
@keyframes flap { from { transform: rotate(-24deg); } to { transform: rotate(30deg); } }
@keyframes bird-bob { from { transform: translateY(-4px); } to { transform: translateY(5px); } }
.bird.down svg { animation: none; rotate: 32deg; opacity: .6; translate: 0 10px; }
.bird.down .wing { animation: none; }

/* ── 平台 ────────────────────────────────────── */
.platform {
  position: absolute; left: 0;
  bottom: calc(var(--ground) + 122px - 16px);   /* 頂面 = 離地 122px */
  height: 16px;
  will-change: transform; z-index: 7;
  pointer-events: none;
}
.deck {
  width: 100%; height: 100%;
  border-radius: 10px;
  background: linear-gradient(var(--green-600) 0 5px, var(--green-800) 5px);
  box-shadow: 0 8px 18px rgba(30, 58, 43, .22);
}
/* 頂面草叢感 */
.deck::before {
  content: ''; position: absolute; left: 6px; right: 6px; top: -4px; height: 5px;
  background: repeating-linear-gradient(90deg,
    var(--green-600) 0 10px, transparent 10px 16px);
  border-radius: 3px; opacity: .85;
}

/* ── 蓄力條 ──────────────────────────────────── */
.chargebar {
  position: absolute; left: 6px; top: -14px;
  width: 54px; height: 6px; border-radius: 999px;
  background: rgba(38, 43, 39, .16);
  overflow: hidden;
}
.chargefill {
  height: 100%; border-radius: 999px;
  background: var(--green-600);
}
.chargefill.full {
  background: #d97b29;
  animation: charge-pulse .3s ease-in-out infinite alternate;
}
@keyframes charge-pulse { from { opacity: .7; } to { opacity: 1; } }

/* ── 終點線 ──────────────────────────────────── */
.finishline {
  position: absolute; left: 0; bottom: calc(var(--ground) - 2px);
  width: 18px; height: 150px;
  will-change: transform; z-index: 9;
}
.pole {
  position: absolute; left: 0; bottom: 0;
  width: 5px; height: 150px; border-radius: 3px;
  background: var(--green-900);
}
.flag {
  position: absolute; left: 5px; top: 0;
  width: 52px; height: 34px;
  background: repeating-conic-gradient(var(--green-900) 0% 25%, #fdfcf8 0% 50%);
  background-size: 12px 12px;
  border-radius: 0 6px 6px 0;
  box-shadow: 0 3px 10px rgba(30, 58, 43, .2);
}
.fintext {
  position: absolute; left: 0; top: -26px;
  font-size: 12px; font-weight: 800; letter-spacing: .14em;
  color: var(--green-800);
}

/* ── 操作提示 ────────────────────────────────── */
.tip {
  position: absolute; right: 20px; bottom: 14px; z-index: 30;
  margin: 0; font-size: 12px; color: var(--muted);
}
.tip kbd {
  font-family: inherit; font-size: 11px;
  background: var(--surface); border: 1px solid var(--line);
  border-bottom-width: 2px; border-radius: 6px; padding: 1px 6px;
}

@media (prefers-reduced-motion: reduce) {
  .arm, .thigh, .shin, .torso, .road, .cloud, .forest, .bird svg, .wing, .figure { animation: none; }
}
</style>
