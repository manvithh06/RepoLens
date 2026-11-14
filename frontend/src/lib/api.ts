import type { ApiErrorBody, RepositoryScan } from '../types/api'

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new ApiError(
      0,
      'network_error',
      `Could not reach the RepoLens API at ${API_BASE_URL}. Is the backend running?`,
    )
  }

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiErrorBody | null
    throw new ApiError(
      response.status,
      payload?.error?.code ?? 'unknown_error',
      payload?.error?.message ?? `The request failed with status ${response.status}.`,
    )
  }

  return (await response.json()) as T
}

export function scanRepository(url: string): Promise<RepositoryScan> {
  return postJson<RepositoryScan>('/api/repositories/scan', { url })
}
