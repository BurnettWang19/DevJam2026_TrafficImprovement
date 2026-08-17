import { defineStore } from 'pinia'

import { demoAnalysis } from '../data/demoAnalysis'
import { analyzeIntersection } from '../services/analysis'
import type { AnalysisResult } from '../types/analysis'
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
  analysisResult: AnalysisResult | null
}

const RESULT_STORAGE_KEY = 'intersection-analysis-result'

function loadStoredResult(): AnalysisResult | null {
  try {
    const stored = localStorage.getItem(RESULT_STORAGE_KEY)
    return stored ? (JSON.parse(stored) as AnalysisResult) : null
  } catch {
    return null
  }
}

function saveResult(result: AnalysisResult | null) {
  try {
    if (result) localStorage.setItem(RESULT_STORAGE_KEY, JSON.stringify(result))
    else localStorage.removeItem(RESULT_STORAGE_KEY)
  } catch {
    // Large generated images can exceed browser storage; the current session still keeps the result.
  }
}

export const useIntersectionStore = defineStore('intersection', {
  state: (): IntersectionState => {
    const storedResult = loadStoredResult()
    return {
      selectedLocation: storedResult?.location ?? null,
      intersectionId: storedResult?.analysisId ?? null,
      geojson: null,
      analysisStatus: storedResult ? 'loaded' : 'idle',
      loading: false,
      error: null,
      errorCode: null,
      radiusMeters: 100,
      analysisResult: storedResult
    }
  },
  actions: {
    selectLocation(location: Location) {
      this.selectedLocation = location
      this.analysisStatus = 'selected'
      this.intersectionId = null
      this.geojson = null
      this.analysisResult = null
      saveResult(null)
      this.error = null
      this.errorCode = null
    },
    clearSelection() {
      this.selectedLocation = null
      this.intersectionId = null
      this.geojson = null
      this.analysisResult = null
      saveResult(null)
      this.analysisStatus = 'idle'
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
        const response = await analyzeIntersection({
          ...this.selectedLocation,
          sideLengthMeters: this.radiusMeters
        })
        this.intersectionId = response.analysisId
        this.analysisResult = response
        saveResult(response)
        this.geojson = response.redesignedGeojson ?? response.enrichedGeojson
        this.analysisStatus = 'loaded'
      } catch (error) {
        const apiError = error as Error & { code?: string }
        this.error = apiError.message
        this.errorCode = apiError.code ?? 'UNKNOWN_ERROR'
        this.analysisStatus = 'error'
      } finally {
        this.loading = false
      }
    },
    loadDemoAnalysis() {
      this.selectedLocation = demoAnalysis.location
      this.intersectionId = demoAnalysis.analysisId
      this.analysisResult = demoAnalysis
      this.geojson = demoAnalysis.redesignedGeojson ?? demoAnalysis.enrichedGeojson
      this.analysisStatus = 'loaded'
      this.error = null
      this.errorCode = null
      saveResult(demoAnalysis)
    }
  }
})
