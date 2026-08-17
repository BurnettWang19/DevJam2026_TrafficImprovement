<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import L from 'leaflet'

const props = defineProps({
  lat: { type: Number, required: true },
  lng: { type: Number, required: true },
  sizeM: { type: Number, required: true },
})
const emit = defineEmits(['pick'])

const el = ref(null)
let map = null
let marker = null
let rect = null

function bounds() {
  const half = props.sizeM / 2
  const dLat = half / 111320
  const dLng = half / (111320 * Math.cos((props.lat * Math.PI) / 180))
  return [
    [props.lat - dLat, props.lng - dLng],
    [props.lat + dLat, props.lng + dLng],
  ]
}

function redraw() {
  if (!map) return
  const pos = [props.lat, props.lng]
  marker.setLatLng(pos)
  rect.setBounds(bounds())
}

onMounted(() => {
  map = L.map(el.value, { zoomControl: true }).setView([props.lat, props.lng], 18)

  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 20,
    attribution: '© OpenStreetMap contributors',
  }).addTo(map)

  marker = L.circleMarker([props.lat, props.lng], {
    radius: 6, color: '#1e3a2b', fillColor: '#2f5d45', fillOpacity: 1, weight: 2,
  }).addTo(map)

  rect = L.rectangle(bounds(), {
    color: '#2f5d45', weight: 2, fillOpacity: 0.07, dashArray: '6 4',
  }).addTo(map)

  map.on('click', (e) => emit('pick', e.latlng.lat, e.latlng.lng))
})

onBeforeUnmount(() => map && map.remove())

watch(() => [props.lat, props.lng, props.sizeM], redraw)

defineExpose({
  flyTo(lat, lng) {
    if (map) map.setView([lat, lng], Math.max(map.getZoom(), 18))
  },
})
</script>

<template>
  <div ref="el" class="map"></div>
</template>

<style scoped>
.map {
  height: 100%;
  min-height: 320px;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--line);
}
:deep(.leaflet-container) { background: var(--bg-sunken); font: inherit; }
:deep(.leaflet-control-attribution) { font-size: 10px; }
</style>
