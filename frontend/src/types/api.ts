export interface RepositoryInfo {
  owner: string
  name: string
  full_name: string
  html_url: string
  description: string | null
  default_branch: string
  primary_language: string | null
  size_kb: number
}

export interface RepositoryScan {
  repository: RepositoryInfo
  file_count: number
  total_bytes: number
  truncated: boolean
  skipped: Record<string, number>
  extensions: Record<string, number>
  sample_paths: string[]
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
  }
}
