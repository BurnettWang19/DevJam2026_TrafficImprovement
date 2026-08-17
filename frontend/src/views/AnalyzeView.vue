<template>
  <section class="workspace">
    <IntersectionMap />
    <aside class="side-panel">
      <MapControls />
      <CriteriaPanel />
      <ScorePanel />
    </aside>
  </section>
</template>

<script setup lang="ts">
import CriteriaPanel from '../components/analysis/CriteriaPanel.vue'
import ScorePanel from '../components/analysis/ScorePanel.vue'
import IntersectionMap from '../components/map/IntersectionMap.vue'
import MapControls from '../components/map/MapControls.vue'
</script>
