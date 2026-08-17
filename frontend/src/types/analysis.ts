import type { FeatureCollection } from './geojson'
import type { Location } from './intersection'

export interface AnalysisRequest extends Location {
  sideLengthMeters: number
}

export interface Finding {
  category: 'crosswalk' | 'sidewalk' | 'lane_marking' | 'overall'
  title: string
  description: string
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  score: number
  evidence_feature_ids: string[]
  recommendation: string
}

export interface ClassicCaseMatch {
  id: string
  title: string
  location: string
  summary: string
  sourceUrl: string
  beforeImageUrl?: string | null
  afterImageUrl?: string | null
  matchReason: string
  score: number
}

export interface ImagePayload {
  mimeType: string
  dataUrl: string
}

export interface AnalysisResult {
  analysisId: string
  status: 'NO_PROBLEM' | 'NOT_INTERSECTION' | 'IMPROVEMENT_PROPOSED' | 'ANALYSIS_FAILED'
  location: Location
  bounds: Record<string, number>
  intersectionType?: string | null
  overallScore?: number | null
  problemSummary: string
  improvementSummary: string
  findings: Finding[]
  matchedCases: ClassicCaseMatch[]
  originalGeojson: FeatureCollection
  enrichedGeojson: FeatureCollection
  redesignedGeojson?: FeatureCollection | null
  sourceImage?: ImagePayload | null
  renderedImage?: ImagePayload | null
  metadata: Record<string, unknown>
}
