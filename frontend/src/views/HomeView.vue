<template>
  <main class="app-shell">
    <header class="top-bar">
      <div>
        <p class="eyebrow">Road Intersection AI</p>
        <h1>Intersection geometry loader</h1>
      </div>
      <RouterLink class="nav-link" to="/analyze">Analyze</RouterLink>
    </header>
    <AnalyzeView />
  </main>
</template>

<script setup lang="ts">
import AnalyzeView from './AnalyzeView.vue'
</script>
