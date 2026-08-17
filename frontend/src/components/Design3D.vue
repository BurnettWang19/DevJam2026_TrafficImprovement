<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  BoundingSphere,
  Cartesian3,
  Cesium3DTileset,
  Color,
  HeadingPitchRange,
  Math as CesiumMath,
  RequestScheduler,
  Viewer,
} from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'
import { apiGet } from '../api'
import { addRoadDesignOverlay } from './design3d/roadOverlay'

const props = defineProps({
  geojson: { type: Object, required: true },
  bbox: { type: Object, required: true },
})

const host = ref(null)
const loading = ref(true)
const ready = ref(false)
const error = ref('')
const rotating = ref(false)
const entityCount = ref(0)

const statusLabel = computed(() => {
  if (error.value) return '3D 城市載入失敗'
  if (ready.value) return `真實城市模型 · ${entityCount.value} 個設計物件`
  return '載入真實城市模型'
})

let viewer
let tileset
let target
let viewRange = 260
let orbitHeading = CesiumMath.toRadians(18)
let orbitFrame
let orbitLastTime = 0
let resizeObserver
let disposed = false
let canvas

function validatedBounds() {
  const south = Number(props.bbox?.south)
  const west = Number(props.bbox?.west)
  const north = Number(props.bbox?.north)
  const east = Number(props.bbox?.east)
  if (![south, west, north, east].every(Number.isFinite)
      || south < -90 || north > 90 || west < -180 || east > 180
      || south >= north || west >= east) {
    throw new Error('INVALID_BOUNDS')
  }
  return { south, west, north, east }
}

function cameraView() {
  return new HeadingPitchRange(
    orbitHeading,
    CesiumMath.toRadians(-48),
    viewRange,
  )
}

function setCameraImmediate() {
  if (!viewer || viewer.isDestroyed() || !target) return
  viewer.camera.lookAt(target, cameraView())
  viewer.scene.requestRender()
}

function resetCamera() {
  if (!viewer || viewer.isDestroyed() || !target) return
  stopOrbit()
  orbitHeading = CesiumMath.toRadians(18)
  viewer.camera.flyToBoundingSphere(new BoundingSphere(target, 1), {
    duration: 0.8,
    offset: cameraView(),
    complete: () => {
      if (!viewer || viewer.isDestroyed()) return
      // Keep the local intersection frame so Cesium's controls orbit this site.
      viewer.camera.lookAt(target, cameraView())
      viewer.scene.requestRender()
    },
  })
}

function orbitTick(timestamp) {
  orbitFrame = undefined
  if (!rotating.value || !viewer || viewer.isDestroyed() || !target) return
  const elapsed = orbitLastTime ? Math.min(timestamp - orbitLastTime, 50) : 16
  orbitLastTime = timestamp
  orbitHeading = (orbitHeading + elapsed * 0.000035) % (Math.PI * 2)
  viewer.camera.lookAt(target, cameraView())
  viewer.scene.requestRender()
  orbitFrame = requestAnimationFrame(orbitTick)
}

function startOrbit() {
  if (!ready.value || rotating.value) return
  rotating.value = true
  orbitLastTime = 0
  if (orbitFrame === undefined) orbitFrame = requestAnimationFrame(orbitTick)
}

function stopOrbit() {
  rotating.value = false
  orbitLastTime = 0
  if (orbitFrame !== undefined) {
    cancelAnimationFrame(orbitFrame)
    orbitFrame = undefined
  }
}

function toggleOrbit() {
  if (rotating.value) stopOrbit()
  else startOrbit()
}

function validateTilesetUrl(value) {
  let parsed
  try {
    parsed = new URL(value)
  } catch {
    throw new Error('INVALID_TILESET_URL')
  }
  if (parsed.protocol !== 'https:'
      || parsed.hostname !== 'tile.googleapis.com'
      || parsed.pathname !== '/v1/3dtiles/root.json'
      || !parsed.searchParams.get('key')) {
    throw new Error('INVALID_TILESET_URL')
  }
  return parsed.toString()
}

function configureScene(bounds) {
  const centerLat = (bounds.south + bounds.north) / 2
  const centerLng = (bounds.west + bounds.east) / 2
  const northSouthMetres = (bounds.north - bounds.south) * 111_320
  const eastWestMetres = (bounds.east - bounds.west)
    * 111_320
    * Math.cos(centerLat * Math.PI / 180)
  const spanMetres = Math.max(northSouthMetres, eastWestMetres)
  viewRange = Math.max(170, Math.min(900, spanMetres * 2.35))
  target = Cartesian3.fromDegrees(centerLng, centerLat, 0)

  viewer.scene.backgroundColor = Color.fromCssColorString('#d7dfe2')
  viewer.scene.fog.enabled = false
  viewer.scene.screenSpaceCameraController.minimumZoomDistance = 18
  viewer.scene.screenSpaceCameraController.maximumZoomDistance = 3_000
  setCameraImmediate()
}

