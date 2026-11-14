from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.repository import RepositoryScan
from app.services.intelligence.languages import LanguageBreakdown


class Evidence(BaseModel):
    """A place in the repository that backs up a claim."""

    path: str
    line: int | None = None


class TreeNode(BaseModel):
    name: str
    path: str  # "" for the repository root
    is_dir: bool
    size: int  # bytes; for folders, the total of everything below
    file_count: int  # 1 for files; for folders, the number of files below
    children: list[TreeNode] = Field(default_factory=list)


class Dependency(BaseModel):
    name: str  # normalised (PEP 503 for Python)
    spec: str  # version constraint as written, "" when there is none
    dev: bool = False
    line: int | None = None


class Manifest(BaseModel):
    path: str
    kind: str  # package.json, requirements.txt, pyproject.toml, ...
    ecosystem: str  # npm, pypi, cargo, composer, go, rubygems
    name: str | None = None
    dependencies: list[Dependency] = Field(default_factory=list)
    scripts: dict[str, str] = Field(default_factory=dict)
    error: str | None = None


FrameworkCategory = Literal[
    "Frontend",
    "Backend",
    "Data and storage",
    "Machine learning and AI",
    "Testing",
    "Build and tooling",
    "Deployment and CI",
]


class Framework(BaseModel):
    name: str
    category: FrameworkCategory
    evidence: list[Evidence]


class EntryPoint(BaseModel):
    path: str
    line: int | None = None
    kind: str  # short label, such as "FastAPI app" or "npm script"
    detail: str  # what was found, such as "app = FastAPI()"


ModuleKind = Literal["source", "test", "example"]


class GraphNode(BaseModel):
    id: str  # repository-relative path
    language: str | None
    kind: ModuleKind
    size: int
    imports: int  # local files this file imports
    imported_by: int  # local files that import this file


class GraphEdge(BaseModel):
    source: str
    target: str


class Cycle(BaseModel):
    # A shortest loop in import order: each file imports the next, the last the first.
    files: list[str]
    group_size: int  # how many files are tangled together in total


class ExternalPackage(BaseModel):
    name: str
    ecosystem: Literal["python", "npm"]
    files: int  # how many files import it


class ImportGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool
    total_files: int  # script files before the node cap
    total_edges: int  # edges before the node cap
    cycles: list[Cycle]
    external_packages: list[ExternalPackage]
    parse_errors: int
    unresolved_imports: int


class ArchitectureModule(BaseModel):
    id: str  # folder path, or "(root)"
    label: str
    kind: ModuleKind
    file_count: int
    size: int


class ArchitectureEdge(BaseModel):
    source: str
    target: str
    weight: int  # number of file-level imports between the two folders


class ArchitectureGraph(BaseModel):
    depth: int
    modules: list[ArchitectureModule]
    edges: list[ArchitectureEdge]


Severity = Literal["high", "medium", "low"]
FindingCategory = Literal[
    "Security",
    "Testing",
    "Documentation",
    "Dependencies",
    "Maintainability",
    "Tooling",
    "CI and deployment",
]
FindingStatus = Literal["Confirmed", "Potential"]


class Finding(BaseModel):
    id: str  # which check produced it
    title: str
    severity: Severity
    category: FindingCategory
    # Confirmed: a deterministic rule found it. Potential: a heuristic or model guess.
    status: FindingStatus
    evidence: list[Evidence]  # empty when the finding is that something is missing
    evidence_total: int = 0  # evidence found before the list was capped
    detail: str | None = None
    why: str
    fix: str
    impact: int = Field(default=0, exclude=True)  # tie-breaker for ranking only


class RepositoryAnalysis(BaseModel):
    analysis_id: str
    scan: RepositoryScan
    languages: LanguageBreakdown
    tree: TreeNode
    manifests: list[Manifest]
    frameworks: list[Framework]
    entry_points: list[EntryPoint]
    graph: ImportGraph
    architecture: ArchitectureGraph
    improvements: list[Finding]
