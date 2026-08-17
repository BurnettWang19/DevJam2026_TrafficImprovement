import { api, normalizeApiError } from './api'
import type { AnalysisRequest, AnalysisResult } from '../types/analysis'

export async function analyzeIntersection(payload: AnalysisRequest): Promise<AnalysisResult> {
  try {
    const response = await api.post<AnalysisResult>('/analyses', payload)
    return response.data
  } catch (error) {
    throw normalizeApiError(error)
  }
}
