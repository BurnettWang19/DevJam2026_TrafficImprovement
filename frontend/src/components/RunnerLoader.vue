<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'

/* 分析等待中的互動小遊戲：小人自動奔跑，按空白鍵跳過三角錐。
   撞到只會踉蹌一下，不會結束——它終究只是個 loading 畫面。 */

const sceneEl = ref(null)

const RUNNER_X_RATIO = 0.18   // 小人固定在畫面 18% 處
const RUNNER_W = 30           // 碰撞盒寬
const GRAVITY = 1400          // px/s²
const JUMP_V = 430            // 起跳初速 px/s
const CONE_SPEED = 175        // px/s
const CONE_W = 24
const CONE_H = 30

const y = ref(0)              // 離地高度
const airborne = ref(false)
const stumbling = ref(false)
const cleared = ref(0)
const cones = reactive([])

let vy = 0
let raf = 0
let last = 0
let spawnAt = 0
let coneId = 0
let stumbleTimer = 0

function jump() {
  if (!airborne.value && !stumbling.value) {
    airborne.value = true
    vy = JUMP_V
  }
}

function onKey(e) {
  if (e.code === 'Space' || e.code === 'ArrowUp') {
    e.preventDefault()
    jump()
  }
}

function step(now) {
  const dt = Math.min((now - last) / 1000, 0.05)
  last = now
  const w = sceneEl.value?.offsetWidth || 360
  const runnerX = w * RUNNER_X_RATIO

  /* 跳躍物理 */
  if (airborne.value) {
    vy -= GRAVITY * dt
    y.value += vy * dt
    if (y.value <= 0) {
      y.value = 0
      vy = 0
      airborne.value = false
    }
  }

  /* 生成三角錐：間隔帶隨機，避免連續到跳不過 */
  if (now >= spawnAt) {
    cones.push({ id: coneId++, x: w + 20, hit: false, scored: false })
    spawnAt = now + 1300 + Math.random() * 1200
  }

  /* 移動與判定 */
  for (let i = cones.length - 1; i >= 0; i--) {
    const c = cones[i]
    c.x -= CONE_SPEED * dt

    const overlap = c.x < runnerX + RUNNER_W && c.x + CONE_W > runnerX + 4
    if (overlap && y.value < CONE_H - 6 && !c.hit && !stumbling.value) {
      c.hit = true
      stumbling.value = true
      clearTimeout(stumbleTimer)
      stumbleTimer = setTimeout(() => { stumbling.value = false }, 650)
    }
    if (!c.scored && !c.hit && c.x + CONE_W < runnerX) {
      c.scored = true
      cleared.value++
    }
    if (c.x < -40) cones.splice(i, 1)
  }

  raf = requestAnimationFrame(step)
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  last = performance.now()
  spawnAt = last + 900
  raf = requestAnimationFrame(step)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  cancelAnimationFrame(raf)
  clearTimeout(stumbleTimer)
})
</script>

