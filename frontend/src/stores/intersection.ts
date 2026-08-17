import { defineStore } from 'pinia'

import { createIntersection } from '../services/intersection'
import type { FeatureCollection } from '../types/geojson'
import type { AnalysisStatus, Location } from '../types/intersection'

interface IntersectionState {
  selectedLocation: Location | null
  intersectionId: string | null
  geojson: FeatureCollection | null
  analysisStatus: AnalysisStatus
  loading: boolean
  error: string | null
  errorCode: string | null
  radiusMeters: number
}

export const useIntersectionStore = defineStore('intersection', {
  state: (): IntersectionState => ({
    selectedLocation: null,
    intersectionId: null,
    geojson: null,
    analysisStatus: 'idle',
    loading: false,
    error: null,
    errorCode: null,
    radiusMeters: 100
  }),
  actions: {
    selectLocation(location: Location) {
      this.selectedLocation = location
      this.analysisStatus = 'selected'
      this.error = null
      this.errorCode = null
    },
    async analyzeSelectedLocation() {
      if (!this.selectedLocation) {
        this.error = 'Select a location on the map first.'
        this.errorCode = 'NO_LOCATION_SELECTED'
        this.analysisStatus = 'error'
        return
      }

      this.loading = true
      this.analysisStatus = 'loading'
      this.error = null
      this.errorCode = null

      try {
        const response = await createIntersection({
          ...this.selectedLocation,
          radiusMeters: this.radiusMeters
        })
        this.intersectionId = response.intersectionId
        this.geojson = response.geojson
        this.analysisStatus = 'loaded'
      } catch (error) {
        const apiError = error as Error & { code?: string }
        this.error = apiError.message
        this.errorCode = apiError.code ?? 'UNKNOWN_ERROR'
        this.analysisStatus = 'error'
      } finally {
        this.loading = false
      }
    }
  }
})