async function initialize() {
  try {
    const bounds = validatedBounds()
    viewer = new Viewer(host.value, {
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      baseLayer: false,
      globe: false,
      skyAtmosphere: false,
      skyBox: false,
      scene3DOnly: true,
      requestRenderMode: true,
      maximumRenderTimeChange: Infinity,
      showRenderLoopErrors: false,
    })
    configureScene(bounds)

    canvas = viewer.canvas
    canvas.addEventListener('pointerdown', stopOrbit)
    canvas.addEventListener('wheel', stopOrbit, { passive: true })

    RequestScheduler.requestsByServer['tile.googleapis.com:443'] = 18
    const config = await apiGet('/api/map-tiles/config')
    const tilesetUrl = validateTilesetUrl(config?.tileset_url)
    const loadedTileset = await Cesium3DTileset.fromUrl(tilesetUrl, {
      showCreditsOnScreen: true,
      maximumScreenSpaceError: 8,
    })
    if (disposed || !viewer || viewer.isDestroyed()) {
      loadedTileset.destroy()
      return
    }

    tileset = loadedTileset
    viewer.scene.primitives.add(tileset)
    const overlay = addRoadDesignOverlay(viewer, props.geojson)
    entityCount.value = overlay.entityCount
    ready.value = true
    loading.value = false
    viewer.scene.requestRender()

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!reduceMotion) startOrbit()
  } catch {
    if (disposed) return
    loading.value = false
    ready.value = false
    error.value = '無法載入真實 3D 城市。請確認 Map Tiles API、帳單與 GOOGLE_MAP_TILES_API_KEY 設定。'
  }
}

onMounted(() => {
  resizeObserver = new ResizeObserver(() => {
    if (!viewer || viewer.isDestroyed()) return
    viewer.resize()
    viewer.scene.requestRender()
  })
  resizeObserver.observe(host.value)
  initialize()
})

onBeforeUnmount(() => {
  disposed = true
  stopOrbit()
  resizeObserver?.disconnect()
  canvas?.removeEventListener('pointerdown', stopOrbit)
  canvas?.removeEventListener('wheel', stopOrbit)
  if (viewer && !viewer.isDestroyed()) viewer.destroy()
  viewer = undefined
  tileset = undefined
})
</script>

<template>
  <div class="city-viewer">
    <div ref="host" class="cesium-host" role="application"
         aria-label="Google 真實城市與路口改善方案 3D 檢視"></div>

    <div class="status-chip" :class="{ ready, failed: !!error }" aria-live="polite">
      <span class="status-dot" aria-hidden="true"></span>
      {{ statusLabel }}
    </div>

    <div v-if="ready" class="view-actions">
      <button type="button" aria-label="將 3D 鏡頭移回路口" @click="resetCamera">
        ↺ 回到路口
      </button>
      <button type="button" :aria-pressed="rotating"
              :aria-label="rotating ? '停止環繞路口' : '開始環繞路口'"
              @click="toggleOrbit">
        {{ rotating ? '停止環繞' : '環繞檢視' }}
      </button>
    </div>

    <div v-if="loading" class="loading-card">
      <span class="loader" aria-hidden="true"></span>
      <p><b>正在載入城市幾何</b><span>建築與地形會依視角逐步清晰</span></p>
    </div>

    <div v-if="error" class="error-card" role="alert">
      <b>真實城市模型尚未就緒</b>
      <p>{{ error }}</p>
    </div>

    <div v-if="ready" class="material-legend" aria-label="改善方案材質圖例">
      <span><i class="asphalt"></i>道路鋪面</span>
      <span><i class="marking"></i>車道標線</span>
      <span><i class="crossing"></i>行穿線</span>
      <span><i class="pedestrian"></i>人行空間</span>
    </div>

    <p v-if="ready" class="interaction-hint">左鍵旋轉・右鍵平移・滾輪縮放</p>
  </div>
</template>

<style scoped>
.city-viewer {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 10;
  overflow: hidden;
  border: 1px solid var(--line-soft);
  border-radius: 14px;
  background: #d7dfe2;
  color: var(--text);
}

.cesium-host,
.cesium-host :deep(.cesium-viewer),
.cesium-host :deep(.cesium-viewer-cesiumWidgetContainer),
.cesium-host :deep(.cesium-widget),
.cesium-host :deep(canvas) {
  width: 100%;
  height: 100%;
}

