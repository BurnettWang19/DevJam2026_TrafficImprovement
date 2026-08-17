# Google Photorealistic 3D Intersection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the handcrafted Three.js building extrusion with Google Photorealistic 3D Tiles and render the proposed road design as realistic, meter-scaled surface markings on the real city mesh.

**Architecture:** FastAPI reads the Map Tiles API key from runtime environment variables and exposes only the browser-required tileset URL through a no-store configuration endpoint, which works both locally and on Cloud Run. The lazily loaded Vue 3D component creates a CesiumJS viewer, streams Google's tiles with mandatory on-screen attribution, and delegates GeoJSON-to-Cesium conversion to a focused overlay module that turns design centerlines into road-width corridors, dashed lane markings, stop bars, and zebra-crossing stripes classified onto the 3D Tiles surface.

**Tech Stack:** FastAPI, Vue 3, Vite 6, CesiumJS, Google Map Tiles API, GeoJSON.

## Global Constraints

- Keep FastAPI and the Vue build in the existing single Cloud Run container architecture.
- Read credentials at runtime; never commit an API key or embed a literal key in source control.
- Accept `GOOGLE_MAP_TILES_API_KEY` as the canonical variable and temporarily accept the already-configured `VITE_GOOGLE_MAP_TILES_API_KEY` as a local compatibility fallback.
- Use Google Photorealistic 3D Tiles only for interactive visualization; do not cache, extract, or send tile imagery to Gemini.
- Set `showCreditsOnScreen: true` so Google and third-party attribution remains visible.
- Preserve the current 2D view and report flow; only replace the implementation behind the existing “3D 檢視” tab.
- Do not add or run automated tests, per the user's instruction. Verification is limited to dependency consistency and a production frontend build.
- Keep all Gemini roles on the currently applicable models; this feature must not alter `backend/models.yaml`.

---

### Task 1: Runtime Map Tiles configuration

**Files:**
- Modify: `.env.example`
- Modify: `backend/config.py`
- Modify: `backend/main.py`

**Interfaces:**
- Produces: `GOOGLE_MAP_TILES_API_KEY: str` in `backend.config`.
- Produces: `GET /api/map-tiles/config -> {"tileset_url": str}` with `Cache-Control: no-store`.
- Produces: `google_map_tiles_api_key: bool` in `/api/health`.

- [x] **Step 1: Document the runtime credential**

Add the following empty entry to `.env.example` without copying the user's real value:

```dotenv
GOOGLE_MAP_TILES_API_KEY=
```

- [x] **Step 2: Load the canonical variable with local compatibility**

Add this next to the existing Google Maps key in `backend/config.py`:

```python
GOOGLE_MAP_TILES_API_KEY = (
    os.getenv("GOOGLE_MAP_TILES_API_KEY", "").strip()
    or os.getenv("VITE_GOOGLE_MAP_TILES_API_KEY", "").strip()
)
```

- [x] **Step 3: Expose a no-store client configuration endpoint**

Import `quote` and `JSONResponse`, import the new config constant, and add this endpoint before the frontend static mount in `backend/main.py`:

```python
from urllib.parse import quote

from fastapi.responses import JSONResponse

@app.get("/api/map-tiles/config")
def map_tiles_config() -> JSONResponse:
    if not GOOGLE_MAP_TILES_API_KEY:
        raise HTTPException(
            503,
            "尚未設定 GOOGLE_MAP_TILES_API_KEY，無法載入 Google Photorealistic 3D Tiles。",
        )
    key = quote(GOOGLE_MAP_TILES_API_KEY, safe="")
    return JSONResponse(
        {"tileset_url": f"https://tile.googleapis.com/v1/3dtiles/root.json?key={key}"},
        headers={"Cache-Control": "no-store"},
    )
```

Add the readiness flag to the health payload:

```python
"google_map_tiles_api_key": bool(GOOGLE_MAP_TILES_API_KEY),
```

- [x] **Step 4: Perform static endpoint review**

