<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

/* 進入視野時從 0 滾動到目標值 */
const props = defineProps({
  value: { type: Number, required: true },
  prefix: { type: String, default: '' },
  duration: { type: Number, default: 1300 },
})

const el = ref(null)
const shown = ref(0)
let io, raf

function run() {
  const t0 = performance.now()
  const tick = (now) => {
    const t = Math.min((now - t0) / props.duration, 1)
    const eased = 1 - Math.pow(1 - t, 3)
    shown.value = Math.round(props.value * eased)
    if (t < 1) raf = requestAnimationFrame(tick)
  }
  raf = requestAnimationFrame(tick)
}

onMounted(() => {
  io = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting)) {
      io.disconnect()
      run()
    }
  }, { threshold: .4 })
  io.observe(el.value)
})

onBeforeUnmount(() => { io?.disconnect(); cancelAnimationFrame(raf) })
</script>

<template>
  <span ref="el" class="mono">{{ prefix }}{{ shown.toLocaleString('en-US') }}</span>
</template>
