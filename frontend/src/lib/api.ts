import type {
  ApiErrorBody,
  ChatAnswer,
  ChatTurn,
  RepositoryAnalysis,
  RepositoryScan,
  Tour,
} from '../types/api'

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

// Errors that will not clear up by asking again, so the UI offers no "Try again".
const FINAL_ERRORS = new Set([
  'llm_not_configured',
  'llm_auth_failed',
  'llm_quota_exhausted',
  'llm_model_unavailable',
  'llm_request_rejected',
  'analysis_not_found',
  'validation_error',
])

export function isRetryable(error: unknown): boolean {
  return !(error instanceof ApiError && FINAL_ERRORS.has(error.code))
}

export function isNotConfigured(error: unknown): boolean {
  return error instanceof ApiError && error.code === 'llm_not_configured'
}

async function send(path: string, body: unknown): Promise<Response> {
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
  return response
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await send(path, body)
  return (await response.json()) as T
}

export type AnalysisStage = 'checking' | 'cloning' | 'analysing'

type StreamLine =
  | { stage: AnalysisStage }
  | { result: RepositoryAnalysis }
  | { error: { code: string; message: string } }

/** Analyse a repository, reporting each real stage as the server reaches it. */
export async function analyzeRepositoryStream(
  url: string,
  onStage: (stage: AnalysisStage) => void,
): Promise<RepositoryAnalysis> {
  const response = await send('/api/repositories/analyze/stream', { url })
  if (!response.body) throw new ApiError(0, 'stream_error', 'The browser could not read the response.')
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (value) buffer += value
    let newline = buffer.indexOf('\n')
    while (newline !== -1) {
      const raw = buffer.slice(0, newline).trim()
      buffer = buffer.slice(newline + 1)
      newline = buffer.indexOf('\n')
      if (!raw) continue
      const line = JSON.parse(raw) as StreamLine
      if ('stage' in line) onStage(line.stage)
      else if ('result' in line) return line.result
      else if ('error' in line) throw new ApiError(200, line.error.code, line.error.message)
    }
    if (done) break
  }
  throw new ApiError(0, 'stream_ended', 'The analysis stopped before it finished. Try again.')
}

export function scanRepository(url: string): Promise<RepositoryScan> {
  return postJson<RepositoryScan>('/api/repositories/scan', { url })
}

export function analyzeRepository(url: string): Promise<RepositoryAnalysis> {
  return postJson<RepositoryAnalysis>('/api/repositories/analyze', { url })
}

export function fetchTour(analysisId: string): Promise<Tour> {
  return postJson<Tour>(`/api/repositories/${encodeURIComponent(analysisId)}/tour`, {})
}

export function askRepository(
  analysisId: string,
  question: string,
  history: ChatTurn[],
): Promise<ChatAnswer> {
  return postJson<ChatAnswer>(`/api/repositories/${encodeURIComponent(analysisId)}/chat`, {
    question,
    history,
  })
}
