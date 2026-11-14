"""Pick and copy the files the tour will read, while the clone still exists.

Excerpts are line-numbered so the model can cite lines, secrets are masked, and .env
files are never included.
"""

from dataclasses import dataclass, field

from app.core.limits import MAX_TOUR_FILE_CHARS, MAX_TOUR_FILES
from app.schemas.analysis import RepositoryAnalysis
from app.services.intelligence.graph import OTHER_GROUP, group_at
from app.services.intelligence.improvements import is_env_file, redact_secrets
from app.services.intelligence.reader import RepoReader

MAX_FOLDER_LISTING = 40
_MAX_ENTRIES = 4
_MAX_HUBS = 6
_MAX_MANIFESTS = 2


@dataclass(frozen=True)
class FileExcerpt:
    path: str
    module: str
    reason: str  # why it was picked: readme, entry point, imported by N files, manifest
    text: str  # line-numbered, possibly cut short
    truncated: bool


@dataclass(frozen=True)
class TourMaterial:
    files: list[FileExcerpt]
    folders: dict[str, list[str]] = field(default_factory=dict)
    entry_points: list[str] = field(default_factory=list)
    stack: list[str] = field(default_factory=list)
    edges: list[str] = field(default_factory=list)


def numbered_excerpt(text: str, limit: int = MAX_TOUR_FILE_CHARS) -> tuple[str, bool]:
    lines: list[str] = []
    used = 0
    for number, line in enumerate(text.splitlines(), start=1):
        row = f"{number:>5} | {line[:300]}"
        if used + len(row) + 1 > limit:
            return "\n".join(lines), True
        lines.append(row)
        used += len(row) + 1
    return "\n".join(lines), False


def _pick_files(
    analysis: RepositoryAnalysis, reader: RepoReader
) -> list[tuple[str, str]]:
    picked: dict[str, str] = {}

    def add(path: str, reason: str) -> None:
        if len(picked) < MAX_TOUR_FILES and reader.has(path) and not is_env_file(path):
            picked.setdefault(path, reason)

    readme = next(
        (p for p in reader.paths if "/" not in p and p.lower().startswith("readme")),
        None,
    )
    if readme:
        add(readme, "README")
    for entry in [e for e in analysis.entry_points if e.kind != "Web page"][
        :_MAX_ENTRIES
    ]:
        add(entry.path, f"entry point ({entry.kind})")
    hubs = sorted(
        (n for n in analysis.graph.nodes if n.kind == "source" and n.imported_by > 0),
        key=lambda n: (-n.imported_by, n.id),
    )
    for node in hubs[:_MAX_HUBS]:
        add(node.id, f"imported by {node.imported_by} files")
    manifests = sorted(
        (m for m in analysis.manifests if not m.error),
        key=lambda m: (m.path.count("/"), m.path),
    )
    for manifest in manifests[:_MAX_MANIFESTS]:
        add(manifest.path, "dependency manifest")
    return list(picked.items())


def build_tour_material(
    analysis: RepositoryAnalysis, reader: RepoReader
) -> TourMaterial:
    depth = max(analysis.architecture.depth, 1)
    modules = {m.id for m in analysis.architecture.modules}

    def module_of(path: str) -> str:
        group = group_at(path, depth)
        return group if group in modules or not modules else OTHER_GROUP

    files = []
    for path, reason in _pick_files(analysis, reader):
        text = reader.text(path)
        if text is None:
            continue
        excerpt, truncated = numbered_excerpt(redact_secrets(text))
        files.append(
            FileExcerpt(
                path=path,
                module=module_of(path),
                reason=reason,
                text=excerpt,
                truncated=truncated,
            )
        )

    folders: dict[str, list[str]] = {}
    for path in reader.paths:
        if is_env_file(path):
            continue
        listing = folders.setdefault(module_of(path), [])
        if len(listing) < MAX_FOLDER_LISTING:
            listing.append(path)

    edges = sorted(analysis.architecture.edges, key=lambda e: -e.weight)[:20]
    return TourMaterial(
        files=files,
        folders=folders,
        entry_points=[
            f"{e.kind}: {e.path}{f':{e.line}' if e.line else ''}"
            for e in analysis.entry_points[:10]
        ],
        stack=[f"{f.name} ({f.category})" for f in analysis.frameworks],
        edges=[f"{e.source} -> {e.target} ({e.weight} imports)" for e in edges],
    )
