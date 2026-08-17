import type { Feature, FeatureCollection as BaseFeatureCollection, LineString } from 'geojson'

export type GeoJsonProperties = Record<string, string | number | boolean | null | string[]>

export type GeoJsonFeature = Feature<LineString, GeoJsonProperties>

export interface FeatureCollection extends BaseFeatureCollection<LineString, GeoJsonProperties> {
  crs?: {
    type: 'name'
    properties: {
      name: 'EPSG:4326' | string
    }
  }
}
