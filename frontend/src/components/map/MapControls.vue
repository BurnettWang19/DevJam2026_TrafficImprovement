<template>
  <section class="panel-section">
    <div class="section-header">
      <h2>Selection</h2>
      <span class="status-pill" :data-status="store.analysisStatus">{{ store.analysisStatus }}</span>
    </div>

    <dl class="coordinate-list">
      <div>
        <dt>Latitude</dt>
        <dd>{{ store.selectedLocation?.latitude ?? 'None' }}</dd>
      </div>
      <div>
        <dt>Longitude</dt>
        <dd>{{ store.selectedLocation?.longitude ?? 'None' }}</dd>
      </div>
    </dl>

    <label class="field">
      <span>Radius meters</span>
      <input v-model.number="store.radiusMeters" type="number" min="10" max="500" step="10" />
    </label>

    <button
      class="primary-button"
      type="button"
      :disabled="!store.selectedLocation || store.loading"
      @click="store.analyzeSelectedLocation"
    >
      {{ store.loading ? 'Loading geometry...' : 'Analyze Intersection' }}
    </button>

    <p v-if="store.error" class="error-message">
      {{ store.errorCode }}: {{ store.error }}
    </p>
  </section>
</template>

<script setup lang="ts">
import { useIntersectionStore } from '../../stores/intersection'

const store = useIntersectionStore()
</script>
