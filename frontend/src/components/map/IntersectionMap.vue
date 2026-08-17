<template>
  <div class="map-frame">
    <div ref="mapContainer" class="map-container" />
    <GeoJsonLayer v-if="mapInstance" :map="mapInstance" :geojson="store.geojson" />
  </div>
</template>

<script setup lang="ts">
import maplibregl, { Marker } from 'maplibre-gl'
import type { Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl'
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'

import { useIntersectionStore } from '../../stores/intersection'
import GeoJsonLayer from './GeoJsonLayer.vue'

const store = useIntersectionStore()
const mapContainer = ref<HTMLDivElement | null>(null)
const mapInstance = shallowRef<MapLibreMap | null>(null)
let marker: Marker | null = null

const selectionSourceId = 'selection-radius'
const selectionFillId = 'selection-radius-fill'
const selectionLineId = 'selection-radius-line'

function createSelectionSquare(longitude: number, latitude: number, sideLengthMeters: number) {
  const halfSide = sideLengthMeters / 2
  const latitudeDelta = halfSide / 111_320
  const longitudeDelta = halfSide / (111_320 * Math.cos((latitude * Math.PI) / 180))
  const coordinates = [
    [longitude - longitudeDelta, latitude - latitudeDelta],
    [longitude + longitudeDelta, latitude - latitudeDelta],
    [longitude + longitudeDelta, latitude + latitudeDelta],
    [longitude - longitudeDelta, latitude + latitudeDelta],
    [longitude - longitudeDelta, latitude - latitudeDelta]
  ]

  return {
    type: 'Feature' as const,
    properties: {},
    geometry: { type: 'Polygon' as const, coordinates: [coordinates] }
  }
}

function updateSelectionVisual() {
  const map = mapInstance.value
  const location = store.selectedLocation
  if (!map || !map.isStyleLoaded()) return

  if (!location) {
    marker?.remove()
    marker = null
    const source = map.getSource(selectionSourceId) as maplibregl.GeoJSONSource | undefined
    source?.setData({ type: 'FeatureCollection', features: [] })
    return
  }

  if (!marker) {
    const element = document.createElement('div')
    element.className = 'intersection-marker'
    element.setAttribute('aria-label', '所選路口中心點')
    marker = new maplibregl.Marker({ element, anchor: 'bottom' })
      .setLngLat([location.longitude, location.latitude])
      .addTo(map)
  } else {
    marker.setLngLat([location.longitude, location.latitude])
  }

  const source = map.getSource(selectionSourceId) as maplibregl.GeoJSONSource | undefined
  source?.setData(createSelectionSquare(location.longitude, location.latitude, store.radiusMeters))
}

onMounted(() => {
  if (!mapContainer.value) {
    return
  }

  mapInstance.value = new maplibregl.Map({
    container: mapContainer.value,
    style: {
      version: 8,
      sources: {
        osm: {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '© OpenStreetMap contributors'
        }
      },
      layers: [{ id: 'osm', type: 'raster', source: 'osm' }]
    },
    center: [121.5654, 25.033],
    zoom: 16
  })

  mapInstance.value.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')

  mapInstance.value.on('load', () => {
    const map = mapInstance.value
    if (!map) return

    map.addSource(selectionSourceId, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    })
    map.addLayer({
      id: selectionFillId,
      type: 'fill',
      source: selectionSourceId,
      paint: { 'fill-color': '#819871', 'fill-opacity': 0.16 }
    })
    map.addLayer({
      id: selectionLineId,
      type: 'line',
      source: selectionSourceId,
      paint: { 'line-color': '#526a47', 'line-width': 2 }
    })
    updateSelectionVisual()
  })

  mapInstance.value.on('click', (event: MapMouseEvent) => {
    const location = {
      latitude: Number(event.lngLat.lat.toFixed(6)),
      longitude: Number(event.lngLat.lng.toFixed(6))
    }
    store.selectLocation(location)
  })
})

watch(
  () => [store.selectedLocation?.latitude, store.selectedLocation?.longitude, store.radiusMeters],
  updateSelectionVisual
)

onBeforeUnmount(() => {
  marker?.remove()
  mapInstance.value?.remove()
})
</script>
