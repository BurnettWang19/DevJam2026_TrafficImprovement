import { api, normalizeApiError } from './api'
import type { IntersectionRequest, IntersectionResponse } from '../types/intersection'

export async function createIntersection(
  payload: IntersectionRequest
): Promise<IntersectionResponse> {
  try {
    const response = await api.post<IntersectionResponse>('/intersections', payload)
    return response.data
  } catch (error) {
    throw normalizeApiError(error)
  }
}