Confirm that the route is declared before `app.mount("/", ...)`, that the response never contains Gemini credentials, and that only the URL the browser already needs is returned.

### Task 2: CesiumJS build integration

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/vite.config.js`

**Interfaces:**
- Produces: `cesium` runtime dependency.
- Produces: `/cesiumStatic/{Workers,ThirdParty,Assets,Widgets}` in the Vite build.
- Produces: compile-time `CESIUM_BASE_URL` equal to `/cesiumStatic/`.

- [x] **Step 1: Replace the obsolete renderer dependency**

From `frontend/`, run:

```bash
npm uninstall three
npm install cesium
npm install --save-dev vite-plugin-static-copy
```

Expected result: `package.json` no longer lists `three`, lists `cesium` under `dependencies`, lists `vite-plugin-static-copy` under `devDependencies`, and npm updates the existing lockfile without discarding unrelated lockfile normalization.

- [x] **Step 2: Configure Cesium static assets in Vite**

Replace `frontend/vite.config.js` with this structure while retaining the existing dev proxy:

```js
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { viteStaticCopy } from 'vite-plugin-static-copy'

const cesiumSource = fileURLToPath(new URL('./node_modules/cesium/Build/Cesium', import.meta.url))
const cesiumBaseUrl = 'cesiumStatic'

