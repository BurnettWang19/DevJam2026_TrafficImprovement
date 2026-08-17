import {
  Cartesian3,
  ClassificationType,
  Color,
  CornerType,
} from 'cesium'

const METRES_PER_DEGREE_LATITUDE = 111_320
const MAX_FEATURES = 400
const MAX_ENTITIES = 700
const EPSILON_METRES = 0.01

// Widths are physical metres. Colors stay close to real paving materials so the
// proposal reads as a design intervention rather than a floating diagram.
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

function validPoint(point) {
  if (!Array.isArray(point) || point.length < 2) return false
  const lng = Number(point[0])
  const lat = Number(point[1])
  return Number.isFinite(lng)
    && Number.isFinite(lat)
    && lng >= -180 && lng <= 180
    && lat >= -90 && lat <= 90
}

function cleanLine(line) {
  if (!Array.isArray(line)) return []
  const cleaned = []
  for (const point of line) {
    if (!validPoint(point)) continue
    const next = [Number(point[0]), Number(point[1])]
    const previous = cleaned.at(-1)
    if (!previous || previous[0] !== next[0] || previous[1] !== next[1]) {
      cleaned.push(next)
    }
  }
  return cleaned.length >= 2 ? cleaned : []
}

function geometryLines(geometry) {
  const coordinates = geometry?.coordinates
  let lines = []
  switch (geometry?.type) {
    case 'LineString':
      lines = [coordinates]
      break
    case 'MultiLineString':
    case 'Polygon':
      lines = coordinates
      break
    case 'MultiPolygon':
      lines = Array.isArray(coordinates) ? coordinates.flat() : []
      break
    default:
      return []
  }
  return (Array.isArray(lines) ? lines : [])
    .map(cleanLine)
    .filter((line) => line.length >= 2)
}

function projectionFor(points) {
  const originLng = points.reduce((sum, point) => sum + point[0], 0) / points.length
  const originLat = points.reduce((sum, point) => sum + point[1], 0) / points.length
  const metresPerDegreeLongitude = Math.max(
    METRES_PER_DEGREE_LATITUDE * Math.cos(originLat * Math.PI / 180),
    0.001,
  )
  return {
    toLocal([lng, lat]) {
      return [
        (lng - originLng) * metresPerDegreeLongitude,
        (lat - originLat) * METRES_PER_DEGREE_LATITUDE,
      ]
    },
    toLngLat([x, y]) {
      return [
        originLng + x / metresPerDegreeLongitude,
        originLat + y / METRES_PER_DEGREE_LATITUDE,
      ]
    },
  }
}

function pathMetrics(points) {
  const projection = projectionFor(points)
  const local = points.map(projection.toLocal)
  const cumulative = [0]
  for (let index = 1; index < local.length; index += 1) {
    const dx = local[index][0] - local[index - 1][0]
    const dy = local[index][1] - local[index - 1][1]
    cumulative.push(cumulative.at(-1) + Math.hypot(dx, dy))
  }
  return {
    projection,
    local,
    cumulative,
    total: cumulative.at(-1),
  }
}

function pointAtDistance(metrics, requestedDistance) {
  const distance = Math.min(Math.max(requestedDistance, 0), metrics.total)
  let index = 1
  while (index < metrics.cumulative.length - 1
      && metrics.cumulative[index] < distance) {
    index += 1
  }

  const segmentStart = metrics.cumulative[index - 1]
  const segmentEnd = metrics.cumulative[index]
  const segmentLength = segmentEnd - segmentStart
  const start = metrics.local[index - 1]
  const end = metrics.local[index]
  const ratio = segmentLength > EPSILON_METRES
    ? (distance - segmentStart) / segmentLength
    : 0
  const xy = [
    start[0] + (end[0] - start[0]) * ratio,
    start[1] + (end[1] - start[1]) * ratio,
  ]
  const tangent = segmentLength > EPSILON_METRES
    ? [(end[0] - start[0]) / segmentLength, (end[1] - start[1]) / segmentLength]
    : [1, 0]
  return { xy, tangent }
}

function pathBetween(metrics, startDistance, endDistance) {
  if (endDistance - startDistance <= EPSILON_METRES) return []
  const path = [pointAtDistance(metrics, startDistance).xy]
  for (let index = 1; index < metrics.local.length - 1; index += 1) {
    const distance = metrics.cumulative[index]
    if (distance > startDistance && distance < endDistance) {
      path.push(metrics.local[index])
    }
  }
  path.push(pointAtDistance(metrics, endDistance).xy)
  return cleanLine(path.map(metrics.projection.toLngLat))
}

