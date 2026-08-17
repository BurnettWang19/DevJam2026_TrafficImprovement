import type { FeatureCollection } from './geojson'

export interface Location {
  latitude: number
  longitude: number
}

export interface IntersectionRequest extends Location {
  radiusMeters: number
}

export interface IntersectionResponse {
  intersectionId: string
  location: Location
  geojson: FeatureCollection
}

export type AnalysisStatus = 'idle' | 'selected' | 'loading' | 'loaded' | 'error'
