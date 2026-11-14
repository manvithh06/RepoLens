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

export interface Evidence {
  path: string
  line: number | null
}

export interface LanguageStat {
  name: string
  files: number
  bytes: number
  percent: number
}

export interface LanguageBreakdown {
  code: LanguageStat[]
  other: LanguageStat[]
  primary: string | null
  unknown_files: number
}

export interface TreeNode {
  name: string
  path: string
  is_dir: boolean
  size: number
  file_count: number
  children: TreeNode[]
}

export interface Dependency {
  name: string
  spec: string
  dev: boolean
  line: number | null
}

export interface Manifest {
  path: string
  kind: string
  ecosystem: string
  name: string | null
  dependencies: Dependency[]
  scripts: Record<string, string>
  error: string | null
}

export type FrameworkCategory =
  | 'Frontend'
  | 'Backend'
  | 'Data and storage'
  | 'Machine learning and AI'
  | 'Testing'
  | 'Build and tooling'
  | 'Deployment and CI'

export interface Framework {
  name: string
  category: FrameworkCategory
  evidence: Evidence[]
}

export interface EntryPoint {
  path: string
  line: number | null
  kind: string
  detail: string
}

export type ModuleKind = 'source' | 'test' | 'example'

export interface GraphNode {
  id: string
  language: string | null
  kind: ModuleKind
  size: number
  imports: number
  imported_by: number
}

export interface GraphEdge {
  source: string
  target: string
}

export interface Cycle {
  files: string[]
  group_size: number
}

export interface ExternalPackage {
  name: string
  ecosystem: 'python' | 'npm'
  files: number
}

export interface ImportGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  truncated: boolean
  total_files: number
  total_edges: number
  cycles: Cycle[]
  external_packages: ExternalPackage[]
  parse_errors: number
  unresolved_imports: number
}

export interface ArchitectureModule {
  id: string
  label: string
  kind: ModuleKind
  file_count: number
  size: number
}

export interface ArchitectureEdge {
  source: string
  target: string
  weight: number
}

export interface ArchitectureGraph {
  depth: number
  modules: ArchitectureModule[]
  edges: ArchitectureEdge[]
}

export interface RepositoryAnalysis {
  analysis_id: string
  scan: RepositoryScan
  languages: LanguageBreakdown
  tree: TreeNode
  manifests: Manifest[]
  frameworks: Framework[]
  entry_points: EntryPoint[]
  graph: ImportGraph
  architecture: ArchitectureGraph
  improvements: Finding[]
}

export type Severity = 'high' | 'medium' | 'low'

export interface Finding {
  id: string
  title: string
  severity: Severity
  category: string
  status: 'Confirmed' | 'Potential'
  evidence: Evidence[]
  evidence_total: number
  detail: string | null
  why: string
  fix: string
}

export interface Citation {
  path: string
  line: number | null
  is_dir: boolean
}

export interface Tour {
  analysis_id: string
  model: string
  commit: string | null
  overview: { text: string; citations: Citation[]; verified: boolean } | null
  steps: { title: string; detail: string; citations: Citation[] }[]
  modules: { name: string; path: string; summary: string; citations: Citation[] }[]
  start_here: { path: string; reason: string }[]
  diagram: string | null
  files_read: string[]
  dropped_claims: number
  cached: boolean
}
