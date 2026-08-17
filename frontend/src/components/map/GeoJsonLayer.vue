<template></template>

<script setup lang="ts">
import type { GeoJSONSource, Map } from 'maplibre-gl'
import { watch } from 'vue'

import type { FeatureCollection } from '../../types/geojson'

const sourceId = 'intersection-roads'
const casingLayerId = 'intersection-roads-casing'
const lineLayerId = 'intersection-roads-line'

const props = defineProps<{
  map: Map
  geojson: FeatureCollection | null
}>()

function ensureLayers() {
  if (!props.map.getSource(sourceId)) {
    props.map.addSource(sourceId, {
      type: 'geojson',
      data: props.geojson ?? { type: 'FeatureCollection', features: [] }
    })
  }

  if (!props.map.getLayer(casingLayerId)) {
    props.map.addLayer({
      id: casingLayerId,
      type: 'line',
      source: sourceId,
      paint: {
        'line-color': '#0f172a',
        'line-width': 8,
        'line-opacity': 0.7
      }
    })
  }

  if (!props.map.getLayer(lineLayerId)) {
    props.map.addLayer({
      id: lineLayerId,
      type: 'line',
      source: sourceId,
      paint: {
        'line-color': '#38bdf8',
        'line-width': 4,
        'line-opacity': 0.95
      }
    })
  }
}

function updateData(geojson: FeatureCollection | null) {
  if (!props.map.isStyleLoaded()) {
    props.map.once('load', () => updateData(geojson))
    return
  }

  ensureLayers()
  const source = props.map.getSource(sourceId) as GeoJSONSource
  source.setData(geojson ?? { type: 'FeatureCollection', features: [] })
}

watch(() => props.geojson, updateData, { immediate: true })
</script>