<template>
  <div class="wrap">
    <div ref="sceneEl" class="scene" @pointerdown="jump">
      <div class="cloud c1"></div>
      <div class="cloud c2"></div>

      <div class="score mono" v-if="cleared">越過 {{ cleared }}</div>

      <div class="runner"
           :class="{ air: airborne, hit: stumbling }"
           :style="{ transform: `translateY(${-y}px)` }">
        <svg viewBox="0 0 60 80" class="figure">
          <!-- 後臂（身體後面，先畫） -->
          <g class="arm a2">
            <path d="M31 24 L24 32 L27 39" stroke="var(--green-700)" stroke-width="4.5"
                  stroke-linecap="round" stroke-linejoin="round" fill="none" />
          </g>
          <!-- 後腿：大腿 + 小腿分開關節 -->
          <g class="thigh t2">
            <line x1="27" y1="42" x2="24" y2="55" stroke="var(--green-700)" stroke-width="5" stroke-linecap="round" />
            <g class="shin s2">
              <line x1="24" y1="55" x2="22" y2="68" stroke="var(--green-700)" stroke-width="5" stroke-linecap="round" />
              <line x1="22" y1="68" x2="28" y2="70" stroke="var(--green-700)" stroke-width="4" stroke-linecap="round" />
            </g>
          </g>
          <!-- 身體與頭 -->
          <g class="torso">
            <path d="M33 18 L27 42" stroke="var(--green-900)" stroke-width="5.5" stroke-linecap="round" fill="none" />
            <circle cx="35" cy="11" r="7" fill="var(--green-900)" />
          </g>
          <!-- 前腿 -->
          <g class="thigh t1">
            <line x1="27" y1="42" x2="33" y2="55" stroke="var(--green-900)" stroke-width="5" stroke-linecap="round" />
            <g class="shin s1">
              <line x1="33" y1="55" x2="32" y2="69" stroke="var(--green-900)" stroke-width="5" stroke-linecap="round" />
              <line x1="32" y1="69" x2="38" y2="70.5" stroke="var(--green-900)" stroke-width="4" stroke-linecap="round" />
            </g>
          </g>
          <!-- 前臂（身體前面，最後畫） -->
          <g class="arm a1">
            <path d="M31 24 L39 31 L36 38" stroke="var(--green-900)" stroke-width="4.5"
                  stroke-linecap="round" stroke-linejoin="round" fill="none" />
          </g>
        </svg>
        <div class="shadow" :style="{ transform: `translateY(${y}px) scaleX(${1 - Math.min(y / 90, 0.5)})`,
                                      opacity: 1 - Math.min(y / 110, 0.6) }"></div>
      </div>

      <div v-for="c in cones" :key="c.id" class="cone" :class="{ tipped: c.hit }"
           :style="{ transform: `translateX(${c.x}px)` }">
        <svg viewBox="0 0 40 36">
          <path d="M20 3 L30 30 L10 30 Z" fill="#d97b29" />
          <path d="M16.4 13 L23.6 13 L25.6 19 L14.4 19 Z" fill="#fdf6ec" />
          <rect x="4" y="29" width="32" height="5" rx="2.5" fill="#b8621c" />
        </svg>
      </div>

      <div class="road"></div>
    </div>
    <p class="tip">按 <kbd>Space</kbd> 或點擊畫面，幫小人跳過三角錐</p>
  </div>
</template>

<style scoped>
.wrap { display: flex; flex-direction: column; align-items: flex-start; }

.scene {
  --stride: .52s;               /* 一個完整跑步循環 */
  position: relative;
  width: min(400px, 100%);
  height: 138px;
  overflow: hidden;
  margin-bottom: 4px;
  cursor: pointer;
  touch-action: manipulation;
  user-select: none;
}

.tip { margin: 0 0 12px; font-size: 12.5px; color: var(--muted); }
.tip kbd {
  font-family: inherit; font-size: 11.5px;
  background: var(--surface); border: 1px solid var(--line);
  border-bottom-width: 2px; border-radius: 6px; padding: 1px 7px;
}

.score {
  position: absolute; top: 6px; right: 10px;
  font-size: 12.5px; color: var(--green-700); font-weight: 600;
}

/* ── 路面 ─────────────────────────────────────────────── */
.road {
  position: absolute; left: 0; right: 0; bottom: 10px; height: 3px;
  background: repeating-linear-gradient(90deg,
    var(--green-700) 0 22px, transparent 22px 40px);
  border-radius: 2px;
  opacity: .55;
  animation: road-flow 1.4s linear infinite;
}
@keyframes road-flow {
  from { background-position-x: 0; }
  to { background-position-x: -240px; }
}

/* ── 雲 ──────────────────────────────────────────────── */
.cloud {
  position: absolute; height: 10px; border-radius: 999px;
  background: var(--line); opacity: .8;
}
.cloud::after {
  content: ''; position: absolute; top: -6px; left: 18px;
  width: 26px; height: 10px; border-radius: 999px; background: inherit;
}
.c1 { width: 52px; top: 16px; animation: drift 8s linear infinite; }
.c2 { width: 38px; top: 40px; animation: drift 11s linear infinite; animation-delay: -5s; }
@keyframes drift {
  from { transform: translateX(420px); }
  to { transform: translateX(-90px); }
}