export default defineConfig({
  define: {
    CESIUM_BASE_URL: JSON.stringify(`/${cesiumBaseUrl}/`),
  },
  plugins: [
    vue(),
    viteStaticCopy({
      targets: [
        { src: `${cesiumSource}/Workers`, dest: cesiumBaseUrl },
        { src: `${cesiumSource}/ThirdParty`, dest: cesiumBaseUrl },
        { src: `${cesiumSource}/Assets`, dest: cesiumBaseUrl },
        { src: `${cesiumSource}/Widgets`, dest: cesiumBaseUrl },
      ],
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
```

### Task 3: GeoJSON road-surface renderer

**Files:**
- Create: `frontend/src/components/design3d/roadOverlay.js`

**Interfaces:**
- Consumes: a Cesium `Viewer` and a validated GeoJSON FeatureCollection whose coordinates are `[longitude, latitude]`.
- Produces: `addRoadDesignOverlay(viewer, geojson): { entityCount: number, layers: string[] }`.

- [x] **Step 1: Define transport-design material specifications**

Create a module-level specification with physical widths in metres and restrained colors that remain readable on aerial photography:

```js
const LAYER_SPEC = {
  roadway: { width: 3.2, color: '#353a37aa', z: 1 },
  sidewalk: { width: 2.2, color: '#c8c5b7dd', edge: '#5f665fff', z: 3 },
  lane_marking: { width: 0.14, color: '#f4f0dcf2', dash: [3, 3], z: 7 },
  channelization: { width: 0.18, color: '#e6b85cf2', dash: [2, 1.4], z: 8 },
  stop_line: { width: 0.48, color: '#fffdf4fa', z: 9 },
  crossing: { width: 0.46, color: '#fffdf4fa', zebra: true, z: 10 },
  crosswalk: { width: 0.46, color: '#fffdf4fa', zebra: true, z: 10 },
  corner_radius: { width: 0.24, color: '#e2ded0f2', z: 6 },
  median: { width: 2.6, color: '#72856fe8', edge: '#3d493cff', z: 4 },
  refuge_island: { width: 2.8, color: '#879581ed', edge: '#3d493cff', z: 5 },
  bulb_out: { width: 2.6, color: '#c8c5b7ed', edge: '#5f665fff', z: 5 },
}
```

- [x] **Step 2: Normalize supported geometry without trusting model output**

Implement `geometryLines(geometry)` for `LineString`, `MultiLineString`, `Polygon`, and `MultiPolygon`; filter every point through `Number.isFinite`, longitude `[-180, 180]`, latitude `[-90, 90]`, and require at least two distinct points per line.

```js
function validPoint(point) {
  return Array.isArray(point)
    && point.length >= 2
    && Number.isFinite(Number(point[0]))
    && Number.isFinite(Number(point[1]))
    && Number(point[0]) >= -180 && Number(point[0]) <= 180
    && Number(point[1]) >= -90 && Number(point[1]) <= 90
}
```

- [x] **Step 3: Convert paths into real dash segments and zebra stripes**

Implement a local equirectangular projection centered on each path, cumulative path-length sampling, and these exact helpers:

```js
function splitDashedPath(points, dashMetres, gapMetres) {
  // Return arrays of two-or-more lng/lat points covering each on interval.
}

function buildZebraStripes(points, stripeWidth = 0.46, gap = 0.54, crossingWidth = 3.6) {
  // Sample the crossing centerline every stripeWidth + gap metres.
  // At each sample, derive the local tangent and return a perpendicular
  // two-point segment of crossingWidth metres.
}
```

The helpers must preserve bends by interpolating against cumulative segment length rather than treating the whole feature as one straight line.

- [x] **Step 4: Add classified, metre-wide corridors**

For each physical segment, call `viewer.entities.add` with a ground corridor and no fixed height:

```js
viewer.entities.add({
  properties: { designLayer: layer },
  corridor: {
    positions: Cartesian3.fromDegreesArray(points.flat()),
    width: spec.width,
    material: Color.fromCssColorString(spec.color),
    cornerType: CornerType.ROUNDED,
    classificationType: ClassificationType.CESIUM_3D_TILE,
    zIndex: spec.z,
  },
})
```

For layers with `edge`, add a darker corridor first at `width + 0.28`, then the fill corridor. For dashed layers, add the result of `splitDashedPath`; for crossings, add the perpendicular result of `buildZebraStripes`. Return the number of added entities and a stable unique list of rendered layers.

### Task 4: Photorealistic 3D viewer

**Files:**
- Replace: `frontend/src/components/Design3D.vue`

**Interfaces:**
- Consumes props: `geojson: FeatureCollection`, `bbox: {south, west, north, east}`.
- Consumes: `GET /api/map-tiles/config`.
- Produces: an interactive Cesium scene with reset-view and optional orbit controls, loading/error states, attribution, and a compact design-material legend.

- [x] **Step 1: Initialize a minimal Cesium viewer**

Import only the required Cesium symbols, its widget stylesheet, `apiGet`, and `addRoadDesignOverlay`. Initialize `Viewer` with timeline, animation, geocoder, base-layer picker, info box, selection indicator, navigation help, and scene mode controls disabled. Disable the globe and atmosphere so Google's mesh is the only basemap.

```js
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
  imageryProvider: false,
  requestRenderMode: true,
  maximumRenderTimeChange: Infinity,
})
viewer.scene.globe.show = false
viewer.scene.skyAtmosphere.show = false
```

- [x] **Step 2: Load the licensed Google tileset**

Fetch the runtime configuration, reject an empty/non-HTTPS Google URL, then create and add the tileset:

```js
const { tileset_url: url } = await apiGet('/api/map-tiles/config')
if (!url?.startsWith('https://tile.googleapis.com/')) throw new Error('3D Tiles 設定無效')
tileset = await Cesium3DTileset.fromUrl(url, {
  showCreditsOnScreen: true,
  maximumScreenSpaceError: 8,
})
viewer.scene.primitives.add(tileset)
```

Set `RequestScheduler.requestsByServer['tile.googleapis.com:443'] = 18` before loading, matching Google's Cesium performance recommendation.

- [x] **Step 3: Frame the selected intersection**

Compute bbox centre and span in metres and reuse one `resetCamera()` function for initial position and the UI button:

```js
const height = Math.max(170, Math.min(900, spanMetres * 2.35))
viewer.camera.flyTo({
  destination: Cartesian3.fromDegrees(centerLng, centerLat, height),
  orientation: {
    heading: CesiumMath.toRadians(18),
    pitch: CesiumMath.toRadians(-48),
    roll: 0,
  },
  duration: 0.8,
})
```

Add the road overlay only after the Google tileset is attached. Report success as “真實城市模型 · N 個設計物件”.

- [x] **Step 4: Preserve intentional interaction and accessibility**

Add quiet, transport-instrument-style controls rather than Cesium's full widget chrome:

- Top-left live status chip: loading, ready, or actionable failure.
- Top-right buttons: `回到路口` and `環繞檢視` / `停止環繞`.
- Bottom-left material legend: `道路鋪面`, `車道標線`, `行穿線`, `人行空間`.
- Bottom hint: `左鍵旋轉・右鍵平移・滾輪縮放`.
- Stop orbit on pointer or wheel input; disable animated orbit under `prefers-reduced-motion`.
- Expose error text with `role="alert"` and buttons with explicit `aria-label`/`aria-pressed`.

Use the existing cream/deep-green system for surrounding chrome, but let the photographic city mesh be the visual signature. Avoid glow, floating tubes, glass panels, and decorative gradients over the map.

- [x] **Step 5: Clean up all Cesium resources**

On unmount, cancel the orbit animation, remove DOM listeners, destroy the Cesium viewer exactly once, and avoid touching it after `viewer.isDestroyed()` becomes true.

### Task 5: Report integration and operational documentation

**Files:**
- Modify: `frontend/src/components/ResultPanel.vue`
- Modify: `README.md`

**Interfaces:**
- `Design3D` no longer consumes the satellite image data URL.
- The 3D view still requires `design.geojson.features` and `bbox`.

- [ ] **Step 1: Update the lazy-view contract**

Change `can3d` and the component invocation to:

```js
const can3d = computed(() =>
  !!(r.value.design?.geojson?.features?.length && r.value.bbox))
```

```vue
<Design3D v-if="view === '3d' && can3d"
          :geojson="r.design.geojson"
          :bbox="r.bbox" />
```

Keep `defineAsyncComponent` so Cesium remains outside the initial application chunk.

- [ ] **Step 2: Document local and Cloud Run configuration**

Add a README section stating:

```dotenv
GOOGLE_MAP_TILES_API_KEY=your_map_tiles_api_key
```

Document that the key must be restricted to Map Tiles API, that browser requests make it observable even though it is delivered at runtime, and that quotas/budget alerts are required. Document `showCreditsOnScreen`, the visualization-only usage, and the local flow `npm install` then `npm run dev` with FastAPI running on port 8000.

- [ ] **Step 3: Document the visual semantics**

State that Photorealistic 3D Tiles are the existing-city context and the colored classified corridors are concept-design overlays, not survey-grade CAD or construction drawings. Describe solid stop bars, dashed lane markings, zebra crossings, and muted pedestrian-space fills.

### Task 6: Non-test build verification

**Files:**
- Verify only; do not create tests.

**Interfaces:**
- Confirms the production bundle can resolve CesiumJS workers/assets and the lazy 3D chunk.

- [ ] **Step 1: Confirm no credentials are tracked**

Run:

```bash
git status --short
git check-ignore .env frontend/.env.local
git diff --check
```

Expected: real `.env` files are ignored, no key appears in the diff, and `git diff --check` emits no whitespace errors.

- [ ] **Step 2: Build the frontend without running tests**

Run:

```bash
cd frontend
npm run build
```

Expected: Vite exits `0`, creates the lazy Cesium/Design3D bundle, and copies `Workers`, `ThirdParty`, `Assets`, and `Widgets` beneath `dist/cesiumStatic/`.

- [ ] **Step 3: Review the final scope**

Run:

```bash
git diff --stat
git diff -- .env.example backend/config.py backend/main.py frontend/package.json frontend/vite.config.js frontend/src/components/design3d/roadOverlay.js frontend/src/components/Design3D.vue frontend/src/components/ResultPanel.vue README.md
```

Expected: no Gemini model changes, no API key literal, no generated `dist/`, and no unrelated application behavior changes.
