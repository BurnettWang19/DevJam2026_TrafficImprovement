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
        <div class="detail">{{ t.detail }}</div>
      </div>
    </li>
  </ol>
</template>

<style scoped>
.trace { list-style: none; margin: 0; padding: 0; }
.trace li { display: flex; gap: 10px; padding: 6px 0; align-items: flex-start; }
.dot {
  flex: none; width: 20px; height: 20px; border-radius: 50%;
  display: grid; place-items: center; font-size: 11px; margin-top: 3px;
  background: #ddd9cd; color: var(--text-2);
}
li.done .dot { background: var(--sev-low-bg); color: var(--green-600); }
li.running .dot { background: #dde7ef; color: #3d6d8f; }
li.failed .dot { background: var(--sev-crit-bg); color: var(--sev-crit-fg); }
li.warning .dot { background: var(--sev-high-bg); color: var(--sev-high-fg); }
.body { flex: 1; min-width: 0; }
.head { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
.head strong { font-size: 13.5px; color: var(--text); }
.ms { font-size: 11px; color: var(--muted); }
.detail { font-size: 12.5px; color: var(--text-2); word-break: break-word; line-height: 1.6; }
</style>