.cesium-host :deep(canvas) { display: block; }
.cesium-host :deep(.cesium-viewer-bottom) { z-index: 4; }
.cesium-host :deep(.cesium-widget-credits) {
  font-size: 10px;
  text-shadow: 0 1px 2px #000;
}

.status-chip,
.view-actions,
.loading-card,
.error-card,
.material-legend,
.interaction-hint {
  position: absolute;
  z-index: 5;
}

.status-chip {
  top: 12px;
  left: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 11px;
  border: 1px solid rgba(255, 255, 255, .66);
  border-radius: 8px;
  background: rgba(30, 38, 34, .82);
  color: #f7f7f1;
  font: 600 11.5px/1.2 ui-monospace, "Cascadia Mono", Consolas, monospace;
  box-shadow: 0 3px 12px rgba(20, 28, 24, .18);
  backdrop-filter: blur(7px);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #e6b85c;
  box-shadow: 0 0 0 3px rgba(230, 184, 92, .18);
}
.status-chip.ready .status-dot { background: #91b493; box-shadow: 0 0 0 3px rgba(145, 180, 147, .18); }
.status-chip.failed .status-dot { background: #cf7966; box-shadow: 0 0 0 3px rgba(207, 121, 102, .18); }

.view-actions {
  top: 12px;
  right: 12px;
  display: flex;
  gap: 6px;
}
.view-actions button {
  padding: 7px 11px;
  border-color: rgba(255, 255, 255, .62);
  border-radius: 8px;
  background: rgba(250, 249, 244, .9);
  color: var(--green-900);
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 3px 12px rgba(20, 28, 24, .14);
  backdrop-filter: blur(7px);
}
.view-actions button:hover { background: #fff; border-color: #fff; }
.view-actions button:focus-visible { outline: 3px solid #e6b85c; outline-offset: 2px; }

.loading-card,
.error-card {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: min(390px, calc(100% - 40px));
  border: 1px solid rgba(255, 255, 255, .72);
  border-radius: 12px;
  background: rgba(248, 247, 241, .94);
  box-shadow: 0 16px 42px rgba(30, 43, 37, .2);
}
.loading-card {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 18px 22px;
}
.loading-card p { margin: 0; line-height: 1.4; }
.loading-card b { display: block; color: var(--green-900); font-size: 14px; }
.loading-card span { display: block; margin-top: 3px; color: var(--muted); font-size: 12px; }
.loader {
  width: 24px;
  height: 24px;
  flex: none;
  border: 3px solid #d7ddd6;
  border-top-color: var(--green-700);
  border-radius: 50%;
  animation: spin .9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.error-card { padding: 20px 22px; border-left: 4px solid #a8412c; }
.error-card b { color: #7e3426; font-size: 15px; }
.error-card p { margin: 7px 0 0; color: var(--text-2); font-size: 13px; line-height: 1.6; }

.material-legend {
  left: 12px;
  bottom: 42px;
  display: grid;
  grid-template-columns: auto auto;
  gap: 6px 14px;
  padding: 9px 11px;
  border: 1px solid rgba(255, 255, 255, .56);
  border-radius: 8px;
  background: rgba(30, 38, 34, .78);
  color: #f6f6ef;
  font-size: 10.5px;
  line-height: 1.2;
  backdrop-filter: blur(7px);
}
.material-legend span { display: flex; align-items: center; gap: 6px; }
.material-legend i { width: 17px; height: 4px; display: inline-block; border-radius: 1px; }
.material-legend .asphalt { background: #555b57; }
.material-legend .marking { background: repeating-linear-gradient(90deg, #f4f0dc 0 5px, transparent 5px 8px); }
.material-legend .crossing { height: 7px; background: repeating-linear-gradient(90deg, #fffdf4 0 3px, transparent 3px 5px); }
.material-legend .pedestrian { background: #c8c5b7; border: 1px solid #5f665f; }

.interaction-hint {
  right: 12px;
  bottom: 35px;
  margin: 0;
  padding: 5px 9px;
  border-radius: 6px;
  background: rgba(30, 38, 34, .72);
  color: rgba(255, 255, 255, .88);
  font-size: 10.5px;
  backdrop-filter: blur(6px);
}

@media (max-width: 680px) {
  .city-viewer { aspect-ratio: 4 / 3; }
  .status-chip { max-width: calc(100% - 24px); }
  .view-actions { top: 48px; }
  .material-legend { grid-template-columns: auto; bottom: 36px; }
  .interaction-hint { display: none; }
}

@media (prefers-reduced-motion: reduce) {
  .loader { animation: none; }
  .view-actions button { transition: none; }
}
</style>
