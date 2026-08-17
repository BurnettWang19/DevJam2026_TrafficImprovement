import axios, { AxiosError } from 'axios'

export interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
  }
}

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string
  ) {
    super(message)
  }
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api',
  timeout: 300000
})

export function normalizeApiError(error: unknown): ApiError {
  if (!axios.isAxiosError<ApiErrorBody>(error)) {
    return new ApiError('UNKNOWN_ERROR', 'An unexpected error occurred.')
  }

  const axiosError = error as AxiosError<ApiErrorBody>
  if (axiosError.code === 'ECONNABORTED') {
    return new ApiError('ANALYSIS_TIMEOUT', '分析時間超過五分鐘，請縮小分析範圍後再試一次。')
  }

  if (!axiosError.response) {
    return new ApiError('NETWORK_ERROR', '無法連線到後端服務，請確認後端正在執行。')
  }

  const body = axiosError.response.data
  return new ApiError(
    body.error?.code ?? 'SERVER_ERROR',
    body.error?.message ?? 'The backend could not complete the request.'
  )
}
