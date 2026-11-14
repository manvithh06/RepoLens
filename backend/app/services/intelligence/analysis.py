"""Run every deterministic analysis over an acquired repository."""

import uuid

from app.schemas.analysis import RepositoryAnalysis
from app.services.acquisition.repository import AcquiredRepository, summarize_scan
from app.services.intelligence.entry_points import find_entry_points
from app.services.intelligence.frameworks import detect_frameworks
from app.services.intelligence.graph import build_architecture, build_import_graph
from app.services.intelligence.imports import collect_imports
from app.services.intelligence.languages import detect_languages
from app.services.intelligence.manifests import parse_manifests
from app.services.intelligence.reader import RepoReader
from app.services.intelligence.tree import build_tree


def analyze_repository(repo: AcquiredRepository) -> RepositoryAnalysis:
    """Blocking: call it with asyncio.to_thread while the clone still exists."""
    files = repo.filtered.files
    reader = RepoReader(repo.root, files)

    manifests = parse_manifests(reader)
    imports = collect_imports(reader)
    return RepositoryAnalysis(
        analysis_id=uuid.uuid4().hex,
        scan=summarize_scan(repo),
        languages=detect_languages(files),
        tree=build_tree(files, root_name=repo.info.name),
        manifests=manifests,
        frameworks=detect_frameworks(manifests, reader.paths),
        entry_points=find_entry_points(reader, manifests),
        graph=build_import_graph(reader, imports),
        architecture=build_architecture(reader, imports),
    )
