<script setup>
defineProps({ trace: { type: Array, default: () => [] } })

const ICON = { running: '◐', done: '✓', failed: '✕', warning: '!' }
</script>

<template>
  <ol class="trace">
    <li v-for="(t, i) in trace" :key="i" :class="t.status">
      <span class="dot">{{ ICON[t.status] || '·' }}</span>
      <div class="body">
        <div class="head">
          <strong>{{ t.step }}</strong>
          <span class="ms mono">{{ t.at_ms }}ms</span>
        </div>
        <div class="detail muted">{{ t.detail }}</div>
      </div>
    </li>
  </ol>
</template>

<style scoped>
.trace { list-style: none; margin: 0; padding: 0; }
.trace li { display: flex; gap: 10px; padding: 6px 0; align-items: flex-start; }
.dot {
  flex: none; width: 20px; height: 20px; border-radius: 50%;
  display: grid; place-items: center; font-size: 11px;
  background: #232c3c; color: var(--muted); margin-top: 2px;
}
li.done .dot { background: #1d4633; color: var(--accent); }
li.running .dot { background: #1e3a4d; color: var(--accent-2); }
li.failed .dot { background: #4a1f22; color: var(--bad); }
li.warning .dot { background: #4a3c14; color: var(--warn); }
.body { flex: 1; min-width: 0; }
.head { display: flex; justify-content: space-between; gap: 8px; }
.ms { font-size: 11px; color: #5f6b7f; }
.detail { font-size: 12.5px; word-break: break-word; }
</style>
