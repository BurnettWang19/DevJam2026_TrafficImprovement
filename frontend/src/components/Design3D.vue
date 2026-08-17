<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { apiGet } from '../api'

/* 3D 設計檢視器：
   - 衛星影像鋪成地面
   - 重繪後的設計向量依圖層懸浮在不同高度（管狀線條 + 淡淡自發光）
   - 自動旋轉展示，滑鼠/觸控可自由環繞、縮放；動一下就停止自轉 */

const props = defineProps({
  image: { type: String, required: true },     // 衛星影像 data URL
  geojson: { type: Object, required: true },   // 設計向量 FeatureCollection
  bbox: { type: Object, required: true },      // {south, west, north, east}
})

const host = ref(null)
const failed = ref(false)
const rotating = ref(true)

const SIZE = 100                 // 地面平面邊長（world units）

/* 各圖層的視覺規格：粗細、離地高度、顏色 */
const LAYER_SPEC = {
  roadway:       { r: 0.32, y: 0.25, color: 0x8d968f },
  lane_marking:  { r: 0.28, y: 0.40, color: 0xe8dcae },
  channelization:{ r: 0.30, y: 0.40, color: 0xd97b29 },
  stop_line:     { r: 0.42, y: 0.45, color: 0xd97b29 },
  crossing:      { r: 0.55, y: 0.60, color: 0xfdfcf8 },
  corner_radius: { r: 0.40, y: 0.55, color: 0x2f5d45 },
  sidewalk:      { r: 0.60, y: 0.95, color: 0x3d7355 },
  bulb_out:      { r: 0.70, y: 1.15, color: 0x2f5d45 },
  median:        { r: 0.70, y: 1.15, color: 0x244834 },
  refuge_island: { r: 0.72, y: 1.30, color: 0x1e3a2b },
}

let renderer, scene, camera, controls, raf, ro
const disposables = []

function toXZ(lng, lat) {
  const { south, west, north, east } = props.bbox
  const x = ((lng - west) / (east - west) - 0.5) * SIZE
  const z = ((lat - south) / (north - south) - 0.5) * -SIZE   // 北在畫面「上」
  return [x, z]
}

function buildScene() {
  scene = new THREE.Scene()

  /* 地面：衛星影像 */
  const tex = new THREE.TextureLoader().load(props.image)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.anisotropy = 4
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(SIZE, SIZE),
    new THREE.MeshBasicMaterial({ map: tex }),
  )
  ground.rotation.x = -Math.PI / 2
  scene.add(ground)
  disposables.push(ground.geometry, ground.material, tex)

  /* 底座：讓地面像一塊模型沙盤 */
  const slab = new THREE.Mesh(
    new THREE.BoxGeometry(SIZE + 4, 3, SIZE + 4),
    new THREE.MeshStandardMaterial({ color: 0x244834, roughness: .85 }),
  )
  slab.position.y = -1.6
  scene.add(slab)
  disposables.push(slab.geometry, slab.material)

  /* 設計向量 → 各圖層懸浮管線 */
  const feats = (props.geojson?.features || [])
  for (const f of feats) {
    const layer = f.properties?.layer
    const spec = LAYER_SPEC[layer]
    const geom = f.geometry || {}
    if (!spec || geom.type !== 'LineString') continue
    const coords = geom.coordinates || []
    if (coords.length < 2) continue

    const pts = coords.map(([lng, lat]) => {
      const [x, z] = toXZ(lng, lat)
      return new THREE.Vector3(x, spec.y, z)
    })
    const curve = new THREE.CatmullRomCurve3(pts)
    const tube = new THREE.TubeGeometry(
      curve, Math.max(pts.length * 4, 12), spec.r, 6, false)
    const mat = new THREE.MeshStandardMaterial({
      color: spec.color,
      emissive: spec.color,
      emissiveIntensity: .25,
      roughness: .5,
    })
    scene.add(new THREE.Mesh(tube, mat))
    disposables.push(tube, mat)
  }

  /* 光 */
  scene.add(new THREE.AmbientLight(0xffffff, 1.0))
  const sun = new THREE.DirectionalLight(0xfff4e0, 1.4)
  sun.position.set(60, 90, 40)
  scene.add(sun)
}