function splitDashedPath(points, dashMetres, gapMetres) {
  const metrics = pathMetrics(points)
  if (metrics.total <= EPSILON_METRES) return []
  const dash = Math.max(Number(dashMetres) || 0, 0.1)
  const gap = Math.max(Number(gapMetres) || 0, 0.1)
  const paths = []
  for (let start = 0; start < metrics.total && paths.length < MAX_ENTITIES; start += dash + gap) {
    const path = pathBetween(metrics, start, Math.min(start + dash, metrics.total))
    if (path.length >= 2) paths.push(path)
  }
  return paths
}

function buildZebraStripes(
  points,
  stripeWidth = 0.46,
  gap = 0.54,
  crossingWidth = 3.6,
) {
  const metrics = pathMetrics(points)
  if (metrics.total <= EPSILON_METRES) return []
  const step = stripeWidth + gap
  const first = Math.min(stripeWidth / 2, metrics.total / 2)
  const stripes = []

  for (let distance = first;
    distance <= metrics.total && stripes.length < MAX_ENTITIES;
    distance += step) {
    const { xy, tangent } = pointAtDistance(metrics, distance)
    const halfWidth = crossingWidth / 2
    const perpendicular = [-tangent[1], tangent[0]]
    const endpoints = [
      [xy[0] - perpendicular[0] * halfWidth, xy[1] - perpendicular[1] * halfWidth],
      [xy[0] + perpendicular[0] * halfWidth, xy[1] + perpendicular[1] * halfWidth],
    ]
    stripes.push(endpoints.map(metrics.projection.toLngLat))
  }

  if (!stripes.length) {
    const { xy, tangent } = pointAtDistance(metrics, metrics.total / 2)
    const halfWidth = crossingWidth / 2
    const perpendicular = [-tangent[1], tangent[0]]
    stripes.push([
      metrics.projection.toLngLat([
        xy[0] - perpendicular[0] * halfWidth,
        xy[1] - perpendicular[1] * halfWidth,
      ]),
      metrics.projection.toLngLat([
        xy[0] + perpendicular[0] * halfWidth,
        xy[1] + perpendicular[1] * halfWidth,
      ]),
    ])
  }
  return stripes
}

function addCorridor(viewer, points, layer, width, color, zIndex) {
  const coordinates = points.flatMap(([lng, lat]) => [lng, lat])
  if (coordinates.length < 4) return false
  viewer.entities.add({
    properties: { designLayer: layer },
    corridor: {
      positions: Cartesian3.fromDegreesArray(coordinates),
      width,
      material: Color.fromCssColorString(color),
      cornerType: CornerType.ROUNDED,
      classificationType: ClassificationType.CESIUM_3D_TILE,
      zIndex,
    },
  })
  return true
}

/**
 * Project the proposed design onto the Google 3D Tiles surface.
 * Invalid model-generated geometry is ignored instead of reaching Cesium.
 */
export function addRoadDesignOverlay(viewer, geojson) {
  const features = Array.isArray(geojson?.features)
    ? geojson.features.slice(0, MAX_FEATURES)
    : []
  const renderedLayers = new Set()
  let entityCount = 0

  for (const feature of features) {
    if (entityCount >= MAX_ENTITIES) break
    const layer = String(feature?.properties?.layer || '')
    const spec = LAYER_SPEC[layer]
    if (!spec) continue

    for (const line of geometryLines(feature?.geometry)) {
      if (entityCount >= MAX_ENTITIES) break
      let physicalPaths = [line]
      if (spec.dash) physicalPaths = splitDashedPath(line, ...spec.dash)
      if (spec.zebra) physicalPaths = buildZebraStripes(line, spec.width)

      for (const path of physicalPaths) {
        const entitiesNeeded = spec.edge ? 2 : 1
        if (entityCount + entitiesNeeded > MAX_ENTITIES) break
        if (spec.edge) {
          const edgeAdded = addCorridor(
            viewer,
            path,
            layer,
            spec.width + 0.28,
            spec.edge,
            spec.z * 2,
          )
          if (edgeAdded) entityCount += 1
        }
        const fillAdded = addCorridor(
          viewer,
          path,
          layer,
          spec.width,
          spec.color,
          spec.z * 2 + 1,
        )
        if (fillAdded) {
          entityCount += 1
          renderedLayers.add(layer)
        }
      }
    }
  }

  return {
    entityCount,
    layers: [...renderedLayers].sort(),
  }
}