/* ── 小人 ─────────────────────────────────────────────── */
.runner {
  position: absolute; left: 18%; bottom: 8px;
  width: 52px; height: 72px;
  will-change: transform;
}
.figure { width: 100%; height: 100%; display: block; overflow: visible; }

/* 跑步顛動：每步落地彈一下（一循環兩步 → 頻率加倍） */
.torso { animation: bob calc(var(--stride) / 2) ease-in-out infinite alternate; }
@keyframes bob { from { transform: translateY(0); } to { transform: translateY(-2.5px); } }

/* 關節：全部同一循環長度，靠 delay 對相位 —— 左右互為半拍 */
.arm, .thigh, .shin { transform-box: view-box; transition: transform .16s ease; }

.thigh { transform-origin: 27px 42px; }
.t1 { animation: thigh-cycle var(--stride) ease-in-out infinite; }
.t2 { animation: thigh-cycle var(--stride) ease-in-out infinite; animation-delay: calc(var(--stride) / -2); }
@keyframes thigh-cycle {
  0%   { transform: rotate(-34deg); }   /* 腿在後 */
  50%  { transform: rotate(36deg); }    /* 抬到前 */
  100% { transform: rotate(-34deg); }
}

/* 小腿：後擺時收起、著地前伸直，相位跟著同側大腿 */
.s1, .s2 { transform-origin: 33px 55px; }
.s2 { transform-origin: 24px 55px; }
.s1 { animation: shin-cycle var(--stride) ease-in-out infinite; }
.s2 { animation: shin-cycle var(--stride) ease-in-out infinite; animation-delay: calc(var(--stride) / -2); }
@keyframes shin-cycle {
  0%   { transform: rotate(58deg); }    /* 後擺收腿 */
  35%  { transform: rotate(38deg); }
  55%  { transform: rotate(-4deg); }    /* 前伸準備著地 */
  75%  { transform: rotate(6deg); }
  100% { transform: rotate(58deg); }
}

/* 手臂與對側腿同步（前腿在前時，前臂在後） */
.arm { transform-origin: 31px 24px; }
.a1 { animation: arm-cycle var(--stride) ease-in-out infinite; animation-delay: calc(var(--stride) / -2); }
.a2 { animation: arm-cycle var(--stride) ease-in-out infinite; }
@keyframes arm-cycle {
  0%   { transform: rotate(-30deg); }
  50%  { transform: rotate(26deg); }
  100% { transform: rotate(-30deg); }
}

/* 空中姿勢：停掉跑步循環，收腿抱膝、手臂上揚 */
.runner.air .t1 { animation: none; transform: rotate(48deg); }
.runner.air .s1 { animation: none; transform: rotate(66deg); }
.runner.air .t2 { animation: none; transform: rotate(-14deg); }
.runner.air .s2 { animation: none; transform: rotate(74deg); }
.runner.air .a1 { animation: none; transform: rotate(-46deg); }
.runner.air .a2 { animation: none; transform: rotate(30deg); }
.runner.air .torso { animation: none; }

/* 踉蹌：閃紅 + 抖動 */
.runner.hit { animation: shake .3s ease-in-out 2; }
.runner.hit .figure :is(path, line, circle) {
  stroke: #a8412c; transition: stroke .1s;
}
.runner.hit .figure circle { fill: #a8412c; stroke: none; }
@keyframes shake {
  0%, 100% { margin-left: 0; }
  25% { margin-left: -3px; }
  75% { margin-left: 3px; }
}

.shadow {
  position: absolute; left: 8px; bottom: -7px;
  width: 36px; height: 6px; border-radius: 50%;
  background: rgba(38, 43, 39, .18);
}

/* ── 三角錐 ───────────────────────────────────────────── */
.cone {
  position: absolute; left: 0; bottom: 11px; width: 26px;
  will-change: transform;
}
.cone svg { display: block; width: 100%; transition: rotate .25s ease; }
.cone.tipped svg { rotate: -62deg; translate: -3px 2px; opacity: .75; }

@media (prefers-reduced-motion: reduce) {
  .arm, .thigh, .shin, .torso, .road, .cloud { animation: none; }
}
</style>
