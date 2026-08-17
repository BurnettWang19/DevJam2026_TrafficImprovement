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
let ro = null

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

/* 脈衝標記：divIcon + CSS 動畫，比純色圓點有存在感 */
const pulseIcon = L.divIcon({
  className: 'pick-marker',
  html: '<span class="ring"></span><span class="dot"></span>',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
})

onMounted(() => {
  map = L.map(el.value, { zoomControl: true }).setView([props.lat, props.lng], 18)

  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 20,
    attribution: '© OpenStreetMap contributors',
  }).addTo(map)

  marker = L.marker([props.lat, props.lng], {
    icon: pulseIcon, interactive: false, keyboard: false,
  }).addTo(map)

  rect = L.rectangle(bounds(), {
    className: 'range-box',
    color: '#2f5d45', weight: 2, fillOpacity: 0.07, dashArray: '8 6',
  }).addTo(map)

  map.on('click', (e) => {
    emit('pick', e.latlng.lat, e.latlng.lng)
    // 點到哪就平滑滑過去，讓選取框回到畫面中心
    map.panTo(e.latlng, { animate: true, duration: .6, easeLinearity: .3 })
  })

  // 側欄收合會改變容器寬度，Leaflet 只監聽 window resize，這裡自己補
  ro = new ResizeObserver(() => map && map.invalidateSize())
  ro.observe(el.value)
})

onBeforeUnmount(() => {
  ro && ro.disconnect()
  map && map.remove()
})

watch(() => [props.lat, props.lng, props.sizeM], redraw)

defineExpose({
  flyTo(lat, lng) {
    if (!map) return
    const target = L.latLng(lat, lng)
    const far = map.getCenter().distanceTo(target) > 3000
    // 遠距離：先拉高再俯衝的飛行運鏡；近距離：平滑短飛
    map.flyTo(target, Math.max(map.getZoom(), 18), {
      animate: true,
      duration: far ? 2.4 : 1.1,
      easeLinearity: .18,
    })
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

/* ── 脈衝標記 ─────────────────────────────────── */
:deep(.pick-marker) { position: relative; }
:deep(.pick-marker .dot) {
  position: absolute; inset: 4px;
  border-radius: 50%;
  background: #2f5d45;
  border: 2px solid #1e3a2b;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, .9);
}
:deep(.pick-marker .ring) {
  position: absolute; inset: 0;
  border-radius: 50%;
  border: 2px solid #2f5d45;
  animation: pick-pulse 1.8s ease-out infinite;
}
@keyframes pick-pulse {
  0%   { transform: scale(.8); opacity: .9; }
  70%  { transform: scale(2.6); opacity: 0; }
  100% { transform: scale(2.6); opacity: 0; }
}

/* ── 範圍框跑馬燈（marching ants） ────────────── */
:deep(.range-box) {
  animation: ants 1.2s linear infinite;
}
@keyframes ants {
  from { stroke-dashoffset: 0; }
  to { stroke-dashoffset: -28; }
}

@media (prefers-reduced-motion: reduce) {
  :deep(.pick-marker .ring), :deep(.range-box) { animation: none; }
}
</style>
