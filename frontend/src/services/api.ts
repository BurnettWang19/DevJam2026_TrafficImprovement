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
  timeout: 30000
})

export function normalizeApiError(error: unknown): ApiError {
  if (!axios.isAxiosError<ApiErrorBody>(error)) {
    return new ApiError('UNKNOWN_ERROR', 'An unexpected error occurred.')
  }

  const axiosError = error as AxiosError<ApiErrorBody>
  if (!axiosError.response) {
    return new ApiError('NETWORK_ERROR', 'Unable to reach the backend API.')
  }

  const body = axiosError.response.data
  return new ApiError(
    body.error?.code ?? 'SERVER_ERROR',
    body.error?.message ?? 'The backend could not complete the request.'
  )
}
