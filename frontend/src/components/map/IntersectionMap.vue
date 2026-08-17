<template>
  <div class="map-frame">
    <div ref="mapContainer" class="map-container" />
    <GeoJsonLayer v-if="mapInstance" :map="mapInstance" :geojson="store.geojson" />
  </div>
</template>

<script setup lang="ts">
import maplibregl, { Marker } from 'maplibre-gl'
import type { Map, MapMouseEvent } from 'maplibre-gl'
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'

import { useIntersectionStore } from '../../stores/intersection'
import GeoJsonLayer from './GeoJsonLayer.vue'

const store = useIntersectionStore()
const mapContainer = ref<HTMLDivElement | null>(null)
const mapInstance = shallowRef<Map | null>(null)
let marker: Marker | null = null

onMounted(() => {
  if (!mapContainer.value) {
    return
  }

  mapInstance.value = new maplibregl.Map({
    container: mapContainer.value,
    style: 'https://demotiles.maplibre.org/style.json',
    center: [121.5654, 25.033],
    zoom: 16
  })

  mapInstance.value.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right')

  mapInstance.value.on('click', (event: MapMouseEvent) => {
    const location = {
      latitude: Number(event.lngLat.lat.toFixed(6)),
      longitude: Number(event.lngLat.lng.toFixed(6))
    }
    store.selectLocation(location)

    if (!marker) {
      marker = new maplibregl.Marker({ color: '#ef4444' })
        .setLngLat([location.longitude, location.latitude])
        .addTo(mapInstance.value as Map)
      return
    }

    marker.setLngLat([location.longitude, location.latitude])
  })
})

onBeforeUnmount(() => {
  marker?.remove()
  mapInstance.value?.remove()
})
</script>