/* 從 OSM 抓建築物輪廓，擠出成立體量體。失敗就靜默略過。 */
async function loadBuildings() {
  const { south, west, north, east } = props.bbox
  let data
  try {
    data = await apiGet(
      `/api/buildings?south=${south}&west=${west}&north=${north}&east=${east}`)
  } catch {
    return
  }
  if (!scene || !data?.buildings?.length) return

  // 1 世界單位 = 幾公尺：由 bbox 的實際寬度換算，讓建築高度是「真的」等比例
  const midLat = (south + north) / 2
  const widthM = (east - west) * 111320 * Math.cos((midLat * Math.PI) / 180)
  const unitsPerMeter = SIZE / widthM

  const matA = new THREE.MeshStandardMaterial({ color: 0xece7db, roughness: .9 })
  const matB = new THREE.MeshStandardMaterial({ color: 0xdfd8c6, roughness: .9 })
  const roofEdge = new THREE.MeshStandardMaterial({ color: 0xd4cdbb, roughness: .95 })
  disposables.push(matA, matB, roofEdge)

  data.buildings.forEach((b, i) => {
    const ring = b.ring || []
    if (ring.length < 4) return
    const shape = new THREE.Shape()
    ring.forEach(([lng, lat], k) => {
      const [x, z] = toXZ(lng, lat)
      if (k === 0) shape.moveTo(x, -z)
      else shape.lineTo(x, -z)
    })
    const h = Math.max(b.height_m * unitsPerMeter, 1.2)
    const geo = new THREE.ExtrudeGeometry(shape, { depth: h, bevelEnabled: false })
    const mesh = new THREE.Mesh(geo, i % 2 ? matA : matB)
    mesh.rotation.x = -Math.PI / 2      // 讓擠出方向朝上
    scene.add(mesh)
    disposables.push(geo)

    // 屋頂描一圈細邊，增加量體的辨識度
    const top = new THREE.LineSegments(
      new THREE.EdgesGeometry(geo, 30),
      new THREE.LineBasicMaterial({ color: 0xb8b09c }),
    )
    top.rotation.x = -Math.PI / 2
    scene.add(top)
    disposables.push(top.geometry, top.material)
  })
}

onMounted(() => {
  const el = host.value
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  } catch {
    failed.value = true
    return
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(el.clientWidth, el.clientHeight)
  el.appendChild(renderer.domElement)

  camera = new THREE.PerspectiveCamera(
    42, el.clientWidth / el.clientHeight, 1, 600)
  camera.position.set(58, 72, 58)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(0, 0, 0)
  controls.enableDamping = true
  controls.dampingFactor = .06
  controls.minDistance = 35
  controls.maxDistance = 220
  controls.maxPolarAngle = 1.42          // 不鑽到地面下
  controls.autoRotate = true
  controls.autoRotateSpeed = 1.1
  controls.addEventListener('start', () => {
    controls.autoRotate = false
    rotating.value = false
  })

  buildScene()
  loadBuildings()

  const tick = () => {
    controls.update()
    renderer.render(scene, camera)
    raf = requestAnimationFrame(tick)
  }
  raf = requestAnimationFrame(tick)

  ro = new ResizeObserver(() => {
    const w = el.clientWidth, h = el.clientHeight
    if (!w || !h) return
    camera.aspect = w / h
    camera.updateProjectionMatrix()
    renderer.setSize(w, h)
  })
  ro.observe(el)
})

function toggleRotate() {
  rotating.value = !rotating.value
  if (controls) controls.autoRotate = rotating.value
}

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  ro?.disconnect()
  controls?.dispose()
  disposables.forEach((d) => d.dispose?.())
  renderer?.dispose()
  if (renderer?.domElement?.parentNode) {
    renderer.domElement.parentNode.removeChild(renderer.domElement)
  }
})
</script>

<template>
  <div class="wrap3d">
    <div ref="host" class="canvas3d"></div>
    <p v-if="failed" class="fail">此裝置不支援 WebGL，無法顯示 3D 檢視。</p>
    <template v-else>
      <button class="spin" @click="toggleRotate">
        {{ rotating ? '⏸ 停止旋轉' : '▶ 自動旋轉' }}
      </button>
      <p class="hint3d">拖曳環繞・滾輪縮放。線條高度代表圖層：越高越接近人行設施。</p>
    </template>
  </div>
</template>

<style scoped>
.wrap3d { position: relative; width: 100%; }
.canvas3d {
  width: 100%;
  aspect-ratio: 4 / 3;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid var(--line-soft);
  background:
    radial-gradient(120% 90% at 50% 10%, #f9f8f3 0%, #e9ece0 70%, #dfe4d4 100%);
  cursor: grab;
}
.canvas3d:active { cursor: grabbing; }
.canvas3d :deep(canvas) { display: block; }

.spin {
  position: absolute; top: 12px; right: 12px;
  font-size: 12.5px; padding: 6px 14px; border-radius: 999px;
  box-shadow: 0 4px 14px rgba(30, 58, 43, .15);
}
.hint3d {
  margin: 10px 0 0; font-size: 12.5px; color: var(--muted); text-align: center;
}
.fail {
  position: absolute; inset: 0; display: grid; place-content: center;
  margin: 0; color: var(--muted); font-size: 14px;
}
</style>
