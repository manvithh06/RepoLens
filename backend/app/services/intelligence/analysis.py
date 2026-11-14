"""Run every deterministic analysis over an acquired repository."""

import uuid
from dataclasses import dataclass

from app.schemas.analysis import RepositoryAnalysis
from app.services.acquisition.repository import AcquiredRepository, summarize_scan
from app.services.chat.chunks import build_chunks
from app.services.chat.index import ChatIndex
from app.services.intelligence.entry_points import find_entry_points
from app.services.intelligence.frameworks import detect_frameworks
from app.services.intelligence.graph import build_architecture, build_import_graph
from app.services.intelligence.imports import collect_imports
from app.services.intelligence.improvements import Context, find_improvements
from app.services.intelligence.languages import detect_languages
from app.services.intelligence.manifests import parse_manifests
from app.services.intelligence.reader import RepoReader
from app.services.intelligence.tree import build_tree
from app.services.store import StoredAnalysis
from app.services.tour.material import build_tour_material


@dataclass(frozen=True)
class AnalysisBundle:
    analysis: RepositoryAnalysis  # sent to the browser
    stored: StoredAnalysis  # kept in memory for the tour and chat


def _line_counts(reader: RepoReader) -> dict[str, int]:
    counts = {}
    for path in reader.paths:
        text = reader.text(path) or ""
        counts[path] = text.count("\n") + (0 if not text or text.endswith("\n") else 1)
    return counts


def analyze_repository(repo: AcquiredRepository) -> AnalysisBundle:
    """Blocking: call it with asyncio.to_thread while the clone still exists."""
    files = repo.filtered.files
    reader = RepoReader(repo.root, files)

    scan = summarize_scan(repo)
    manifests = parse_manifests(reader)
    imports = collect_imports(reader)
    entry_points = find_entry_points(reader, manifests)
    graph = build_import_graph(reader, imports)
    improvements = find_improvements(
        Context(
            reader=reader,
            scan=scan,
            manifests=manifests,
            graph=graph,
            entry_points=entry_points,
        )
    )
    analysis = RepositoryAnalysis(
        analysis_id=uuid.uuid4().hex,
        scan=scan,
        languages=detect_languages(files),
        tree=build_tree(files, root_name=repo.info.name),
        manifests=manifests,
        frameworks=detect_frameworks(manifests, reader.paths),
        entry_points=entry_points,
        graph=graph,
        architecture=build_architecture(reader, imports),
        improvements=improvements,
    )
    stored = StoredAnalysis(
        analysis_id=analysis.analysis_id,
        full_name=repo.info.full_name,
        description=repo.info.description,
        branch=repo.info.default_branch,
        commit=repo.commit,
        line_counts=_line_counts(reader),
        tour_material=build_tour_material(analysis, reader),
        chat_index=ChatIndex(build_chunks(reader)),
    )
    return AnalysisBundle(analysis=analysis, stored=stored)
